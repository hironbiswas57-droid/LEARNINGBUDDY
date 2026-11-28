"""Provider-neutral tutor and reviewer orchestration."""

import json
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

from ..config import settings
from ..db import db


class OpenAICompatibleClient:
    def chat(self, model: str, messages: list, temperature: float = 0.4) -> str:
        if not settings.llm_api_key or not model:
            raise RuntimeError("AI provider credentials and model are not configured.")
        body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode("utf-8")
        request = urllib.request.Request(settings.llm_base_url.rstrip("/") + "/chat/completions", data=body, headers={"Authorization": "Bearer " + settings.llm_api_key, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"].strip()


class TutorService:
    def __init__(self, client: Optional[OpenAICompatibleClient] = None):
        self.client = client or OpenAICompatibleClient()

    def _tutor_draft(self, question: str, retry_note: str = "", history: Optional[list] = None, age_bracket: str = "adult") -> str:
        if settings.llm_provider == "mock":
            return ("Let’s work through that together. First, restate the idea in your own words and identify what you already know. "
                    "Then try one small step and check whether it moves you toward the goal. "
                    "If you share the subject and the part that feels unclear, I can make the next hint more specific. "
                    "This demo response has not been fact-checked.")
        messages = [
            {"role": "system", "content": "You are LearnMate, tutoring a " + age_bracket + " learner. Use an age-appropriate, hint-first Socratic style, explain reasoning in small steps, and never invent citations. If unsure, say so."},
        ] + (history or []) + [
            {"role": "user", "content": question + (("\nReviewer note: " + retry_note) if retry_note else "")},
        ]
        return self.client.chat(settings.llm_model, messages)

    def _review(self, question: str, answer: str, trusted_material: str = "", age_bracket: str = "adult") -> Dict[str, str]:
        if not settings.llm_api_key or not settings.reviewer_model:
            return {"status": "unavailable", "reason": "No reviewer model is configured."}
        prompt = "Review the draft for factual and logical correctness, age appropriateness, and support from the trusted material. Return ONLY JSON: {\"approved\": boolean, \"reason\": string}. If the material is insufficient or you are uncertain, approve=false."
        try:
            raw = self.client.chat(settings.reviewer_model, [{"role": "system", "content": prompt}, {"role": "user", "content": "Learner age group: " + age_bracket + "\nQuestion: " + question + "\nTrusted course material: " + (trusted_material or "No trusted course material supplied.") + "\nDraft answer: " + answer}], temperature=0)
            result = json.loads(raw)
            return {"status": "approved" if result.get("approved") is True else "rejected", "reason": str(result.get("reason", ""))[:500]}
        except (Exception, json.JSONDecodeError) as exc:
            return {"status": "unavailable", "reason": str(exc)[:250] or "Reviewer service unavailable."}

    def reply(self, user: Dict[str, Any], question: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        question = question.strip()
        if not question or len(question) > 4000:
            raise ValueError("Ask a question of 1 to 4000 characters.")
        with db() as connection:
            if conversation_id:
                conversation = connection.execute("SELECT id FROM ai_conversations WHERE id=? AND user_id=?", (conversation_id, user["id"])).fetchone()
                if not conversation:
                    raise PermissionError("That conversation is unavailable.")
                thread_id = conversation_id
            else:
                thread_id = str(uuid.uuid4())
                connection.execute("INSERT INTO ai_conversations(id,user_id,title) VALUES(?,?,?)", (thread_id, user["id"], question[:60]))
            history = [{"role": row["role"], "content": row["content"]} for row in connection.execute("SELECT role,content FROM ai_messages WHERE conversation_id=? ORDER BY created_at DESC,id DESC LIMIT 10", (thread_id,)).fetchall()]
            history.reverse()
            user_message_id = str(uuid.uuid4())
            connection.execute("INSERT INTO ai_messages(id,conversation_id,role,content) VALUES(?,?,?,?)", (user_message_id, thread_id, "user", question))
        age_bracket = user.get("age_bracket", "adult")
        answer = self._tutor_draft(question, history=history, age_bracket=age_bracket)
        review = self._review(question, answer, age_bracket=age_bracket)
        if review["status"] == "rejected":
            revised = self._tutor_draft(question, review["reason"], history=history, age_bracket=age_bracket)
            revised_review = self._review(question, revised, age_bracket=age_bracket)
            answer, review = revised, revised_review
        answer_status = "verified" if review["status"] == "approved" else "unverified"
        with db() as connection:
            message_id = str(uuid.uuid4())
            connection.execute("INSERT INTO ai_messages(id,conversation_id,role,content,verification_status) VALUES(?,?,?,?,?)", (message_id, thread_id, "assistant", answer, answer_status))
            connection.execute("INSERT INTO ai_verification_logs(id,message_id,status,reviewer,notes) VALUES(?,?,?,?,?)", (str(uuid.uuid4()), message_id, review["status"], settings.reviewer_model or "unconfigured", review["reason"]))
            return {"conversation_id": thread_id, "message_id": message_id, "answer": answer,
                    "verification": {"status": answer_status, "reviewer_status": review["status"], "reason": review["reason"]}}

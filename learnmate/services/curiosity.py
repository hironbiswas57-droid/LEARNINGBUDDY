"""Curiosity research, learner scoped recommendations, and discussion rooms."""

import json
import re
import uuid
from typing import Any, Dict, Optional

from ..db import db
from .tutor import TutorService


ARTICLES = [
    ("paper-crow-tools", "Young crows can invent tools", "A bird meets a puzzle with no instructions. What could it make?", "Researchers found that young New Caledonian crows could make and use tools without seeing other crows do it first. The result raises a fascinating question: how much problem-solving can emerge from curiosity and practice?", "Animal minds", "Nature", "https://www.nature.com/articles/433121a"),
    ("paper-crow-brains", "Inside the minds of clever crows", "Why do some crows become especially good at solving tool puzzles?", "A study of American crows linked differences in tool-learning performance with activity in brain circuits. It is a reminder that a species-wide ability can still look different from one individual to another.", "Animal minds", "Nature Communications", "https://www.nature.com/articles/s41467-023-42203-8"),
    ("paper-crow-compound-tools", "When one tool becomes two", "Could an animal join objects together to solve a problem?", "Scientists studied New Caledonian crows building compound tools. The work explores whether a clever solution comes from planning ahead, learning by trial and error, or a mix of both.", "Invention", "Scientific Reports", "https://www.nature.com/articles/s41598-018-33458-z"),
    ("paper-collective-intelligence", "Can a group think better by taking turns?", "More talking is not always the same as better teamwork.", "Researchers ran experiments on how interaction patterns affect groups solving problems. Their results explore a surprising design question: can brief pauses help people think independently before combining ideas?", "People & ideas", "PNAS", "https://www.pnas.org/doi/10.1073/pnas.1802407115"),
]

ROOMS = [
    ("room-wild-science", "Wild science", "Science", "What everyday thing would you love to investigate? Bring one observation and one possible explanation."),
    ("room-impossible-inventions", "Impossible inventions", "Imagination", "Invent something that solves a tiny, real-world annoyance. Sketch the idea in words."),
    ("room-many-lenses", "Many lenses", "Big questions", "Choose a question with no single answer. What changes when someone sees it differently?"),
]


def seed_catalog() -> None:
    with db() as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO research_articles(id,title,hook,summary,topic,source_name,source_url) VALUES(?,?,?,?,?,?,?)",
            ARTICLES,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO curiosity_rooms(id,name,topic,prompt,age_min,age_max) VALUES(?,?,?,?,13,17)", ROOMS
        )


def _age(user: Dict[str, Any]) -> str:
    return user.get("age_bracket", "adult")


def get_articles(user: Dict[str, Any]) -> Dict[str, Any]:
    with db() as connection:
        connection.execute("INSERT OR IGNORE INTO curiosity_preferences(user_id) VALUES(?)", (user["id"],))
        rows = connection.execute(
            """SELECT a.*, EXISTS(SELECT 1 FROM research_article_events e WHERE e.user_id=? AND e.article_id=a.id AND e.event_type='save'
                 AND e.id=(SELECT e2.id FROM research_article_events e2 WHERE e2.user_id=e.user_id AND e2.article_id=e.article_id ORDER BY e2.created_at DESC,e2.rowid DESC LIMIT 1)) AS saved
                 FROM research_articles a WHERE a.is_active=1 AND a.age_min<=? AND a.age_max>=? ORDER BY a.topic,a.title""",
            (user["id"], 13 if _age(user) == "teen" else 18, 13 if _age(user) == "teen" else 18),
        ).fetchall()
        preference = connection.execute("SELECT recommendations_enabled FROM curiosity_preferences WHERE user_id=?", (user["id"],)).fetchone()
        topics = []
        if preference and preference[0]:
            topics = [row[0] for row in connection.execute("""SELECT topic FROM (
                SELECT a.topic AS topic, CASE e.event_type WHEN 'save' THEN 2 ELSE 1 END AS weight
                  FROM research_article_events e JOIN research_articles a ON a.id=e.article_id
                 WHERE e.user_id=? AND e.event_type IN ('view','save')
                UNION ALL
                SELECT a.topic AS topic, CASE q.helpful WHEN 1 THEN 2 ELSE -1 END AS weight
                  FROM curiosity_questions q JOIN research_articles a ON a.id=q.article_id
                 WHERE q.user_id=? AND q.helpful IS NOT NULL
            ) GROUP BY topic HAVING SUM(weight)>0 ORDER BY SUM(weight) DESC LIMIT 2""", (user["id"], user["id"])).fetchall()]
        return {"articles": [dict(row) for row in rows], "recommendations_enabled": bool(preference[0]) if preference else False, "recommended_topics": topics}


def get_public_articles() -> list:
    with db() as connection:
        rows = connection.execute("SELECT id,title,hook,summary,topic,reading_minutes,source_name,source_url FROM research_articles WHERE is_active=1 ORDER BY topic,title").fetchall()
        return [dict(row) for row in rows]


def article_event(user: Dict[str, Any], article_id: str, event_type: str) -> Dict[str, Any]:
    if event_type not in ("view", "save", "unsave"):
        raise ValueError("Event must be view, save, or unsave.")
    with db() as connection:
        if not connection.execute("SELECT 1 FROM research_articles WHERE id=? AND is_active=1", (article_id,)).fetchone():
            raise LookupError("Research note not found.")
        connection.execute("INSERT INTO research_article_events(id,user_id,article_id,event_type) VALUES(?,?,?,?)", (str(uuid.uuid4()), user["id"], article_id, event_type))
        return {"recorded": True, "event": event_type}


def preferences(user: Dict[str, Any], enabled: Optional[bool] = None) -> Dict[str, Any]:
    with db() as connection:
        connection.execute("INSERT OR IGNORE INTO curiosity_preferences(user_id) VALUES(?)", (user["id"],))
        if enabled is not None:
            connection.execute("UPDATE curiosity_preferences SET recommendations_enabled=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (int(enabled), user["id"]))
        row = connection.execute("SELECT recommendations_enabled FROM curiosity_preferences WHERE user_id=?", (user["id"],)).fetchone()
        return {"recommendations_enabled": bool(row[0]), "scope": "Only this learner's own reading, saves, and article-specific answer feedback."}


def ask(user: Dict[str, Any], data: Dict[str, Any], tutor: TutorService) -> Dict[str, Any]:
    question = str(data.get("question", "")).strip()
    if not question or len(question) > 2000:
        raise ValueError("Ask a question of 1 to 2000 characters.")
    article_id = data.get("article_id") or None
    if article_id is not None:
        with db() as connection:
            if not connection.execute("SELECT 1 FROM research_articles WHERE id=? AND is_active=1", (article_id,)).fetchone():
                raise ValueError("Choose a research note from the curiosity library.")
    result = tutor.reply(user, question, data.get("conversation_id"))
    deck = {
        "start_here": "Name the part you want to understand, then compare it with the explanation below.",
        "explanation": result["answer"],
        "try_next": "What evidence would help you check this idea? Look for the method and limits in the original research.",
        "verification": result["verification"]["status"],
    }
    item_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("INSERT INTO curiosity_questions(id,user_id,article_id,conversation_id,prompt,answer,solution_deck,verification_status) VALUES(?,?,?,?,?,?,?,?)", (item_id, user["id"], article_id, result["conversation_id"], question, result["answer"], json.dumps(deck), result["verification"]["status"]))
    return {"id": item_id, "conversation_id": result["conversation_id"], "question": question, "answer": result["answer"], "verification": result["verification"], "solution_deck": deck}


def history(user: Dict[str, Any]) -> list:
    with db() as connection:
        rows = connection.execute("SELECT id,prompt,answer,solution_deck,verification_status,article_id,created_at FROM curiosity_questions WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user["id"],)).fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            row["solution_deck"] = json.loads(row["solution_deck"])
        return result


def feedback(user: Dict[str, Any], question_id: str, helpful: bool) -> Dict[str, Any]:
    with db() as connection:
        cursor = connection.execute("UPDATE curiosity_questions SET helpful=? WHERE id=? AND user_id=?", (int(helpful), question_id, user["id"]))
        if not cursor.rowcount:
            raise LookupError("Curiosity answer not found.")
        return {"saved": True}


def rooms(user: Optional[Dict[str, Any]] = None) -> list:
    age = 13 if user is None or _age(user) == "teen" else 18
    with db() as connection:
        rows = connection.execute("SELECT r.*, (SELECT COUNT(*) FROM curiosity_room_messages m WHERE m.room_id=r.id AND m.status='visible') AS message_count FROM curiosity_rooms r WHERE r.is_active=1 AND r.age_min<=? AND r.age_max>=? ORDER BY r.name", (age, age)).fetchall()
        return [dict(row) for row in rows]


def messages(user: Dict[str, Any], room_id: str, limit: int = 60) -> list:
    age = 13 if _age(user) == "teen" else 18
    with db() as connection:
        if not connection.execute("SELECT 1 FROM curiosity_rooms WHERE id=? AND is_active=1 AND age_min<=? AND age_max>=?", (room_id, age, age)).fetchone():
            raise LookupError("Study circle not found.")
        rows = connection.execute("""SELECT m.id,m.user_id,u.display_name,m.body,m.status,m.created_at FROM curiosity_room_messages m JOIN users u ON u.id=m.user_id
             WHERE m.room_id=? AND (m.status='visible' OR m.user_id=?) ORDER BY m.created_at DESC LIMIT ?""", (room_id, user["id"], max(1, min(limit, 100)))).fetchall()
        return [dict(row) for row in reversed(rows)]


_CONTACT = re.compile(r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\s().-]*){9,})")


def post_message(user: Dict[str, Any], room_id: str, body: str) -> Dict[str, Any]:
    body = body.strip()
    if not body or len(body) > 1000:
        raise ValueError("Write a message of 1 to 1000 characters.")
    status = "pending_review" if _CONTACT.search(body) else "visible"
    message_id = str(uuid.uuid4())
    age = 13 if _age(user) == "teen" else 18
    with db() as connection:
        if not connection.execute("SELECT 1 FROM curiosity_rooms WHERE id=? AND is_active=1 AND age_min<=? AND age_max>=?", (room_id, age, age)).fetchone():
            raise LookupError("Study circle not found.")
        connection.execute("INSERT INTO curiosity_room_messages(id,room_id,user_id,body,status) VALUES(?,?,?,?,?)", (message_id, room_id, user["id"], body, status))
        return {"id": message_id, "user_id": user["id"], "display_name": user["display_name"], "body": body, "status": status}


def report_message(user: Dict[str, Any], message_id: str, reason: str) -> Dict[str, Any]:
    reason = reason.strip()[:300]
    if not reason:
        raise ValueError("Add a short reason for the report.")
    age = 13 if _age(user) == "teen" else 18
    with db() as connection:
        row = connection.execute("SELECT m.user_id,r.age_min,r.age_max FROM curiosity_room_messages m JOIN curiosity_rooms r ON r.id=m.room_id WHERE m.id=? AND r.is_active=1", (message_id,)).fetchone()
        if not row:
            raise LookupError("Message not found.")
        if not row["age_min"] <= age <= row["age_max"]:
            raise LookupError("Message not found.")
        if row["user_id"] == user["id"]:
            raise ValueError("You cannot report your own message.")
        connection.execute("INSERT OR IGNORE INTO curiosity_message_reports(id,message_id,reporter_id,reason) VALUES(?,?,?,?)", (str(uuid.uuid4()), message_id, user["id"], reason))
        connection.execute("UPDATE curiosity_room_messages SET status='pending_review' WHERE id=?", (message_id,))
        return {"reported": True, "status": "pending_review"}

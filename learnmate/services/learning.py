"""Learner profile, catalog, progress, goals, and focus operations."""

from datetime import date, timedelta
import json
import uuid
from typing import Any, Dict, List

from ..db import db


def profile_for(user_id: str) -> Dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT u.id,u.email,u.display_name,u.role,u.age_bracket,u.preferred_language,p.* FROM users u LEFT JOIN learner_profiles p ON p.user_id=u.id WHERE u.id=?", (user_id,)).fetchone()
        if not row:
            return {}
        result = dict(row)
        for key in ("interests", "accessibility_preferences"):
            if result.get(key):
                result[key] = json.loads(result[key])
        return result


def update_profile(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"display_name", "preferred_language", "education_level", "learning_pace", "interests", "accessibility_preferences", "daily_target_minutes"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError("Unsupported profile fields: " + ", ".join(sorted(unknown)))
    with db() as connection:
        if "display_name" in data:
            name = str(data["display_name"]).strip()
            if not name or len(name) > 100:
                raise ValueError("Display name is required and must be under 100 characters.")
            connection.execute("UPDATE users SET display_name=? WHERE id=?", (name, user_id))
        if "preferred_language" in data:
            language = str(data["preferred_language"]).strip()[:12]
            if not language:
                raise ValueError("Preferred language cannot be empty.")
            connection.execute("UPDATE users SET preferred_language=? WHERE id=?", (language, user_id))
        profile_fields = {key: data[key] for key in ("education_level", "learning_pace") if key in data}
        for key, value in profile_fields.items():
            if not isinstance(value, str) or not value.strip() or len(value) > 80:
                raise ValueError(key.replace("_", " ").capitalize() + " must be a non-empty string under 80 characters.")
            connection.execute("UPDATE learner_profiles SET " + key + "=? WHERE user_id=?", (value.strip(), user_id))
        for key in ("interests", "accessibility_preferences"):
            if key in data:
                value = data[key]
                if not isinstance(value, list) or len(value) > 30 or not all(isinstance(item, str) and len(item) <= 80 for item in value):
                    raise ValueError(key.replace("_", " ").capitalize() + " must be a list of up to 30 short strings.")
                connection.execute("UPDATE learner_profiles SET " + key + "=? WHERE user_id=?", (json.dumps(value), user_id))
        if "daily_target_minutes" in data:
            target = int(data["daily_target_minutes"])
            if target < 5 or target > 480:
                raise ValueError("Daily target must be between 5 and 480 minutes.")
            connection.execute("UPDATE learner_profiles SET daily_target_minutes=? WHERE user_id=?", (target, user_id))
    return profile_for(user_id)


def courses_for(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    age = {"toddler": 5, "child": 10, "teen": 16, "adult": 25}.get(user["age_bracket"], 25)
    with db() as connection:
        rows = connection.execute("""SELECT c.id,c.title,c.description,c.level,c.duration_minutes,s.name AS subject,s.color,
          COALESCE(e.progress,0) AS progress, CASE WHEN e.user_id IS NULL THEN 0 ELSE 1 END AS enrolled,
          (SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) AS lesson_count
          FROM courses c LEFT JOIN subjects s ON s.id=c.subject_id LEFT JOIN course_enrollments e ON e.course_id=c.id AND e.user_id=?
          WHERE c.is_published=1 AND c.age_min<=? AND c.age_max>=? ORDER BY c.title""", (user["id"], age, age)).fetchall()
        return [dict(row) for row in rows]


def overview(user: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    start = today - timedelta(days=6)
    with db() as connection:
        profile = connection.execute("SELECT xp,streak_days,daily_target_minutes FROM learner_profiles WHERE user_id=?", (user["id"],)).fetchone()
        minutes = {row["record_date"]: row["minutes"] for row in connection.execute("SELECT record_date,minutes FROM streak_records WHERE user_id=? AND record_date>=?", (user["id"], start.isoformat()))}
        goals = connection.execute("SELECT COUNT(*) total, SUM(completed) complete FROM learning_goals WHERE user_id=? AND due_date=?", (user["id"], today.isoformat())).fetchone()
        sessions = connection.execute("SELECT COUNT(*) total, COALESCE(SUM(CASE WHEN ended_at IS NOT NULL THEN 1 ELSE 0 END),0) completed FROM study_sessions WHERE user_id=? AND started_at>=?", (user["id"], start.isoformat())).fetchone()
        badges = connection.execute("SELECT badge_key,earned_at FROM achievements WHERE user_id=? ORDER BY earned_at DESC LIMIT 6", (user["id"],)).fetchall()
        week = [{"date": (start + timedelta(days=index)).isoformat(), "day": (start + timedelta(days=index)).strftime("%a"), "minutes": minutes.get((start + timedelta(days=index)).isoformat(), 0)} for index in range(7)]
        return {"week": week, "today_minutes": minutes.get(today.isoformat(), 0), "daily_target_minutes": profile["daily_target_minutes"] if profile else 60,
                "streak_days": profile["streak_days"] if profile else 0, "xp": profile["xp"] if profile else 0,
                "goals_today": {"total": goals["total"] or 0, "completed": goals["complete"] or 0},
                "study_sessions_week": sessions["total"], "badges": [dict(row) for row in badges]}


def goals_for(user_id: str) -> List[Dict[str, Any]]:
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT id,title,detail,due_date,completed,category FROM learning_goals WHERE user_id=? ORDER BY due_date,created_at", (user_id,))]


def create_goal(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    title = str(data.get("title", "")).strip()
    if not title or len(title) > 140:
        raise ValueError("Goal title is required and must be under 140 characters.")
    goal_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("INSERT INTO learning_goals(id,user_id,title,detail,due_date,category) VALUES(?,?,?,?,?,?)", (goal_id, user_id, title, str(data.get("detail", ""))[:300], str(data.get("due_date") or date.today().isoformat()), str(data.get("category") or "Learning")[:40]))
        row = connection.execute("SELECT id,title,detail,due_date,completed,category FROM learning_goals WHERE id=?", (goal_id,)).fetchone()
        return dict(row)


def update_goal(user_id: str, goal_id: str, completed: bool) -> Dict[str, Any]:
    with db() as connection:
        cursor = connection.execute("UPDATE learning_goals SET completed=? WHERE id=? AND user_id=?", (1 if completed else 0, goal_id, user_id))
        if cursor.rowcount == 0:
            raise LookupError("Goal not found.")
        row = connection.execute("SELECT id,title,detail,due_date,completed,category FROM learning_goals WHERE id=?", (goal_id,)).fetchone()
        return dict(row)


def lessons_for(course_id: str, user_id: str) -> List[Dict[str, Any]]:
    with db() as connection:
        enrolled = connection.execute("SELECT 1 FROM course_enrollments WHERE user_id=? AND course_id=?", (user_id, course_id)).fetchone()
        if not enrolled:
            raise PermissionError("Enroll in this course before opening its lessons.")
        return [dict(row) for row in connection.execute("""SELECT l.id,l.title,l.kind,l.content,l.order_index,
          CASE WHEN c.user_id IS NULL THEN 0 ELSE 1 END AS completed
          FROM lessons l LEFT JOIN lesson_completions c ON c.lesson_id=l.id AND c.user_id=? WHERE l.course_id=? ORDER BY l.order_index""", (user_id, course_id))]


def complete_lesson(user_id: str, lesson_id: str) -> Dict[str, Any]:
    with db() as connection:
        lesson = connection.execute("SELECT course_id FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        enrolled = connection.execute("SELECT 1 FROM course_enrollments WHERE user_id=? AND course_id=?", (user_id, lesson["course_id"])).fetchone() if lesson else None
        if not lesson or not enrolled:
            raise PermissionError("The lesson is unavailable for this learner.")
        inserted = connection.execute("INSERT OR IGNORE INTO lesson_completions(user_id,lesson_id) VALUES(?,?)", (user_id, lesson_id)).rowcount
        total = connection.execute("SELECT COUNT(*) FROM lessons WHERE course_id=?", (lesson["course_id"],)).fetchone()[0]
        done = connection.execute("SELECT COUNT(*) FROM lesson_completions lc JOIN lessons l ON l.id=lc.lesson_id WHERE lc.user_id=? AND l.course_id=?", (user_id, lesson["course_id"])).fetchone()[0]
        progress = done / max(total, 1)
        connection.execute("UPDATE course_enrollments SET progress=? WHERE user_id=? AND course_id=?", (progress, user_id, lesson["course_id"]))
        if inserted:
            connection.execute("UPDATE learner_profiles SET xp=xp+25 WHERE user_id=?", (user_id,))
        return {"lesson_id": lesson_id, "completed": True, "course_progress": progress, "xp_awarded": 25 if inserted else 0}


def enroll(user_id: str, course_id: str) -> Dict[str, Any]:
    with db() as connection:
        course = connection.execute("SELECT id FROM courses WHERE id=? AND is_published=1", (course_id,)).fetchone()
        if not course:
            raise LookupError("Course not found.")
        connection.execute("INSERT OR IGNORE INTO course_enrollments(user_id,course_id) VALUES(?,?)", (user_id, course_id))
        return dict(connection.execute("SELECT course_id,progress,enrolled_at FROM course_enrollments WHERE user_id=? AND course_id=?", (user_id, course_id)).fetchone())


def start_focus(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    duration = int(data.get("planned_minutes", 25))
    if duration < 1 or duration > 180:
        raise ValueError("Focus duration must be between 1 and 180 minutes.")
    course_id = data.get("course_id")
    if course_id:
        with db() as connection:
            enrolled = connection.execute("SELECT 1 FROM course_enrollments WHERE user_id=? AND course_id=?", (user_id, course_id)).fetchone()
            if not enrolled:
                raise PermissionError("Enroll in a course before attaching it to a focus session.")
    session_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("INSERT INTO study_sessions(id,user_id,course_id,started_at,planned_minutes,focus_state) VALUES(?,?,?,CURRENT_TIMESTAMP,?,'active')", (session_id, user_id, course_id, duration))
        return dict(connection.execute("SELECT id,course_id,started_at,planned_minutes,focus_state,distraction_count FROM study_sessions WHERE id=?", (session_id,)).fetchone())


def finish_focus(user_id: str, session_id: str, state: str) -> Dict[str, Any]:
    if state not in ("paused", "completed", "cancelled"):
        raise ValueError("Focus state must be paused, completed, or cancelled.")
    with db() as connection:
        cursor = connection.execute("UPDATE study_sessions SET ended_at=CURRENT_TIMESTAMP,focus_state=? WHERE id=? AND user_id=? AND ended_at IS NULL", (state, session_id, user_id))
        if cursor.rowcount == 0:
            row = connection.execute("SELECT * FROM study_sessions WHERE id=? AND user_id=?", (session_id, user_id)).fetchone()
            if not row:
                raise LookupError("Study session not found.")
        row = connection.execute("SELECT id,started_at,ended_at,planned_minutes,focus_state,distraction_count FROM study_sessions WHERE id=?", (session_id,)).fetchone()
        if cursor.rowcount:
            minutes = connection.execute("SELECT MIN(planned_minutes,MAX(1,CAST((julianday(ended_at)-julianday(started_at))*1440 AS INTEGER))) FROM study_sessions WHERE id=?", (session_id,)).fetchone()[0]
            record_date = date.today().isoformat()
            connection.execute("INSERT INTO streak_records(user_id,record_date,minutes) VALUES(?,?,?) ON CONFLICT(user_id,record_date) DO UPDATE SET minutes=minutes+excluded.minutes", (user_id, record_date, minutes))
            active_dates = {item[0] for item in connection.execute("SELECT record_date FROM streak_records WHERE user_id=? AND minutes>0", (user_id,))}
            streak = 0
            day = date.today()
            while day.isoformat() in active_dates:
                streak += 1
                day -= timedelta(days=1)
            connection.execute("UPDATE learner_profiles SET streak_days=? WHERE user_id=?", (streak, user_id))
        return dict(row)

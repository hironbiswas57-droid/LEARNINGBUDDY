"""Small local learning catalog and development-only demo account."""

from datetime import date, timedelta
from .config import settings
from .db import db
from .security import password_hash


def seed() -> None:
    with db() as connection:
        subjects = [("design", "Product design", "#7067f0"), ("science", "Data science", "#55b6a4"), ("writing", "Writing", "#e4a75b")]
        connection.executemany("INSERT OR IGNORE INTO subjects(id,name,color) VALUES(?,?,?)", subjects)
        courses = [
            ("course-design", "design", "Designing for people", "Learn to turn a messy problem into a thoughtful product experience.", "Intermediate", 155, 13, 99),
            ("course-python", "science", "Python, one idea at a time", "Build a sturdy foundation in Python through short, practical lessons.", "Beginner", 210, 13, 99),
            ("course-writing", "writing", "Write with clarity", "Shape a clear argument and make every sentence do useful work.", "Beginner", 125, 13, 99),
        ]
        connection.executemany("INSERT OR IGNORE INTO courses(id,subject_id,title,description,level,duration_minutes,age_min,age_max) VALUES(?,?,?,?,?,?,?,?)", courses)
        lessons = [
            ("lesson-research", "course-design", "Start with the real problem", "lesson", "Good product work begins with a specific person and a specific moment.", 1),
            ("lesson-signals", "course-design", "Find the useful signals", "lesson", "Look for repeated behaviors, workarounds, and moments of friction.", 2),
            ("lesson-python-data", "course-python", "Give data a name", "lesson", "Variables give a value a name so you can use it again.", 1),
            ("lesson-python-loops", "course-python", "Repeat with loops", "lesson", "Loops let a program repeat a small instruction over a collection.", 2),
            ("lesson-writing-claim", "course-writing", "Make one clear claim", "lesson", "A useful paragraph starts with one idea it can support.", 1),
        ]
        connection.executemany("INSERT OR IGNORE INTO lessons(id,course_id,title,kind,content,order_index) VALUES(?,?,?,?,?,?)", lessons)
        if settings.environment == "development":
            user_id = "demo-learner"
            connection.execute("INSERT OR IGNORE INTO users(id,email,password_hash,display_name,role,age_bracket) VALUES(?,?,?,?,?,?)", (user_id, "demo@learnmate.ai", password_hash("LearnMate123!"), "Maya Chen", "LEARNER", "adult"))
            connection.execute("INSERT OR IGNORE INTO learner_profiles(user_id,education_level,learning_pace,interests,daily_target_minutes,xp,streak_days) VALUES(?,?,?,?,?,?,?)", (user_id, "University", "Visual", '["Product design", "Behavioral science", "Writing"]', 60, 1240, 8))
            connection.executemany("INSERT OR IGNORE INTO course_enrollments(user_id,course_id,progress) VALUES(?,?,?)", [(user_id, "course-design", 0.68), (user_id, "course-python", 0.32), (user_id, "course-writing", 0.85)])
            today = date.today()
            goals = [("goal-research", "Read one research note", "Designing for people", today.isoformat(), 0, "Learning"), ("goal-practice", "Practice for 20 minutes", "Python, one idea at a time", today.isoformat(), 0, "Practice"), ("goal-review", "Review your design notes", "Designing for people", today.isoformat(), 1, "Review")]
            connection.executemany("INSERT OR IGNORE INTO learning_goals(id,user_id,title,detail,due_date,completed,category) VALUES(?,?,?,?,?,?,?)", [(g[0], user_id) + g[1:] for g in goals])
            sample_minutes = [18, 24, 32, 28, 48, 26, 42]
            connection.executemany("INSERT OR IGNORE INTO streak_records(user_id,record_date,minutes) VALUES(?,?,?)", [(user_id, (today - timedelta(days=6-index)).isoformat(), sample_minutes[index]) for index in range(7)])
            connection.execute("INSERT OR IGNORE INTO streak_records(user_id,record_date,minutes) VALUES(?,?,?)", (user_id, (today - timedelta(days=7)).isoformat(), 21))
            connection.execute("INSERT OR IGNORE INTO achievements(id,user_id,badge_key) VALUES(?,?,?)", ("badge-first-steps", user_id, "first_steps"))

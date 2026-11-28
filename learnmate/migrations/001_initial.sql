CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('LEARNER','PARENT','EDUCATOR','MENTOR','MODERATOR','ADMIN')),
  age_bracket TEXT NOT NULL DEFAULT 'adult' CHECK (age_bracket IN ('toddler','child','teen','adult')),
  preferred_language TEXT NOT NULL DEFAULT 'en',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE learner_profiles (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  education_level TEXT NOT NULL DEFAULT 'University',
  learning_pace TEXT NOT NULL DEFAULT 'Steady',
  interests TEXT NOT NULL DEFAULT '[]',
  accessibility_preferences TEXT NOT NULL DEFAULT '[]',
  daily_target_minutes INTEGER NOT NULL DEFAULT 60,
  xp INTEGER NOT NULL DEFAULT 0,
  streak_days INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE guardian_relationships (
  guardian_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  learner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','revoked')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guardian_id, learner_id)
);
CREATE TABLE consent_records (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL,
  granted INTEGER NOT NULL DEFAULT 0,
  granted_by TEXT REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  refresh_hash TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX sessions_user_id_idx ON sessions(user_id);
CREATE TABLE subjects (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT NOT NULL DEFAULT '#5c67e8');
CREATE TABLE courses (
  id TEXT PRIMARY KEY,
  subject_id TEXT REFERENCES subjects(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  level TEXT NOT NULL DEFAULT 'Beginner',
  duration_minutes INTEGER NOT NULL DEFAULT 0,
  age_min INTEGER NOT NULL DEFAULT 13,
  age_max INTEGER NOT NULL DEFAULT 99,
  is_published INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE lessons (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'lesson',
  content TEXT NOT NULL DEFAULT '',
  order_index INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE course_enrollments (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  progress REAL NOT NULL DEFAULT 0,
  enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, course_id)
);
CREATE TABLE lesson_completions (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_id TEXT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
  completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE learning_resources (id TEXT PRIMARY KEY, lesson_id TEXT REFERENCES lessons(id) ON DELETE CASCADE, title TEXT NOT NULL, resource_type TEXT NOT NULL, storage_key TEXT NOT NULL, access_level TEXT NOT NULL DEFAULT 'course');
CREATE TABLE learning_goals (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  due_date TEXT NOT NULL,
  completed INTEGER NOT NULL DEFAULT 0,
  category TEXT NOT NULL DEFAULT 'Learning',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX goals_user_due_idx ON learning_goals(user_id, due_date);
CREATE TABLE study_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  course_id TEXT REFERENCES courses(id),
  started_at TEXT NOT NULL,
  ended_at TEXT,
  planned_minutes INTEGER NOT NULL DEFAULT 25,
  focus_state TEXT NOT NULL DEFAULT 'active',
  distraction_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE ai_conversations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL DEFAULT 'Study session', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX ai_conversations_user_idx ON ai_conversations(user_id, created_at);
CREATE TABLE ai_messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE, role TEXT NOT NULL CHECK (role IN ('user','assistant')), content TEXT NOT NULL, verification_status TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE ai_verification_logs (id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES ai_messages(id) ON DELETE CASCADE, status TEXT NOT NULL, reviewer TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE assessments (id TEXT PRIMARY KEY, course_id TEXT REFERENCES courses(id), title TEXT NOT NULL, assessment_type TEXT NOT NULL DEFAULT 'quiz', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE questions (id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE, prompt TEXT NOT NULL, options TEXT NOT NULL DEFAULT '[]', answer_key TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '', difficulty INTEGER NOT NULL DEFAULT 1);
CREATE TABLE quiz_attempts (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, assessment_id TEXT NOT NULL REFERENCES assessments(id), score REAL NOT NULL DEFAULT 0, submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE quiz_responses (attempt_id TEXT NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE, question_id TEXT NOT NULL REFERENCES questions(id), response TEXT NOT NULL, is_correct INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(attempt_id, question_id));
CREATE TABLE daily_challenges (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, challenge_date TEXT NOT NULL, question_count INTEGER NOT NULL DEFAULT 10, completed_count INTEGER NOT NULL DEFAULT 0, UNIQUE(user_id, challenge_date));
CREATE TABLE streak_records (user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, record_date TEXT NOT NULL, minutes INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, record_date));
CREATE TABLE achievements (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, badge_key TEXT NOT NULL, earned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, badge_key));
CREATE TABLE communities (id TEXT PRIMARY KEY, name TEXT NOT NULL, subject_id TEXT REFERENCES subjects(id), age_min INTEGER NOT NULL DEFAULT 13, age_max INTEGER NOT NULL DEFAULT 99, is_moderated INTEGER NOT NULL DEFAULT 1);
CREATE TABLE community_memberships (community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, status TEXT NOT NULL DEFAULT 'active', PRIMARY KEY(community_id,user_id));
CREATE TABLE discussions (id TEXT PRIMARY KEY, community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE messages (id TEXT PRIMARY KEY, discussion_id TEXT REFERENCES discussions(id) ON DELETE CASCADE, sender_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, media_key TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE moderation_reports (id TEXT PRIMARY KEY, reporter_id TEXT NOT NULL REFERENCES users(id), target_type TEXT NOT NULL, target_id TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE live_sessions (id TEXT PRIMARY KEY, course_id TEXT REFERENCES courses(id), educator_id TEXT NOT NULL REFERENCES users(id), provider TEXT NOT NULL, provider_meeting_id TEXT, starts_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}');
CREATE TABLE attendance_records (session_id TEXT NOT NULL REFERENCES live_sessions(id), user_id TEXT NOT NULL REFERENCES users(id), joined_at TEXT, left_at TEXT, PRIMARY KEY(session_id,user_id));
CREATE TABLE transcripts (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES live_sessions(id), storage_key TEXT NOT NULL, access_policy TEXT NOT NULL DEFAULT 'educator_only');
CREATE TABLE generated_summaries (id TEXT PRIMARY KEY, transcript_id TEXT NOT NULL REFERENCES transcripts(id), content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE certificates (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), course_id TEXT NOT NULL REFERENCES courses(id), issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,course_id));
CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL DEFAULT 'Professional');
CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', visibility TEXT NOT NULL DEFAULT 'private');
CREATE TABLE job_simulations (id TEXT PRIMARY KEY, skill_id TEXT REFERENCES skills(id), title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '{}');
CREATE TABLE career_profiles (user_id TEXT PRIMARY KEY REFERENCES users(id), headline TEXT NOT NULL DEFAULT '', resume_key TEXT, visibility TEXT NOT NULL DEFAULT 'private');
CREATE TABLE marketplace_listings (id TEXT PRIMARY KEY, seller_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', price_cents INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE transactions (id TEXT PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES marketplace_listings(id), buyer_id TEXT NOT NULL REFERENCES users(id), provider_ref TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE notifications (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', read_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE audit_logs (id TEXT PRIMARY KEY, actor_id TEXT REFERENCES users(id), action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT, ip_address TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX audit_logs_actor_idx ON audit_logs(actor_id, created_at);

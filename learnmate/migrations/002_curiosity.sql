CREATE TABLE research_articles (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  hook TEXT NOT NULL,
  summary TEXT NOT NULL,
  topic TEXT NOT NULL,
  reading_minutes INTEGER NOT NULL DEFAULT 4,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  age_min INTEGER NOT NULL DEFAULT 13,
  age_max INTEGER NOT NULL DEFAULT 99,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE curiosity_preferences (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  recommendations_enabled INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE research_article_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id TEXT NOT NULL REFERENCES research_articles(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('view','save','unsave')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX article_events_user_idx ON research_article_events(user_id,created_at);
CREATE TABLE curiosity_questions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id TEXT REFERENCES research_articles(id) ON DELETE SET NULL,
  conversation_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  answer TEXT NOT NULL,
  solution_deck TEXT NOT NULL DEFAULT '{}',
  verification_status TEXT NOT NULL DEFAULT 'unverified',
  helpful INTEGER CHECK (helpful IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX curiosity_questions_user_idx ON curiosity_questions(user_id,created_at);
CREATE TABLE curiosity_rooms (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  topic TEXT NOT NULL,
  prompt TEXT NOT NULL,
  age_min INTEGER NOT NULL DEFAULT 13,
  age_max INTEGER NOT NULL DEFAULT 99,
  is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE curiosity_room_messages (
  id TEXT PRIMARY KEY,
  room_id TEXT NOT NULL REFERENCES curiosity_rooms(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'visible' CHECK (status IN ('visible','pending_review','hidden')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX room_messages_idx ON curiosity_room_messages(room_id,status,created_at);
CREATE TABLE curiosity_message_reports (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL REFERENCES curiosity_room_messages(id) ON DELETE CASCADE,
  reporter_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(message_id,reporter_id)
);

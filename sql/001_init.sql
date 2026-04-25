-- OpenClaw Build Manager
-- V1 initial schema

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  category_id INTEGER,
  owner_agent TEXT NOT NULL DEFAULT 'system_engineer',
  goal TEXT,
  default_context TEXT,
  conversation_provider TEXT,
  conversation_surface TEXT,
  conversation_channel_id TEXT,
  conversation_thread_id TEXT,
  conversation_session_key TEXT,
  conversation_label TEXT,
  conversation_is_canonical INTEGER NOT NULL DEFAULT 0,
  conversation_bound_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  archived_at TEXT,
  FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER,
  parent_task_id INTEGER,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'captured',
  priority INTEGER NOT NULL DEFAULT 3,
  category_id INTEGER,
  next_action TEXT,
  resume_prompt TEXT,
  estimated_minutes INTEGER,
  energy_level TEXT,
  focus_mode TEXT,
  task_type TEXT NOT NULL DEFAULT 'task',
  origin_agent TEXT,
  capture_source TEXT,
  human_active INTEGER NOT NULL DEFAULT 0,
  agent_active INTEGER NOT NULL DEFAULT 0,
  can_agent_execute INTEGER NOT NULL DEFAULT 0,
  needs_user_input INTEGER NOT NULL DEFAULT 0,
  autonomous_safe INTEGER NOT NULL DEFAULT 0,
  waiting_question TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_worked_at TEXT,
  completed_at TEXT,
  archived_at TEXT,
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (parent_task_id) REFERENCES tasks(id),
  FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT
);

CREATE TABLE IF NOT EXISTS task_tags (
  task_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY (task_id, tag_id),
  FOREIGN KEY (task_id) REFERENCES tasks(id),
  FOREIGN KEY (tag_id) REFERENCES tags(id)
);

CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  attachment_type TEXT NOT NULL,
  title TEXT,
  content TEXT,
  path TEXT,
  url TEXT,
  note_ref TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT
);

CREATE TABLE IF NOT EXISTS dependencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  depends_on_task_id INTEGER NOT NULL,
  dependency_type TEXT NOT NULL DEFAULT 'requires',
  created_at TEXT NOT NULL,
  created_by TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(id),
  FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  note_type TEXT NOT NULL,
  title TEXT,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  session_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  planned_minutes INTEGER,
  estimated_human_minutes INTEGER,
  estimated_agent_minutes INTEGER,
  final_human_minutes INTEGER,
  final_agent_minutes INTEGER,
  estimation_confidence REAL,
  needs_confirmation INTEGER NOT NULL DEFAULT 0,
  confirmed_at TEXT,
  created_by TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_human_active ON tasks(human_active);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_active ON tasks(agent_active);
CREATE INDEX IF NOT EXISTS idx_tasks_category_id ON tasks(category_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_entity ON activity_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log(created_at);
CREATE INDEX IF NOT EXISTS idx_notes_entity ON notes(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_work_sessions_task_id ON work_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_work_sessions_started_at ON work_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_dependencies_task_id ON dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_depends_on ON dependencies(depends_on_task_id);

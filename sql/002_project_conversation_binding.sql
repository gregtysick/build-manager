-- Build Manager
-- Add canonical project conversation binding metadata

ALTER TABLE projects ADD COLUMN conversation_provider TEXT;
ALTER TABLE projects ADD COLUMN conversation_surface TEXT;
ALTER TABLE projects ADD COLUMN conversation_channel_id TEXT;
ALTER TABLE projects ADD COLUMN conversation_thread_id TEXT;
ALTER TABLE projects ADD COLUMN conversation_session_key TEXT;
ALTER TABLE projects ADD COLUMN conversation_label TEXT;
ALTER TABLE projects ADD COLUMN conversation_is_canonical INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN conversation_bound_at TEXT;

-- =========================================================
-- Supabase / PostgreSQL Schema Definition for Discord Ticket Bot
-- =========================================================

-- 1. Panels Table
CREATE TABLE IF NOT EXISTS panels (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    color INTEGER DEFAULT 3447003,
    image_url TEXT,
    banner_url TEXT,
    thumbnail_url TEXT,
    footer_text TEXT,
    channel_id BIGINT,
    message_id BIGINT,
    categories_json TEXT DEFAULT '[]'
);

-- 2. Tickets Table
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    panel_id INTEGER NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
    category_id TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    claimed_by BIGINT,
    priority TEXT DEFAULT 'Medium',
    department TEXT,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    first_response_at TEXT,
    is_hidden INTEGER DEFAULT 0,
    last_staff_message_at TEXT,
    member_responded INTEGER DEFAULT 1,
    category_points INTEGER DEFAULT 0
);

-- 3. Ratings Table
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    staff_id BIGINT NOT NULL,
    stars INTEGER NOT NULL,
    feedback TEXT,
    created_at TEXT NOT NULL
);

-- 4. Blacklist Table
CREATE TABLE IF NOT EXISTS blacklist (
    user_id BIGINT PRIMARY KEY,
    reason TEXT NOT NULL,
    added_by BIGINT NOT NULL,
    created_at TEXT NOT NULL
);

-- 5. Guild Settings Table
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    log_channel_id BIGINT,
    transcript_channel_id BIGINT,
    category_id BIGINT,
    owner_role_id BIGINT,
    admin_role_id BIGINT,
    support_manager_role_id BIGINT,
    senior_support_role_id BIGINT,
    support_role_id BIGINT,
    language TEXT DEFAULT 'ar',
    bot_token TEXT
);

-- 6. Internal Notes Table
CREATE TABLE IF NOT EXISTS internal_notes (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 7. Wizard Sessions Table
CREATE TABLE IF NOT EXISTS wizard_sessions (
    user_id BIGINT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 8. Settings Audit Logs Table
CREATE TABLE IF NOT EXISTS settings_audit_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    executor_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);

-- 9. Action Permissions Table
CREATE TABLE IF NOT EXISTS action_permissions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    action_name TEXT NOT NULL,
    min_rank INTEGER DEFAULT 10,
    allowed_roles_json TEXT DEFAULT '[]',
    CONSTRAINT idx_action_permissions_guild_action UNIQUE (guild_id, action_name)
);

-- 10. Ticket Audit Logs Table
CREATE TABLE IF NOT EXISTS ticket_audit_logs (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    executor_id BIGINT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);

-- 11. Staff Stats Table
CREATE TABLE IF NOT EXISTS staff_stats (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    points INTEGER DEFAULT 0,
    tickets_handled INTEGER DEFAULT 0,
    total_stars INTEGER DEFAULT 0,
    total_ratings INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

-- Indexes for Optimal Query Performance
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel_id);
CREATE INDEX IF NOT EXISTS idx_ratings_staff ON ratings(staff_id);
CREATE INDEX IF NOT EXISTS idx_notes_ticket ON internal_notes(ticket_id);
CREATE INDEX IF NOT EXISTS idx_audit_ticket ON ticket_audit_logs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_staff_stats ON staff_stats(guild_id, user_id);

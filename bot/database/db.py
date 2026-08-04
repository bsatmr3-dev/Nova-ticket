import json
import os
import sys
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

class DatabaseManager:
    def __init__(self):
        self.db_path = os.path.abspath(os.path.join("database", "tickets.db"))
        os.makedirs("database", exist_ok=True)
        self.use_postgres = False

        db_url = os.environ.get("DATABASE_URL")
        if HAS_POSTGRES and db_url and db_url.strip():
            sys.stderr.write("[DB_INFO] Testing PostgreSQL connection via DATABASE_URL...\n")
            try:
                conn = self._get_postgres_connection(db_url.strip())
                conn.close()
                self.use_postgres = True
                sys.stderr.write("[DB_INFO] Successfully connected to PostgreSQL database (Supabase)!\n")
            except Exception as e:
                sys.stderr.write(f"[DB_WARNING] PostgreSQL connection failed ({e}). Falling back to local SQLite ({self.db_path})...\n")
                self.use_postgres = False
        else:
            if not HAS_POSTGRES:
                sys.stderr.write(f"[DB_INFO] psycopg2 is not installed in environment. Using local SQLite database ({self.db_path}).\n")
            else:
                sys.stderr.write(f"[DB_INFO] DATABASE_URL is not set. Using local SQLite database ({self.db_path}).\n")
            self.use_postgres = False

        try:
            self._init_db()
        except Exception as e:
            sys.stderr.write(f"[DB_INIT_ERROR] Database initialization error: {e}\n")

    def _get_postgres_connection(self, db_url: str):
        clean_url = db_url.strip()
        if clean_url.startswith("postgres://"):
            clean_url = clean_url.replace("postgres://", "postgresql://", 1)
        
        if "sslmode=" not in clean_url:
            if "?" in clean_url:
                clean_url += "&sslmode=require"
            else:
                clean_url += "?sslmode=require"

        try:
            return psycopg2.connect(clean_url, connect_timeout=10)
        except Exception as e:
            if "sslmode=require" in clean_url:
                try:
                    fallback_url = clean_url.replace("sslmode=require", "sslmode=prefer")
                    return psycopg2.connect(fallback_url, connect_timeout=10)
                except Exception:
                    pass
            raise e

    def _get_sqlite_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        return conn

    def _get_connection(self):
        if self.use_postgres:
            db_url = os.environ.get("DATABASE_URL", "")
            try:
                conn = self._get_postgres_connection(db_url)
                return ("postgres", conn)
            except Exception as conn_err:
                sys.stderr.write(f"[DB_CONN_ERROR] PostgreSQL connection failed ({conn_err}). Falling back to SQLite.\n")
                return ("sqlite", self._get_sqlite_connection())
        else:
            return ("sqlite", self._get_sqlite_connection())

    def _run_query(self, query: str, params: tuple = (), fetch: str = None):
        backend = "sqlite"
        conn = None
        try:
            backend, conn = self._get_connection()
        except Exception as conn_err:
            sys.stderr.write(f"[DB_CONN_CRITICAL] Failed to get connection: {conn_err}\n")
            return None

        try:
            if backend == "postgres":
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                # Convert ? placeholders to %s for PostgreSQL
                p_query = query.replace("?", "%s")
                
                # Convert SQLite-specific upsert syntax to PostgreSQL ON CONFLICT
                if "INSERT OR IGNORE" in p_query:
                    p_query = p_query.replace("INSERT OR IGNORE INTO", "INSERT INTO")
                    if "guild_settings" in p_query:
                        p_query += " ON CONFLICT (guild_id) DO NOTHING"
                    elif "blacklist" in p_query:
                        p_query += " ON CONFLICT (user_id) DO NOTHING"
                    elif "staff_stats" in p_query:
                        p_query += " ON CONFLICT (guild_id, user_id) DO NOTHING"
                elif "INSERT OR REPLACE" in p_query:
                    p_query = p_query.replace("INSERT OR REPLACE INTO", "INSERT INTO")
                    if "guild_settings" in p_query:
                        p_query += " ON CONFLICT (guild_id) DO UPDATE SET guild_id = EXCLUDED.guild_id"
                    elif "blacklist" in p_query:
                        p_query += " ON CONFLICT (user_id) DO UPDATE SET reason = EXCLUDED.reason, added_by = EXCLUDED.added_by, created_at = EXCLUDED.created_at"
                    elif "wizard_sessions" in p_query:
                        p_query += " ON CONFLICT (user_id) DO UPDATE SET state_json = EXCLUDED.state_json, updated_at = EXCLUDED.updated_at"
                    elif "action_permissions" in p_query:
                        p_query += " ON CONFLICT (guild_id, action_name) DO UPDATE SET min_rank = EXCLUDED.min_rank, allowed_roles_json = EXCLUDED.allowed_roles_json"

                if fetch == "lastrowid" and "INSERT INTO" in p_query.upper() and "RETURNING" not in p_query.upper():
                    p_query += " RETURNING id"

                cursor.execute(p_query, params)
                
                result = None
                if fetch == "one":
                    row = cursor.fetchone()
                    result = dict(row) if row else None
                elif fetch == "all":
                    rows = cursor.fetchall()
                    result = [dict(r) for r in rows]
                elif fetch == "lastrowid":
                    try:
                        row = cursor.fetchone()
                        if row:
                            result = row.get("id") or row.get("lastval") or 1
                        else:
                            cursor.execute("SELECT lastval()")
                            r2 = cursor.fetchone()
                            result = r2.get("lastval") if r2 else 1
                    except Exception:
                        result = 1
                
                conn.commit()
                return result

            else: # SQLite
                cursor = conn.cursor()
                # Clean up Postgres specific functions or clauses if any
                s_query = query
                if "CAST(" in s_query and " AS TEXT)" in s_query:
                    s_query = s_query.replace("CAST(channel_id AS TEXT)", "channel_id")

                cursor.execute(s_query, params)
                
                result = None
                if fetch == "one":
                    row = cursor.fetchone()
                    result = dict(row) if row else None
                elif fetch == "all":
                    rows = cursor.fetchall()
                    result = [dict(r) for r in rows]
                elif fetch == "lastrowid":
                    result = cursor.lastrowid

                conn.commit()
                return result

        except Exception as e:
            sys.stderr.write(f"[DB_QUERY_ERROR] Query Error: {e} | Query: {query}\n")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _init_db(self):
        backend, conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if backend == "postgres":
                pk_type = "SERIAL PRIMARY KEY"
                text_type = "TEXT"
                int_type = "INTEGER"
            else:
                pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
                text_type = "TEXT"
                int_type = "INTEGER"
            
            queries = [
                f"""CREATE TABLE IF NOT EXISTS panels (
                    id {pk_type},
                    title {text_type} NOT NULL,
                    description {text_type} NOT NULL,
                    color {int_type} DEFAULT 3447003,
                    image_url {text_type},
                    banner_url {text_type},
                    thumbnail_url {text_type},
                    footer_text {text_type},
                    channel_id BIGINT,
                    message_id BIGINT,
                    categories_json {text_type} DEFAULT '[]'
                )""",
                f"""CREATE TABLE IF NOT EXISTS tickets (
                    id {pk_type},
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL UNIQUE,
                    user_id BIGINT NOT NULL,
                    panel_id {int_type} NOT NULL,
                    category_id {text_type} NOT NULL,
                    status {text_type} DEFAULT 'open',
                    claimed_by BIGINT,
                    priority {text_type} DEFAULT 'Medium',
                    department {text_type},
                    created_at {text_type} NOT NULL,
                    closed_at {text_type},
                    first_response_at {text_type},
                    is_hidden {int_type} DEFAULT 0,
                    last_staff_message_at {text_type},
                    member_responded {int_type} DEFAULT 1,
                    category_points {int_type} DEFAULT 0,
                    evidence_enabled {int_type} DEFAULT 1
                )""",
                f"""CREATE TABLE IF NOT EXISTS ticket_evidence (
                    id {pk_type},
                    ticket_id {int_type} NOT NULL,
                    channel_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    evidence_url {text_type} NOT NULL,
                    note {text_type},
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS ratings (
                    id {pk_type},
                    ticket_id {int_type} NOT NULL,
                    user_id BIGINT NOT NULL,
                    staff_id BIGINT NOT NULL,
                    stars {int_type} NOT NULL,
                    feedback {text_type},
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS blacklist (
                    user_id BIGINT PRIMARY KEY,
                    reason {text_type} NOT NULL,
                    added_by BIGINT NOT NULL,
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    log_channel_id BIGINT,
                    transcript_channel_id BIGINT,
                    category_id BIGINT,
                    owner_role_id BIGINT,
                    admin_role_id BIGINT,
                    support_manager_role_id BIGINT,
                    senior_support_role_id BIGINT,
                    support_role_id BIGINT,
                    language {text_type} DEFAULT 'ar',
                    bot_token {text_type}
                )""",
                f"""CREATE TABLE IF NOT EXISTS internal_notes (
                    id {pk_type},
                    ticket_id {int_type} NOT NULL,
                    author_id BIGINT NOT NULL,
                    content {text_type} NOT NULL,
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS wizard_sessions (
                    user_id BIGINT PRIMARY KEY,
                    state_json {text_type} NOT NULL,
                    updated_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS settings_audit_logs (
                    id {pk_type},
                    guild_id BIGINT NOT NULL,
                    executor_id BIGINT NOT NULL,
                    action {text_type} NOT NULL,
                    details {text_type},
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS action_permissions (
                    id {pk_type},
                    guild_id BIGINT NOT NULL,
                    action_name {text_type} NOT NULL,
                    min_rank {int_type} DEFAULT 10,
                    allowed_roles_json {text_type} DEFAULT '[]',
                    UNIQUE(guild_id, action_name)
                )""",
                f"""CREATE TABLE IF NOT EXISTS ticket_audit_logs (
                    id {pk_type},
                    ticket_id {int_type} NOT NULL,
                    action {text_type} NOT NULL,
                    executor_id BIGINT NOT NULL,
                    details {text_type},
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS staff_stats (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    points {int_type} DEFAULT 0,
                    tickets_handled {int_type} DEFAULT 0,
                    total_stars {int_type} DEFAULT 0,
                    total_ratings {int_type} DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )""",
                f"""CREATE TABLE IF NOT EXISTS closure_info (
                    ticket_id {int_type} PRIMARY KEY,
                    user_handled {int_type} DEFAULT 0,
                    staff_punished {int_type} DEFAULT 0,
                    evidence_urls {text_type},
                    punishment_type {text_type},
                    staff_details {text_type},
                    ticket_type {text_type} DEFAULT 'general',
                    complaint_accepted {int_type} DEFAULT 0,
                    punished_user_id BIGINT DEFAULT 0,
                    timeout_duration {int_type} DEFAULT 0,
                    created_at {text_type} NOT NULL
                )""",
                f"""CREATE TABLE IF NOT EXISTS user_infractions (
                    id {pk_type},
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    infraction_type {text_type} NOT NULL,
                    reason {text_type},
                    duration_minutes {int_type} DEFAULT 0,
                    executor_id BIGINT NOT NULL,
                    ticket_id {int_type} DEFAULT 0,
                    created_at {text_type} NOT NULL
                )"""
            ]
            
            for q in queries:
                cursor.execute(q)
            
            # Column addition checks
            if backend == "postgres":
                try:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='tickets' AND column_name='category_points';
                    """)
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE tickets ADD COLUMN category_points INTEGER DEFAULT 0;")

                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='tickets' AND column_name='evidence_enabled';
                    """)
                    if not cursor.fetchone():
                        cursor.execute("ALTER TABLE tickets ADD COLUMN evidence_enabled INTEGER DEFAULT 1;")

                    for col, col_type in [("ticket_type", "VARCHAR(255) DEFAULT 'general'"), ("complaint_accepted", "INTEGER DEFAULT 0"), ("punished_user_id", "BIGINT DEFAULT 0"), ("timeout_duration", "INTEGER DEFAULT 0")]:
                        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='closure_info' AND column_name='{col}';")
                        if not cursor.fetchone():
                            cursor.execute(f"ALTER TABLE closure_info ADD COLUMN {col} {col_type};")
                except Exception as e:
                    sys.stderr.write(f"[DB_MIGRATION] Migration check failed: {e}\n")
            else:
                try:
                    cursor.execute("PRAGMA table_info(tickets)")
                    cols = [row[1] for row in cursor.fetchall()]
                    if "category_points" not in cols:
                        cursor.execute("ALTER TABLE tickets ADD COLUMN category_points INTEGER DEFAULT 0;")
                    if "evidence_enabled" not in cols:
                        cursor.execute("ALTER TABLE tickets ADD COLUMN evidence_enabled INTEGER DEFAULT 1;")

                    cursor.execute("PRAGMA table_info(closure_info)")
                    c_cols = [row[1] for row in cursor.fetchall()]
                    if "ticket_type" not in c_cols:
                        cursor.execute("ALTER TABLE closure_info ADD COLUMN ticket_type TEXT DEFAULT 'general';")
                    if "complaint_accepted" not in c_cols:
                        cursor.execute("ALTER TABLE closure_info ADD COLUMN complaint_accepted INTEGER DEFAULT 0;")
                    if "punished_user_id" not in c_cols:
                        cursor.execute("ALTER TABLE closure_info ADD COLUMN punished_user_id BIGINT DEFAULT 0;")
                    if "timeout_duration" not in c_cols:
                        cursor.execute("ALTER TABLE closure_info ADD COLUMN timeout_duration INTEGER DEFAULT 0;")
                except Exception as e:
                    sys.stderr.write(f"[DB_MIGRATION] SQLite migration check failed: {e}\n")

            conn.commit()
            sys.stderr.write(f"[DB_INFO] Database schema initialized successfully on backend: {backend}\n")
        except Exception as e:
            sys.stderr.write(f"[DB_INIT_ERROR] Database schema initialization failed: {e}\n")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # --- Panel Operations ---
    def save_panel(self, title: str, description: str, color: int, categories: list, **kwargs) -> int:
        panel_id = kwargs.get("panel_id")
        if panel_id:
            existing = self._run_query("SELECT id FROM panels WHERE id = ?", (panel_id,), fetch="one")
            if existing:
                self._run_query("""
                UPDATE panels
                SET title = ?, description = ?, color = ?, image_url = ?, banner_url = ?, thumbnail_url = ?, footer_text = ?, channel_id = ?, message_id = ?, categories_json = ?
                WHERE id = ?
                """, (
                    title, description, color,
                    kwargs.get("image_url"), kwargs.get("banner_url"), kwargs.get("thumbnail_url"), kwargs.get("footer_text"),
                    kwargs.get("channel_id"), kwargs.get("message_id"),
                    json.dumps(categories),
                    panel_id
                ))
            else:
                self._run_query("""
                INSERT INTO panels (id, title, description, color, image_url, banner_url, thumbnail_url, footer_text, channel_id, message_id, categories_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    panel_id, title, description, color,
                    kwargs.get("image_url"), kwargs.get("banner_url"), kwargs.get("thumbnail_url"), kwargs.get("footer_text"),
                    kwargs.get("channel_id"), kwargs.get("message_id"),
                    json.dumps(categories)
                ))
            return panel_id
        else:
            return self._run_query("""
            INSERT INTO panels (title, description, color, image_url, banner_url, thumbnail_url, footer_text, channel_id, message_id, categories_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, description, color,
                kwargs.get("image_url"), kwargs.get("banner_url"), kwargs.get("thumbnail_url"), kwargs.get("footer_text"),
                kwargs.get("channel_id"), kwargs.get("message_id"),
                json.dumps(categories)
            ), fetch="lastrowid") or 1

    def update_panel_message_id(self, panel_id: int, message_id: int):
        self._run_query("UPDATE panels SET message_id = ? WHERE id = ?", (message_id, panel_id))

    def get_panels(self) -> List[Dict[str, Any]]:
        rows = self._run_query("SELECT * FROM panels", fetch="all") or []
        for r in rows:
            if isinstance(r, dict):
                cat_json = r.get("categories_json")
                if cat_json:
                    try:
                        r["categories"] = json.loads(cat_json)
                    except Exception:
                        r["categories"] = []
                else:
                    r["categories"] = []
        return rows

    def get_panel_by_id(self, panel_id: int) -> Optional[Dict[str, Any]]:
        row = self._run_query("SELECT * FROM panels WHERE id = ?", (panel_id,), fetch="one")
        if not row and panel_id == 16:
            default_categories = [
                {
                    "id": "general",
                    "name": "الدعم الفني والتقني",
                    "description": "لفتح تذكرة دعم فني أو تقني مباشرة",
                    "emoji": "🛠️",
                    "questions": [
                        {"label": "السبب الرئيسي لفتح التذكرة", "required": True, "style": "short"},
                        {"label": "تفاصيل وتوضيح الطلب / المشكلة", "required": True, "style": "paragraph"}
                    ],
                    "welcome_msg": "مرحباً بك {user} في قسم {category}، يرجى الانتظار وتوضيح المشكلة."
                },
                {
                    "id": "sales",
                    "name": "الاستفسارات والمبيعات",
                    "description": "لأي استفسارات عامة أو مبيعات",
                    "emoji": "💰",
                    "questions": [
                        {"label": "الاستفسار أو الطلب", "required": True, "style": "paragraph"}
                    ],
                    "welcome_msg": "مرحباً بك {user} في قسم المبيعات والاستفسارات."
                }
            ]
            self.save_panel(
                title="لوحة الدعم الفني والتذاكر",
                description="مرحباً بك! يرجى اختيار القسم المناسب من القائمة أسفله لفتح تذكرة مباشرة مع فريق الدعم.",
                color=3447003,
                categories=default_categories,
                panel_id=16
            )
            row = self._run_query("SELECT * FROM panels WHERE id = ?", (16,), fetch="one")

        if row and isinstance(row, dict):
            cat_json = row.get("categories_json")
            if cat_json:
                try:
                    row["categories"] = json.loads(cat_json)
                except Exception:
                    row["categories"] = []
            else:
                row["categories"] = []
        return row

    def delete_panel(self, panel_id: int):
        self._run_query("DELETE FROM panels WHERE id = ?", (panel_id,))

    # --- Ticket Operations ---
    def create_ticket(self, guild_id: int, channel_id: int, user_id: int, panel_id: int, category_id: str, points: int = 0) -> int:
        ticket_id = self._run_query("""
        INSERT INTO tickets (guild_id, channel_id, user_id, panel_id, category_id, status, created_at, category_points)
        VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
        """, (guild_id, channel_id, user_id, panel_id, category_id, datetime.utcnow().isoformat(), points), fetch="lastrowid")
        
        if not ticket_id:
            res = self.get_ticket_by_channel(channel_id)
            if res:
                return res.get("id", 1)
            return 1
        return ticket_id

    def get_user_open_ticket(self, user_id: int, category_id: str) -> Optional[Dict[str, Any]]:
        return self._run_query("SELECT * FROM tickets WHERE user_id = ? AND category_id = ? AND status = 'open'", (user_id, category_id), fetch="one")

    def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        res = self._run_query("SELECT * FROM tickets WHERE id = ?", (ticket_id,), fetch="one")
        if not res:
            res = self._run_query("SELECT * FROM tickets WHERE id = ?", (str(ticket_id),), fetch="one")
        return res

    def get_ticket_by_channel(self, channel_id: Any) -> Optional[Dict[str, Any]]:
        if not channel_id:
            return None
        
        s_id = str(channel_id)
        try:
            i_id = int(channel_id)
        except Exception:
            i_id = 0

        res = self._run_query("SELECT * FROM tickets WHERE channel_id = ?", (i_id,), fetch="one")
        if not res:
            res = self._run_query("SELECT * FROM tickets WHERE channel_id = ?", (s_id,), fetch="one")
        return res

    def get_all_tickets(self) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM tickets ORDER BY id DESC", fetch="all") or []

    def update_ticket_status(self, channel_id: int, status: str):
        closed_at = datetime.utcnow().isoformat() if status == 'closed' else None
        self._run_query("UPDATE tickets SET status = ?, closed_at = COALESCE(?, closed_at) WHERE channel_id = ?", (status, closed_at, channel_id))

    def claim_ticket(self, channel_id: int, staff_id: Optional[int]):
        self._run_query("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?", (staff_id, channel_id))

    def set_first_response(self, channel_id: int):
        self._run_query("UPDATE tickets SET first_response_at = ? WHERE channel_id = ? AND first_response_at IS NULL", (datetime.utcnow().isoformat(), channel_id))

    def update_staff_reply(self, channel_id: int, timestamp: str):
        self._run_query("UPDATE tickets SET last_staff_message_at = ?, member_responded = 0 WHERE channel_id = ?", (timestamp, channel_id))

    def set_member_responded(self, channel_id: int):
        self._run_query("UPDATE tickets SET member_responded = 1, last_staff_message_at = NULL WHERE channel_id = ?", (channel_id,))

    def update_priority(self, channel_id: int, priority: str):
        self._run_query("UPDATE tickets SET priority = ? WHERE channel_id = ?", (priority, channel_id))

    def update_department(self, channel_id: int, department: str):
        self._run_query("UPDATE tickets SET department = ? WHERE channel_id = ?", (department, channel_id))

    def update_ticket_hidden(self, channel_id: int, is_hidden: int):
        self._run_query("UPDATE tickets SET is_hidden = ? WHERE channel_id = ?", (is_hidden, channel_id))

    def update_ticket_owner(self, channel_id: int, new_user_id: int):
        self._run_query("UPDATE tickets SET user_id = ? WHERE channel_id = ?", (new_user_id, channel_id))

    # --- Evidence Operations ---
    def add_evidence(self, ticket_id: int, channel_id: int, user_id: int, evidence_url: str, note: str = None) -> int:
        return self._run_query("""
        INSERT INTO ticket_evidence (ticket_id, channel_id, user_id, evidence_url, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, channel_id, user_id, evidence_url, note or "", datetime.utcnow().isoformat()), fetch="lastrowid") or 1

    def get_ticket_evidence(self, ticket_id: int) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM ticket_evidence WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,), fetch="all") or []

    def is_evidence_enabled(self, channel_id: int) -> bool:
        row = self._run_query("SELECT evidence_enabled FROM tickets WHERE channel_id = ?", (channel_id,), fetch="one")
        if row and isinstance(row, dict):
            val = row.get("evidence_enabled")
            return val != 0
        return True

    def toggle_ticket_evidence(self, channel_id: int) -> bool:
        current = self.is_evidence_enabled(channel_id)
        new_state = 0 if current else 1
        self._run_query("UPDATE tickets SET evidence_enabled = ? WHERE channel_id = ?", (new_state, channel_id))
        return bool(new_state)

    # --- Audit Logs ---
    def log_audit_event(self, ticket_id: int, action: str, executor_id: int, details: str = None):
        self._run_query("""
        INSERT INTO ticket_audit_logs (ticket_id, action, executor_id, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (ticket_id, action, executor_id, details or "", datetime.utcnow().isoformat()))

    def get_audit_logs(self, ticket_id: int) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM ticket_audit_logs WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,), fetch="all") or []

    # --- Guild Settings & Action Permissions ---
    def get_guild_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return self._run_query("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,), fetch="one")

    def get_guild_setting(self, guild_id: int, key: str, default: Any = None) -> Any:
        settings = self.get_guild_settings(guild_id)
        if settings and isinstance(settings, dict) and key in settings and settings[key] is not None:
            return settings[key]
        return default

    def set_guild_setting(self, guild_id: int, key: str, value: Any):
        self._run_query("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        try:
            self._run_query(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
        except Exception as e:
            sys.stderr.write(f"Error updating guild setting {key}: {e}\n")

    def get_action_permission(self, guild_id: int, action_name: str) -> Optional[Dict[str, Any]]:
        res = self._run_query("SELECT * FROM action_permissions WHERE guild_id = ? AND action_name = ?", (guild_id, action_name), fetch="one")
        if res and isinstance(res, dict):
            res["allowed_roles"] = json.loads(res.get("allowed_roles_json") or "[]")
        return res

    def set_action_permission(self, guild_id: int, action_name: str, min_rank: int = 10, allowed_roles: list = None):
        self._run_query("""
        INSERT OR REPLACE INTO action_permissions (guild_id, action_name, min_rank, allowed_roles_json)
        VALUES (?, ?, ?, ?)
        """, (guild_id, action_name, min_rank, json.dumps(allowed_roles or [])))

    # --- Rating & Notes ---
    def add_rating(self, ticket_id: int, user_id: int, staff_id: int, stars: int, feedback: str = None):
        self._run_query("""
        INSERT INTO ratings (ticket_id, user_id, staff_id, stars, feedback, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, user_id, staff_id, stars, feedback, datetime.utcnow().isoformat()))

    def has_ticket_been_rated(self, ticket_id: int) -> bool:
        res = self._run_query("SELECT 1 FROM ratings WHERE ticket_id = ?", (ticket_id,), fetch="one")
        return res is not None

    def save_closure_info(self, ticket_id: int, **kwargs):
        self._run_query("""
        INSERT INTO closure_info (
            ticket_id, user_handled, staff_punished, evidence_urls, punishment_type,
            staff_details, ticket_type, complaint_accepted, punished_user_id, timeout_duration, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (ticket_id) DO UPDATE SET
            user_handled = EXCLUDED.user_handled,
            staff_punished = EXCLUDED.staff_punished,
            evidence_urls = EXCLUDED.evidence_urls,
            punishment_type = EXCLUDED.punishment_type,
            staff_details = EXCLUDED.staff_details,
            ticket_type = EXCLUDED.ticket_type,
            complaint_accepted = EXCLUDED.complaint_accepted,
            punished_user_id = EXCLUDED.punished_user_id,
            timeout_duration = EXCLUDED.timeout_duration
        """, (
            ticket_id,
            kwargs.get("user_handled", 0),
            kwargs.get("staff_punished", 0),
            kwargs.get("evidence_urls", ""),
            kwargs.get("punishment_type", ""),
            kwargs.get("staff_details", ""),
            kwargs.get("ticket_type", "general"),
            kwargs.get("complaint_accepted", 0),
            kwargs.get("punished_user_id", 0),
            kwargs.get("timeout_duration", 0),
            datetime.utcnow().isoformat()
        ))

    def get_closure_info(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        return self._run_query("SELECT * FROM closure_info WHERE ticket_id = ?", (ticket_id,), fetch="one")

    # --- User Infractions & Warnings ---
    def add_infraction(self, guild_id: int, user_id: int, infraction_type: str, reason: str, duration_minutes: int, executor_id: int, ticket_id: int) -> int:
        return self._run_query("""
        INSERT INTO user_infractions (guild_id, user_id, infraction_type, reason, duration_minutes, executor_id, ticket_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (guild_id, user_id, infraction_type, reason, duration_minutes, executor_id, ticket_id, datetime.utcnow().isoformat()))

    def get_user_infractions(self, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        return self._run_query("""
        SELECT * FROM user_infractions WHERE guild_id = ? AND user_id = ? ORDER BY id DESC
        """, (guild_id, user_id), fetch="all") or []

    def get_user_infractions_summary(self, guild_id: int, user_id: int) -> Dict[str, int]:
        infractions = self.get_user_infractions(guild_id, user_id)
        verbal_count = sum(1 for i in infractions if i.get("infraction_type") == "verbal_warning")
        official_count = sum(1 for i in infractions if i.get("infraction_type") == "official_warning")
        timeout_count = sum(1 for i in infractions if i.get("infraction_type") == "timeout")
        return {
            "verbal_warnings": verbal_count,
            "official_warnings": official_count,
            "timeouts": timeout_count,
            "total": len(infractions)
        }

    def delete_rating_by_user_and_staff(self, user_id: int, staff_id: int, guild_id: int) -> int:
        ratings = self._run_query("""
        SELECT id FROM ratings WHERE user_id = ? AND staff_id = ?
        """, (user_id, staff_id), fetch="all") or []
        if not ratings:
            return 0
        
        count = len(ratings)
        self._run_query("DELETE FROM ratings WHERE user_id = ? AND staff_id = ?", (user_id, staff_id))
        self.recalculate_staff_rating_stats(guild_id, staff_id)
        return count

    def get_staff_ratings(self, staff_id: int) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM ratings WHERE staff_id = ? ORDER BY id DESC", (staff_id,), fetch="all") or []

    def get_all_ratings(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM ratings ORDER BY id DESC LIMIT ?", (limit,), fetch="all") or []

    def recalculate_staff_rating_stats(self, guild_id: int, staff_id: int):
        query = """
        SELECT COALESCE(SUM(r.stars), 0) as tot_stars, COUNT(r.id) as tot_ratings
        FROM ratings r
        JOIN tickets t ON r.ticket_id = t.id
        WHERE r.staff_id = ? AND t.guild_id = ?
        """
        res = self._run_query(query, (staff_id, guild_id), fetch="one")
        tot_stars = res["tot_stars"] if res and "tot_stars" in res else 0
        tot_ratings = res["tot_ratings"] if res and "tot_ratings" in res else 0
        
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, staff_id))
        self._run_query("UPDATE staff_stats SET total_stars = ?, total_ratings = ? WHERE guild_id = ? AND user_id = ?", (tot_stars, tot_ratings, guild_id, staff_id))

    def delete_rating(self, rating_id: int):
        rating = self._run_query("SELECT staff_id, ticket_id FROM ratings WHERE id = ?", (rating_id,), fetch="one")
        if not rating:
            return
        
        staff_id = rating.get("staff_id")
        ticket_id = rating.get("ticket_id")
        
        ticket = self._run_query("SELECT guild_id FROM tickets WHERE id = ?", (ticket_id,), fetch="one")
        guild_id = ticket.get("guild_id") if ticket else None
        
        self._run_query("DELETE FROM ratings WHERE id = ?", (rating_id,))
        if guild_id and staff_id:
            self.recalculate_staff_rating_stats(guild_id, staff_id)

    def delete_staff_ratings(self, staff_id: int):
        guilds = self._run_query("""
        SELECT DISTINCT t.guild_id 
        FROM ratings r 
        JOIN tickets t ON r.ticket_id = t.id 
        WHERE r.staff_id = ?
        """, (staff_id,), fetch="all") or []
        
        self._run_query("DELETE FROM ratings WHERE staff_id = ?", (staff_id,))
        for g in guilds:
            if isinstance(g, dict) and g.get("guild_id"):
                self.recalculate_staff_rating_stats(g["guild_id"], staff_id)

    def delete_all_ratings(self):
        self._run_query("DELETE FROM ratings")
        self._run_query("UPDATE staff_stats SET total_stars = 0, total_ratings = 0")

    def add_internal_note(self, ticket_id: int, author_id: int, content: str):
        self._run_query("""
        INSERT INTO internal_notes (ticket_id, author_id, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (ticket_id, author_id, content, datetime.utcnow().isoformat()))

    def get_internal_notes(self, ticket_id: int) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM internal_notes WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,), fetch="all") or []

    # --- Blacklist ---
    def is_blacklisted(self, user_id: int) -> bool:
        res = self._run_query("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,), fetch="one")
        return res is not None

    def blacklist_user(self, user_id: int, reason: str, added_by: int):
        self._run_query("INSERT OR REPLACE INTO blacklist (user_id, reason, added_by, created_at) VALUES (?, ?, ?, ?)",
                       (user_id, reason, added_by, datetime.utcnow().isoformat()))

    def unblacklist_user(self, user_id: int):
        self._run_query("DELETE FROM blacklist WHERE user_id = ?", (user_id,))

    def get_blacklisted_users(self) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM blacklist ORDER BY created_at DESC", fetch="all") or []

    # --- Stats & Analytics ---
    def get_statistics(self) -> Dict[str, Any]:
        row_tot = self._run_query("SELECT COUNT(*) as total FROM tickets", fetch="one")
        total = row_tot["total"] if row_tot and "total" in row_tot else 0

        row_open = self._run_query("SELECT COUNT(*) as open_cnt FROM tickets WHERE status = 'open'", fetch="one")
        open_cnt = row_open["open_cnt"] if row_open and "open_cnt" in row_open else 0

        row_closed = self._run_query("SELECT COUNT(*) as closed_cnt FROM tickets WHERE status = 'closed'", fetch="one")
        closed_cnt = row_closed["closed_cnt"] if row_closed and "closed_cnt" in row_closed else 0

        row_rating = self._run_query("SELECT AVG(stars) as avg_rating FROM ratings", fetch="one")
        avg_rating = round(row_rating["avg_rating"], 2) if row_rating and row_rating.get("avg_rating") else 0.0

        top_staff = self._run_query("""
        SELECT staff_id, AVG(stars) as avg_stars, COUNT(*) as total_ratings 
        FROM ratings GROUP BY staff_id ORDER BY avg_stars DESC LIMIT 5
        """, fetch="all") or []

        return {
            "total_tickets": total,
            "open_tickets": open_cnt,
            "closed_tickets": closed_cnt,
            "average_rating": avg_rating,
            "top_staff": top_staff
        }

    # --- Wizard Sessions (Setup Resume) ---
    def save_wizard_session(self, user_id: int, state_dict: Dict[str, Any]):
        self._run_query(
            "INSERT OR REPLACE INTO wizard_sessions (user_id, state_json, updated_at) VALUES (?, ?, ?)",
            (user_id, json.dumps(state_dict), datetime.utcnow().isoformat())
        )

    def get_wizard_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self._run_query("SELECT state_json FROM wizard_sessions WHERE user_id = ?", (user_id,), fetch="one")
        if row and isinstance(row, dict) and row.get("state_json"):
            try:
                return json.loads(row["state_json"])
            except Exception:
                return None
        return None

    def delete_wizard_session(self, user_id: int):
        self._run_query("DELETE FROM wizard_sessions WHERE user_id = ?", (user_id,))

    # --- Staff Stats & Points ---
    def get_staff_stats(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        row = self._run_query("SELECT * FROM staff_stats WHERE guild_id = ? AND user_id = ?", (guild_id, user_id), fetch="one")
        
        rating_data = self._run_query("""
            SELECT COALESCE(SUM(r.stars), 0) as tot_stars, COUNT(r.id) as tot_ratings
            FROM ratings r
            JOIN tickets t ON r.ticket_id = t.id
            WHERE r.staff_id = ? AND t.guild_id = ?
        """, (user_id, guild_id), fetch="one")
        
        tot_stars = rating_data["tot_stars"] if rating_data and "tot_stars" in rating_data else 0
        tot_ratings = rating_data["tot_ratings"] if rating_data and "tot_ratings" in rating_data else 0
        
        if row and isinstance(row, dict):
            res = dict(row)
            res["total_stars"] = tot_stars
            res["total_ratings"] = tot_ratings
            return res
        else:
            if tot_ratings > 0:
                return {
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "points": 0,
                    "tickets_handled": 0,
                    "total_stars": tot_stars,
                    "total_ratings": tot_ratings
                }
        return None

    def get_all_staff_stats(self, guild_id: int) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM staff_stats WHERE guild_id = ? ORDER BY points DESC", (guild_id,), fetch="all") or []

    def update_staff_points(self, guild_id: int, user_id: int, points_delta: int):
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        self._run_query("UPDATE staff_stats SET points = points + ? WHERE guild_id = ? AND user_id = ?", (points_delta, guild_id, user_id))

    def increment_staff_tickets(self, guild_id: int, user_id: int):
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        self._run_query("UPDATE staff_stats SET tickets_handled = tickets_handled + 1 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    def add_staff_rating_stat(self, guild_id: int, user_id: int, stars: int):
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        self._run_query("UPDATE staff_stats SET total_stars = total_stars + ?, total_ratings = total_ratings + 1 WHERE guild_id = ? AND user_id = ?", (stars, guild_id, user_id))

    def reset_staff_points(self, guild_id: int, user_id: Optional[int] = None):
        if user_id:
            self._run_query("UPDATE staff_stats SET points = 0 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        else:
            self._run_query("UPDATE staff_stats SET points = 0 WHERE guild_id = ?", (guild_id,))

    def set_staff_points(self, guild_id: int, user_id: int, points: int):
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        self._run_query("UPDATE staff_stats SET points = ? WHERE guild_id = ? AND user_id = ?", (points, guild_id, user_id))

    # --- Settings Audit Logs ---
    def log_settings_change(self, guild_id: int, executor_id: int, action: str, details: str = None):
        self._run_query(
            "INSERT INTO settings_audit_logs (guild_id, executor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, executor_id, action, details or "", datetime.utcnow().isoformat())
        )

    def get_settings_audit_logs(self, guild_id: int, limit: int = 15) -> List[Dict[str, Any]]:
        return self._run_query(
            "SELECT * FROM settings_audit_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
            (guild_id, limit), fetch="all"
        ) or []

    # --- Import / Export Configuration (JSON) ---
    def export_guild_config(self, guild_id: int) -> Dict[str, Any]:
        settings = self.get_guild_settings(guild_id) or {}
        panels = self.get_panels() or []
        return {
            "version": "2.0",
            "exported_at": datetime.utcnow().isoformat(),
            "guild_id": guild_id,
            "settings": settings,
            "panels": panels
        }

    def import_guild_config(self, guild_id: int, data: Dict[str, Any], executor_id: int):
        settings = data.get("settings", {})
        if settings:
            self._run_query("""
            INSERT INTO guild_settings 
            (guild_id, log_channel_id, transcript_channel_id, category_id, owner_role_id, admin_role_id, support_manager_role_id, senior_support_role_id, support_role_id, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET
                log_channel_id = EXCLUDED.log_channel_id,
                transcript_channel_id = EXCLUDED.transcript_channel_id,
                category_id = EXCLUDED.category_id,
                owner_role_id = EXCLUDED.owner_role_id,
                admin_role_id = EXCLUDED.admin_role_id,
                support_manager_role_id = EXCLUDED.support_manager_role_id,
                senior_support_role_id = EXCLUDED.senior_support_role_id,
                support_role_id = EXCLUDED.support_role_id,
                language = EXCLUDED.language
            """, (
                guild_id,
                settings.get("log_channel_id"),
                settings.get("transcript_channel_id"),
                settings.get("category_id"),
                settings.get("owner_role_id"),
                settings.get("admin_role_id"),
                settings.get("support_manager_role_id"),
                settings.get("senior_support_role_id"),
                settings.get("support_role_id"),
                settings.get("language", "ar")
            ))

        panels = data.get("panels", [])
        for p in panels:
            p_id = p.get("id")
            if p_id:
                self._run_query("DELETE FROM panels WHERE id = ?", (p_id,))
                self._run_query("""
                INSERT INTO panels (id, title, description, color, image_url, banner_url, thumbnail_url, footer_text, channel_id, message_id, categories_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p_id,
                    p.get("title", "Imported Panel"),
                    p.get("description", "Imported Panel Description"),
                    p.get("color", 3447003),
                    p.get("image_url"),
                    p.get("banner_url"),
                    p.get("thumbnail_url"),
                    p.get("footer_text"),
                    p.get("channel_id"),
                    p.get("message_id"),
                    json.dumps(p.get("categories", []))
                ))
            else:
                self._run_query("""
                INSERT INTO panels (title, description, color, image_url, banner_url, thumbnail_url, footer_text, channel_id, message_id, categories_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.get("title", "Imported Panel"),
                    p.get("description", "Imported Panel Description"),
                    p.get("color", 3447003),
                    p.get("image_url"),
                    p.get("banner_url"),
                    p.get("thumbnail_url"),
                    p.get("footer_text"),
                    p.get("channel_id"),
                    p.get("message_id"),
                    json.dumps(p.get("categories", []))
                ))

        self.log_settings_change(guild_id, executor_id, "IMPORT_CONFIG", f"Imported {len(panels)} panels and guild settings")

db = DatabaseManager()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)
    
    cmd = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    
    res = None
    if cmd == "get_bot_token":
        res = {"token": db.get_guild_setting(0, "bot_token", "")}
    elif cmd == "save_bot_token":
        db.set_guild_setting(0, "bot_token", args.get("token", ""))
        res = {"success": True}
    elif cmd == "get_settings":
        res = db.get_guild_settings(args.get("guild_id", 0)) or {}
    elif cmd == "save_settings":
        gid = args.get("guild_id", 0)
        for k, v in args.items():
            if k != "guild_id":
                db.set_guild_setting(gid, k, v)
        res = {"success": True}
    elif cmd == "get_panels":
        res = db.get_panels()
    elif cmd == "save_panel":
        pid = db.save_panel(
            title=args.get("title", "New Panel"),
            description=args.get("description", ""),
            color=args.get("color", 3447003),
            categories=args.get("categories", []),
            image_url=args.get("image_url"),
            banner_url=args.get("banner_url"),
            thumbnail_url=args.get("thumbnail_url"),
            footer_text=args.get("footer_text"),
            channel_id=args.get("channel_id"),
            message_id=args.get("message_id"),
            panel_id=args.get("id")
        )
        res = {"id": pid}
    elif cmd == "delete_panel":
        db.delete_panel(args.get("id"))
        res = {"success": True}
    elif cmd == "get_blacklist":
        res = db.get_blacklisted_users()
    elif cmd == "add_blacklist":
        db.blacklist_user(args.get("user_id"), args.get("reason", "No reason"), args.get("added_by", 0))
        res = {"success": True}
    elif cmd == "remove_blacklist":
        db.unblacklist_user(args.get("user_id"))
        res = {"success": True}
    elif cmd == "get_guilds":
        res = []
    elif cmd == "sync_commands":
        res = {"success": True}
    elif cmd == "get_staff_stats":
        res = db.get_staff_stats(args.get("guild_id"), args.get("user_id"))
    elif cmd == "get_all_staff_stats":
        res = db.get_all_staff_stats(args.get("guild_id"))
    elif cmd == "update_points":
        db.update_staff_points(args.get("guild_id"), args.get("user_id"), args.get("delta", 0))
        res = {"success": True}
    elif cmd == "reset_points":
        db.reset_staff_points(args.get("guild_id"), args.get("user_id"))
        res = {"success": True}
    
    print(json.dumps(res))

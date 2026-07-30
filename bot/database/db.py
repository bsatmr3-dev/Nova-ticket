import sqlite3
import json
import os
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if not db_path:
            try:
                from bot.config.settings import Config
                self.db_path = Config.DATABASE_PATH
            except ImportError:
                self.db_path = "database/tickets.db"
        else:
            self.db_path = db_path
        
        # Radical fix: ensure database path is absolute relative to bot root
        if not os.path.isabs(self.db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, self.db_path)
            
        db_url = os.environ.get("DATABASE_URL")
        self.is_postgres = HAS_POSTGRES and (db_url is not None and len(db_url.strip()) > 0)
        
        if not self.is_postgres:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
        try:
            self._init_db()
        except Exception as e:
            sys.stderr.write(f"[DB_INIT_ERROR] Database initialization failed: {e}. Falling back to SQLite...\n")
            self.is_postgres = False
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._init_db()

    def _get_connection(self):
        if self.is_postgres:
            db_url = os.environ.get("DATABASE_URL")
            try:
                if db_url and len(db_url.strip()) > 0:
                    clean_url = db_url.strip()
                    if clean_url.startswith("postgres://"):
                        clean_url = clean_url.replace("postgres://", "postgresql://", 1)
                    conn = psycopg2.connect(clean_url, connect_timeout=10)
                    return conn
                else:
                    raise ValueError("DATABASE_URL environment variable is empty or not set.")
            except Exception as e:
                sys.stderr.write(f"Error connecting to Supabase PostgreSQL via DATABASE_URL: {e}\n")
                self.is_postgres = False
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                sys.stderr.write(f"[DB_CONNECTION] Fallback to SQLite DB file: {self.db_path} (Absolute: {os.path.abspath(self.db_path)})\n")
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                return conn
        else:
            # SQLite connection
            sys.stderr.write(f"[DB_CONNECTION] Connecting to SQLite DB file: {self.db_path} (Absolute: {os.path.abspath(self.db_path)})\n")
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _execute(self, cursor, query, params=None):
        if self.is_postgres:
            # Convert ? placeholders to %s for PostgreSQL
            query = query.replace("?", "%s")
            # Convert INSERT OR IGNORE / REPLACE
            if "INSERT OR IGNORE" in query:
                # This is a bit complex for a regex, but we can do a simple swap for specific cases
                query = query.replace("INSERT OR IGNORE INTO", "INSERT INTO")
                # We'd need ON CONFLICT DO NOTHING for real ignore, but let's stick to basic queries for now
                # Or handle specifically
            elif "INSERT OR REPLACE" in query:
                query = query.replace("INSERT OR REPLACE INTO", "INSERT INTO")
                # We'd need ON CONFLICT DO UPDATE
            
        cursor.execute(query, params or ())

    def _init_db(self):
        # We'll use a more robust approach for init
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Use appropriate SERIAL / AUTOINCREMENT
            pk_type = "SERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
            text_type = "TEXT"
            int_type = "INTEGER"
            
            # Tables
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
                    category_points {int_type} DEFAULT 0
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
                )"""
            ]
            
            for q in queries:
                cursor.execute(q)
            
            # Self-healing migration for tickets.category_points column
            if self.is_postgres:
                try:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='tickets' AND column_name='category_points';
                    """)
                    if not cursor.fetchone():
                        sys.stderr.write("[DB_MIGRATION] Adding missing column 'category_points' to PostgreSQL table 'tickets'\n")
                        cursor.execute("ALTER TABLE tickets ADD COLUMN category_points INTEGER DEFAULT 0;")
                except Exception as e:
                    sys.stderr.write(f"[DB_MIGRATION] PostgreSQL migration check failed: {e}\n")
            else:
                try:
                    cursor.execute("PRAGMA table_info(tickets)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if "category_points" not in columns:
                        sys.stderr.write("[DB_MIGRATION] Adding missing column 'category_points' to SQLite table 'tickets'\n")
                        cursor.execute("ALTER TABLE tickets ADD COLUMN category_points INTEGER DEFAULT 0")
                except Exception as e:
                    sys.stderr.write(f"[DB_MIGRATION] SQLite migration check failed: {e}\n")

            # Indexes
            if not self.is_postgres:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id, status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_staff ON ratings(staff_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_ticket ON internal_notes(ticket_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ticket ON ticket_audit_logs(ticket_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_stats ON staff_stats(guild_id, user_id)")

            # Self-healing migration to synchronize staff rating statistics
            try:
                cursor.execute("SELECT guild_id, user_id FROM staff_stats")
                rows = cursor.fetchall()
                for row in rows:
                    try:
                        g_id = row[0]
                        u_id = row[1]
                    except Exception:
                        g_id = row["guild_id"]
                        u_id = row["user_id"]

                    cursor.execute("""
                        SELECT COALESCE(SUM(r.stars), 0) as tot_stars, COUNT(r.id) as tot_ratings
                        FROM ratings r
                        JOIN tickets t ON r.ticket_id = t.id
                        WHERE r.staff_id = ? AND t.guild_id = ?
                    """ if not self.is_postgres else """
                        SELECT COALESCE(SUM(r.stars), 0) as tot_stars, COUNT(r.id) as tot_ratings
                        FROM ratings r
                        JOIN tickets t ON r.ticket_id = t.id
                        WHERE r.staff_id = %s AND t.guild_id = %s
                    """, (u_id, g_id))

                    res = cursor.fetchone()
                    tot_stars = 0
                    tot_ratings = 0
                    if res:
                        try:
                            tot_stars = res[0]
                            tot_ratings = res[1]
                        except Exception:
                            tot_stars = res.get("tot_stars", 0)
                            tot_ratings = res.get("tot_ratings", 0)

                    cursor.execute("""
                        UPDATE staff_stats SET total_stars = ?, total_ratings = ? WHERE guild_id = ? AND user_id = ?
                    """ if not self.is_postgres else """
                        UPDATE staff_stats SET total_stars = %s, total_ratings = %s WHERE guild_id = %s AND user_id = %s
                    """, (tot_stars, tot_ratings, g_id, u_id))
                sys.stderr.write("[DB_MIGRATION] Recalculated and synchronized all staff ratings stats successfully.\n")
            except Exception as e:
                sys.stderr.write(f"[DB_MIGRATION] Staff ratings stats synchronization failed: {e}\n")

            conn.commit()
        except Exception as e:
            print(f"Database Init Error: {e}")
            raise e
        finally:
            conn.close()

    def _get_row(self, row):
        if self.is_postgres:
            # RealDictCursor makes it a dict
            return row
        return dict(row)

    # --- Generic Wrapper ---
    def _run_query(self, query: str, params: tuple = (), fetch: str = None):
        conn = self._get_connection()
        try:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                query = query.replace("?", "%s")
                # Handle specific SQL differences
                if "INSERT OR IGNORE" in query:
                    # Very basic translation, might need refinement
                    query = query.replace("INSERT OR IGNORE INTO", "INSERT INTO")
                    if "guild_settings" in query:
                        query += " ON CONFLICT (guild_id) DO NOTHING"
                    elif "blacklist" in query:
                        query += " ON CONFLICT (user_id) DO NOTHING"
                    elif "staff_stats" in query:
                        query += " ON CONFLICT (guild_id, user_id) DO NOTHING"
                elif "INSERT OR REPLACE" in query:
                    query = query.replace("INSERT OR REPLACE INTO", "INSERT INTO")
                    if "guild_settings" in query:
                        query += " ON CONFLICT (guild_id) DO UPDATE SET guild_id = EXCLUDED.guild_id"
                    elif "blacklist" in query:
                        query += " ON CONFLICT (user_id) DO UPDATE SET reason = EXCLUDED.reason, added_by = EXCLUDED.added_by, created_at = EXCLUDED.created_at"
                    elif "wizard_sessions" in query:
                        query += " ON CONFLICT (user_id) DO UPDATE SET state_json = EXCLUDED.state_json, updated_at = EXCLUDED.updated_at"
                    elif "action_permissions" in query:
                        query += " ON CONFLICT (guild_id, action_name) DO UPDATE SET min_rank = EXCLUDED.min_rank, allowed_roles_json = EXCLUDED.allowed_roles_json"
                
                # Handle COALESCE difference for NULL in sqlite vs postgres
                # SQLite: COALESCE(?, closed_at) -> Postgres needs casting sometimes or works fine
            else:
                cursor = conn.cursor()
            
            cursor.execute(query, params)
            
            result = None
            if fetch == "one":
                row = cursor.fetchone()
                result = self._get_row(row) if row else None
            elif fetch == "all":
                rows = cursor.fetchall()
                result = [self._get_row(r) for r in rows]
            elif fetch == "lastrowid":
                if self.is_postgres:
                    # Postgres doesn't have lastrowid on cursor easily, often uses RETURNING
                    # But for simple insert, we can try
                    try:
                        cursor.execute("SELECT lastval()")
                        result = cursor.fetchone()['lastval']
                    except:
                        result = 0
                else:
                    result = cursor.lastrowid
            
            conn.commit()
            return result
        except Exception as e:
            print(f"Query Error: {e} | Query: {query}")
            return None
        finally:
            conn.close()

    # --- Panel Operations ---
    def save_panel(self, title: str, description: str, color: int, categories: list, **kwargs) -> int:
        panel_id = kwargs.get("panel_id")
        if panel_id:
            # Check if panel with this ID exists in the database
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
            ), fetch="lastrowid")

    def update_panel_message_id(self, panel_id: int, message_id: int):
        self._run_query("UPDATE panels SET message_id = ? WHERE id = ?", (message_id, panel_id))

    def get_panels(self) -> List[Dict[str, Any]]:
        rows = self._run_query("SELECT * FROM panels", fetch="all") or []
        for r in rows:
            r["categories"] = json.loads(r["categories_json"]) if r.get("categories_json") else []
        return rows

    def get_panel_by_id(self, panel_id: int) -> Optional[Dict[str, Any]]:
        row = self._run_query("SELECT * FROM panels WHERE id = ?", (panel_id,), fetch="one")
        if not row and panel_id == 16:
            # Auto-create default panel 16 for Postgres/SQLite migration fallback
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

        if row:
            row["categories"] = json.loads(row["categories_json"]) if row.get("categories_json") else []
        return row

    def delete_panel(self, panel_id: int):
        self._run_query("DELETE FROM panels WHERE id = ?", (panel_id,))

    # --- Ticket Operations ---
    def create_ticket(self, guild_id: int, channel_id: int, user_id: int, panel_id: int, category_id: str, points: int = 0) -> int:
        sys.stderr.write(f"[TICKET_LIFECYCLE] [INSERT_START] Attempting to INSERT ticket: guild_id={guild_id}, channel_id={channel_id}, user_id={user_id}, panel_id={panel_id}, category_id={category_id}\n")
        
        ticket_id = self._run_query("""
        INSERT INTO tickets (guild_id, channel_id, user_id, panel_id, category_id, status, created_at, category_points)
        VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
        """, (guild_id, channel_id, user_id, panel_id, category_id, datetime.utcnow().isoformat(), points), fetch="lastrowid")
        
        if ticket_id:
            sys.stderr.write(f"[TICKET_LIFECYCLE] [INSERT_SUCCESS] Ticket created successfully: ticket_id={ticket_id}, channel_id={channel_id}\n")
            # Verify the record actually exists in the database immediately after insert
            verify_res = self.get_ticket_by_channel(channel_id)
            if verify_res:
                sys.stderr.write(f"[TICKET_LIFECYCLE] [INSERT_VERIFIED] Verified newly created ticket in database: ticket_id={verify_res.get('id')}, channel_id={verify_res.get('channel_id')}\n")
            else:
                sys.stderr.write(f"[TICKET_LIFECYCLE] [INSERT_VERIFY_FAILED] CRITICAL ERROR: Ticket was inserted with ticket_id={ticket_id}, but verification lookup returned None immediately!\n")
        else:
            sys.stderr.write(f"[TICKET_LIFECYCLE] [INSERT_FAILED] CRITICAL ERROR: Insert failed, _run_query returned None for channel_id={channel_id}\n")
            raise Exception(f"Failed to save ticket to database: channel_id={channel_id}")
            
        return ticket_id

    def get_user_open_ticket(self, user_id: int, category_id: str) -> Optional[Dict[str, Any]]:
        return self._run_query("SELECT * FROM tickets WHERE user_id = ? AND category_id = ? AND status = 'open'", (user_id, category_id), fetch="one")

    def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        # Ensure lookup works for both string and int IDs
        res = self._run_query("SELECT * FROM tickets WHERE id = ?", (ticket_id,), fetch="one")
        if not res:
            res = self._run_query("SELECT * FROM tickets WHERE id = ?", (str(ticket_id),), fetch="one")
        return res

    def get_ticket_by_channel(self, channel_id: Any) -> Optional[Dict[str, Any]]:
        if not channel_id:
            sys.stderr.write("[TICKET_LIFECYCLE] [QUERY_ERROR] get_ticket_by_channel called with empty channel_id\n")
            return None
        
        # Convert to string and int versions
        s_id = str(channel_id)
        try:
            i_id = int(channel_id)
        except Exception as err:
            sys.stderr.write(f"[TICKET_LIFECYCLE] [QUERY_ERROR] Failed to cast channel_id to int: {err}\n")
            i_id = 0

        # Print the exact query and used channel_id as requested
        query = "SELECT * FROM tickets WHERE channel_id = ? OR channel_id = ? OR CAST(channel_id AS TEXT) = ?"
        sys.stderr.write(f"[TICKET_LIFECYCLE] [QUERY_BY_CHANNEL] Executing query: '{query}' with parameters: i_id={i_id} ({type(i_id).__name__}), s_id='{s_id}' ({type(s_id).__name__})\n")
        
        res = self._run_query(query, (i_id, s_id, s_id), fetch="one")
        
        if not res and i_id == 0:
            query2 = "SELECT * FROM tickets WHERE CAST(channel_id AS TEXT) = ?"
            sys.stderr.write(f"[TICKET_LIFECYCLE] [QUERY_BY_CHANNEL_FALLBACK] Executing fallback query: '{query2}' with parameter: '{s_id}'\n")
            res = self._run_query(query2, (s_id,), fetch="one")
            
        if res:
            sys.stderr.write(f"[TICKET_LIFECYCLE] [QUERY_SUCCESS] Succeeded looking up ticket! Found: ticket_id={res.get('id')}, channel_id={res.get('channel_id')}, status={res.get('status')}\n")
        else:
            sys.stderr.write(f"[TICKET_LIFECYCLE] [QUERY_NOT_FOUND] Warning: No ticket record found in database for channel_id={channel_id}\n")
            
        return res

    def get_all_tickets(self) -> List[Dict[str, Any]]:
        return self._run_query("SELECT * FROM tickets ORDER BY id DESC", fetch="all") or []

    def update_ticket_status(self, channel_id: int, status: str):
        closed_at = datetime.utcnow().isoformat() if status == 'closed' else None
        if self.is_postgres:
            self._run_query("UPDATE tickets SET status = ?, closed_at = COALESCE(%s, closed_at) WHERE channel_id = ?", (status, closed_at, channel_id))
        else:
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
        if settings and key in settings and settings[key] is not None:
            return settings[key]
        return default

    def set_guild_setting(self, guild_id: int, key: str, value: Any):
        self._run_query("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        try:
            self._run_query(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
        except Exception as e:
            if not self.is_postgres:
                try:
                    self._run_query(f"ALTER TABLE guild_settings ADD COLUMN {key} TEXT")
                    self._run_query(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
                except: pass
            print(f"Error updating guild setting {key}: {e}")

    def get_action_permission(self, guild_id: int, action_name: str) -> Optional[Dict[str, Any]]:
        res = self._run_query("SELECT * FROM action_permissions WHERE guild_id = ? AND action_name = ?", (guild_id, action_name), fetch="one")
        if res:
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
        tot_stars = res["tot_stars"] if res else 0
        tot_ratings = res["tot_ratings"] if res else 0
        
        # Update staff_stats
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, staff_id))
        if self.is_postgres:
            self._run_query("UPDATE staff_stats SET total_stars = %s, total_ratings = %s WHERE guild_id = %s AND user_id = %s", (tot_stars, tot_ratings, guild_id, staff_id))
        else:
            self._run_query("UPDATE staff_stats SET total_stars = ?, total_ratings = ? WHERE guild_id = ? AND user_id = ?", (tot_stars, tot_ratings, guild_id, staff_id))

    def delete_rating(self, rating_id: int):
        # 1. Fetch rating to get staff_id and ticket_id
        rating = self._run_query("SELECT staff_id, ticket_id FROM ratings WHERE id = ?", (rating_id,), fetch="one")
        if not rating:
            return
        
        staff_id = rating["staff_id"]
        ticket_id = rating["ticket_id"]
        
        # 2. Fetch guild_id from ticket
        ticket = self._run_query("SELECT guild_id FROM tickets WHERE id = ?", (ticket_id,), fetch="one")
        guild_id = ticket["guild_id"] if ticket else None
        
        # 3. Delete the rating
        self._run_query("DELETE FROM ratings WHERE id = ?", (rating_id,))
        
        # 4. Recalculate stats
        if guild_id and staff_id:
            self.recalculate_staff_rating_stats(guild_id, staff_id)

    def delete_staff_ratings(self, staff_id: int):
        # Get unique guild_ids for this staff's ratings before deleting
        guilds = self._run_query("""
        SELECT DISTINCT t.guild_id 
        FROM ratings r 
        JOIN tickets t ON r.ticket_id = t.id 
        WHERE r.staff_id = ?
        """, (staff_id,), fetch="all") or []
        
        self._run_query("DELETE FROM ratings WHERE staff_id = ?", (staff_id,))
        
        for g in guilds:
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
        total = self._run_query("SELECT COUNT(*) as total FROM tickets", fetch="one")["total"]
        open_cnt = self._run_query("SELECT COUNT(*) as open_cnt FROM tickets WHERE status = 'open'", fetch="one")["open_cnt"]
        closed_cnt = self._run_query("SELECT COUNT(*) as closed_cnt FROM tickets WHERE status = 'closed'", fetch="one")["closed_cnt"]
        
        row_rating = self._run_query("SELECT AVG(stars) as avg_rating FROM ratings", fetch="one")
        avg_rating = round(row_rating["avg_rating"], 2) if row_rating and row_rating["avg_rating"] else 0.0

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
        if row and row["state_json"]:
            return json.loads(row["state_json"])
        return None

    def delete_wizard_session(self, user_id: int):
        self._run_query("DELETE FROM wizard_sessions WHERE user_id = ?", (user_id,))

    # --- Staff Stats & Points ---
    def get_staff_stats(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        row = self._run_query("SELECT * FROM staff_stats WHERE guild_id = ? AND user_id = ?", (guild_id, user_id), fetch="one")
        
        # Dynamically calculate total_stars and total_ratings from ratings table to be 100% accurate
        rating_data = self._run_query("""
            SELECT COALESCE(SUM(r.stars), 0) as tot_stars, COUNT(r.id) as tot_ratings
            FROM ratings r
            JOIN tickets t ON r.ticket_id = t.id
            WHERE r.staff_id = ? AND t.guild_id = ?
        """, (user_id, guild_id), fetch="one")
        
        tot_stars = rating_data["tot_stars"] if rating_data else 0
        tot_ratings = rating_data["tot_ratings"] if rating_data else 0
        
        if row:
            res = dict(row)
            res["total_stars"] = tot_stars
            res["total_ratings"] = tot_ratings
            return res
        else:
            # If they don't have stats yet but they have ratings, return a default dictionary
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
        if self.is_postgres:
            self._run_query("UPDATE staff_stats SET points = points + %s WHERE guild_id = %s AND user_id = %s", (points_delta, guild_id, user_id))
        else:
            self._run_query("UPDATE staff_stats SET points = points + ? WHERE guild_id = ? AND user_id = ?", (points_delta, guild_id, user_id))

    def increment_staff_tickets(self, guild_id: int, user_id: int):
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        if self.is_postgres:
            self._run_query("UPDATE staff_stats SET tickets_handled = tickets_handled + 1 WHERE guild_id = %s AND user_id = %s", (guild_id, user_id))
        else:
            self._run_query("UPDATE staff_stats SET tickets_handled = tickets_handled + 1 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

    def add_staff_rating_stat(self, guild_id: int, user_id: int, stars: int):
        self._run_query("INSERT OR IGNORE INTO staff_stats (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        if self.is_postgres:
            self._run_query("UPDATE staff_stats SET total_stars = total_stars + %s, total_ratings = total_ratings + 1 WHERE guild_id = %s AND user_id = %s", (stars, guild_id, user_id))
        else:
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
            # We can't easily do INSERT OR REPLACE with all columns in a generic way for Postgres here
            # but we can try basic insert
            self._run_query("""
            INSERT INTO guild_settings 
            (guild_id, log_channel_id, transcript_channel_id, category_id, owner_role_id, admin_role_id, support_manager_role_id, senior_support_role_id, support_role_id, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                # First delete existing panel with that ID to avoid conflict
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
        # Mock or real implementation for guilds
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

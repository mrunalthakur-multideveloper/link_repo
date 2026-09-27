"""Neon PostgreSQL database handler for LinkedIn scraper.
Primary backend: Neon Serverless PostgreSQL (via psycopg2 / DATABASE_URL or NEON_DATABASE_URL)
Fallback backend: Supabase REST API (via requests / SUPABASE_URL + SUPABASE_KEY)
"""

import os
import sys
import time
import json
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Load environment variables
load_dotenv()


class NeonDatabaseManager:
    """Manages all Neon PostgreSQL database operations with automatic table creation,
    connection pooling resilience, and automatic checkpointing."""

    def __init__(self):
        # Database URL for Neon PostgreSQL
        raw_url = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")
        if raw_url:
            raw_url = raw_url.strip()
            # Ensure sslmode=require for Neon DB connections if not present
            if "neon.tech" in raw_url and "sslmode=" not in raw_url:
                separator = "&" if "?" in raw_url else "?"
                raw_url = f"{raw_url}{separator}sslmode=require"
        self.connection_string = raw_url

        # Target Table (where scraped jobs are saved)
        self.table_name = os.getenv("NEON_TABLE") or os.getenv("TARGET_TABLE") or os.getenv("SUPABASE_TABLE", "links")
        self.progress_table = os.getenv("PROGRESS_TABLE", "scraper_progress_repo1")
        self.active_clients_table = os.getenv("ACTIVE_CLIENTS_TABLE", "active_clients")

        # ── ApplyUS CRM Active Clients Configuration ──
        self.crm_backend_url = (os.getenv("CRM_BACKEND_URL") or "https://api.applyus.org").strip().rstrip("/")
        self.crm_endpoint_path = (os.getenv("CRM_ENDPOINT_PATH") or "/api/clients/active").strip()
        if not self.crm_endpoint_path.startswith("/"):
            self.crm_endpoint_path = "/" + self.crm_endpoint_path
        self.crm_api_key = (os.getenv("INTERNAL_SERVICE_API_KEY") or os.getenv("CRM_API_KEY") or "applservice_key_2026").strip()
        self.active_clients: List[Dict[str, Any]] = []

        self.initialized = False
        self.offline_mode = False
        self.backend_type = "offline"  # "neon_postgres" | "supabase_rest" | "offline"

        # Postgres connection
        self.conn = None

        # ── Fallback Supabase REST API credentials (if user still has them configured) ──
        self.supabase_url = os.getenv("TARGET_SUPABASE_URL") or os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("TARGET_SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
        self.rest_headers = {}
        if self.supabase_key:
            self.rest_headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
        if self.supabase_url:
            self.supabase_url = self.supabase_url.strip().rstrip("/")
            if not self.supabase_url.startswith("http"):
                self.supabase_url = f"https://{self.supabase_url}"

        # ── Source Database (Where onboarding_submissions table lives) ──
        self.source_database_url = os.getenv("SOURCE_DATABASE_URL")
        self.source_supabase_url = os.getenv("SOURCE_SUPABASE_URL") or self.supabase_url
        self.source_supabase_key = os.getenv("SOURCE_SUPABASE_KEY") or self.supabase_key
        self.source_table = os.getenv("SOURCE_TABLE", "onboarding_submissions")

        self.source_rest_headers = {}
        if self.source_supabase_key:
            self.source_rest_headers = {
                "apikey": self.source_supabase_key,
                "Authorization": f"Bearer {self.source_supabase_key}",
                "Content-Type": "application/json",
            }
        if self.source_supabase_url:
            self.source_supabase_url = self.source_supabase_url.strip().rstrip("/")
            if not self.source_supabase_url.startswith("http"):
                self.source_supabase_url = f"https://{self.source_supabase_url}"

    def initialize(self) -> bool:
        """Initialize connection to Neon PostgreSQL (or fallback to Supabase REST)."""
        if self.offline_mode:
            print("⚠️ Running in offline mode (database disabled)")
            return False

        # ── Mode 1: Neon PostgreSQL Connection via DATABASE_URL ─────────────
        if self.connection_string and HAS_PSYCOPG2:
            print("📡 Connecting to Neon PostgreSQL...")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.conn = psycopg2.connect(self.connection_string)
                    self.conn.autocommit = True

                    # Verify and auto-create tables if they don't exist
                    self._ensure_tables_exist()

                    self.initialized = True
                    self.backend_type = "neon_postgres"
                    print(f"✓ Neon PostgreSQL connected successfully (target table: '{self.table_name}')")
                    return True
                except Exception as e:
                    print(f"❌ Neon PostgreSQL Attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"   Retrying in {wait_time}s...")
                        time.sleep(wait_time)

        # ── Mode 2: Fallback to Supabase REST API (if DATABASE_URL is not set) ─
        if self.supabase_url and self.supabase_key:
            print(f"📡 Connecting via Supabase REST API fallback: {self.supabase_url}...")
            try:
                test_url = f"{self.supabase_url}/rest/v1/{self.table_name}?select=id&limit=1"
                resp = requests.get(test_url, headers=self.rest_headers, timeout=10)
                if resp.status_code in [200, 206]:
                    self.initialized = True
                    self.backend_type = "supabase_rest"
                    print(f"✓ Supabase REST connected successfully (table: '{self.table_name}')")
                    return True
                elif resp.status_code == 404 and self.table_name == "links":
                    fb_url = f"{self.supabase_url}/rest/v1/linkedin_jobs?select=id&limit=1"
                    fb_resp = requests.get(fb_url, headers=self.rest_headers, timeout=10)
                    if fb_resp.status_code in [200, 206]:
                        self.table_name = "linkedin_jobs"
                        self.initialized = True
                        self.backend_type = "supabase_rest"
                        print(f"✓ Supabase REST connected (using '{self.table_name}')")
                        return True
            except Exception as e:
                print(f"❌ Supabase REST fallback test failed: {e}")

        # If both fail / credentials not found
        print("❌ Database connection failed or credentials not found in .env")
        print("   Please provide in .env:")
        print("     DATABASE_URL=postgresql://[user]:[password]@[endpoint].neon.tech/[dbname]?sslmode=require")
        print("   Continuing in offline mode (database disabled)...")
        self.offline_mode = True
        self.backend_type = "offline"
        return False

    def _ensure_connection(self):
        """Ensure the Neon PostgreSQL connection is alive, reconnecting if closed (handles serverless idle sleep)."""
        if self.backend_type != "neon_postgres" or not self.connection_string or not HAS_PSYCOPG2:
            return

        need_reconnect = False
        if self.conn is None or getattr(self.conn, "closed", 1) != 0:
            need_reconnect = True
        else:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except Exception:
                need_reconnect = True

        if need_reconnect:
            try:
                self.conn = psycopg2.connect(self.connection_string)
                self.conn.autocommit = True
            except Exception as e:
                print(f"⚠️ Reconnecting to Neon PostgreSQL failed: {e}")

    def _ensure_tables_exist(self):
        """Create the target jobs table and scraper progress table in Neon DB if they don't already exist."""
        if not self.conn or self.conn.closed != 0:
            return

        with self.conn.cursor() as cur:
            # 1. Target links table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(255) UNIQUE,
                    title VARCHAR(500),
                    company_name VARCHAR(255),
                    company_url VARCHAR(500),
                    company_logo VARCHAR(1000),
                    location_city VARCHAR(255),
                    location_state VARCHAR(255),
                    location_country VARCHAR(255),
                    location_display VARCHAR(500),
                    description TEXT,
                    date_posted DATE,
                    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    job_url VARCHAR(1000),
                    apply_url VARCHAR(1000),
                    job_type VARCHAR(255),
                    job_level VARCHAR(255),
                    company_industry VARCHAR(255),
                    job_function VARCHAR(255),
                    is_remote BOOLEAN DEFAULT FALSE,
                    is_easy_apply BOOLEAN DEFAULT FALSE,
                    compensation_min NUMERIC,
                    compensation_max NUMERIC,
                    compensation_currency VARCHAR(50),
                    compensation_interval VARCHAR(50),
                    salary_text VARCHAR(500),
                    experience VARCHAR(255),
                    skills TEXT,
                    sponsorship_h1b VARCHAR(255),
                    source VARCHAR(50) DEFAULT 'l_i',
                    emails TEXT,
                    search_keyword VARCHAR(255)
                );
            """)

            # Ensure index on job_id for fast deduplication
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_job_id ON {self.table_name} (job_id);
            """)

            # Ensure all columns exist in case table was created with an older schema
            columns_to_check = [
                ("sponsorship_h1b", "VARCHAR(255)"),
                ("source", "VARCHAR(50) DEFAULT 'l_i'"),
                ("skills", "TEXT"),
                ("salary_text", "VARCHAR(500)"),
                ("experience", "VARCHAR(255)"),
                ("search_keyword", "VARCHAR(255)"),
                ("emails", "TEXT"),
            ]
            for col_name, col_type in columns_to_check:
                try:
                    cur.execute(f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
                except Exception:
                    pass

            # 2. Scraper progress checkpoint table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.progress_table} (
                    id INT PRIMARY KEY,
                    last_index INT DEFAULT 0,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute(f"""
                INSERT INTO {self.progress_table} (id, last_index)
                VALUES (1, 0)
                ON CONFLICT (id) DO NOTHING;
            """)

            # 3. Active clients table in Neon DB
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.active_clients_table} (
                    id SERIAL PRIMARY KEY,
                    lead_id VARCHAR(255) UNIQUE,
                    subscription_id VARCHAR(255),
                    subscription_status VARCHAR(50),
                    company_id VARCHAR(50),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    full_name VARCHAR(255),
                    email VARCHAR(255),
                    phone_number VARCHAR(100),
                    domain VARCHAR(255),
                    desired_job_titles JSONB,
                    skills JSONB,
                    client_experience_in_years NUMERIC,
                    client_experience_in_months NUMERIC,
                    target_role_level VARCHAR(100),
                    work_location VARCHAR(255),
                    city VARCHAR(100),
                    state VARCHAR(100),
                    country VARCHAR(100),
                    resume_filename TEXT,
                    raw_data JSONB,
                    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.active_clients_table}_lead_id ON {self.active_clients_table} (lead_id);
            """)

    def job_exists(self, job_id: str) -> bool:
        """Check if job already exists in database."""
        if self.offline_mode or not self.initialized:
            return False

        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            try:
                with self.conn.cursor() as cur:
                    cur.execute(f"SELECT 1 FROM {self.table_name} WHERE job_id = %s LIMIT 1", (job_id,))
                    return cur.fetchone() is not None
            except Exception:
                return False

        elif self.backend_type == "supabase_rest":
            try:
                url = f"{self.supabase_url}/rest/v1/{self.table_name}?job_id=eq.{job_id}&select=id"
                r = requests.get(url, headers=self.rest_headers, timeout=10)
                return bool(r.status_code == 200 and r.json())
            except Exception:
                return False

        return False

    def save_job(self, job_dict: dict) -> Optional[Any]:
        """Save a single job to Neon PostgreSQL (or Supabase REST fallback)."""
        if self.offline_mode or not self.initialized:
            return None

        job_id = job_dict.get("job_id")
        if job_id and self.job_exists(job_id):
            return None

        # Neon PostgreSQL Mode
        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            try:
                columns = list(job_dict.keys())
                values = [job_dict[col] for col in columns]
                placeholders = ["%s"] * len(columns)

                insert_query = (
                    f"INSERT INTO {self.table_name} ({', '.join(columns)}) "
                    f"VALUES ({', '.join(placeholders)}) "
                    f"ON CONFLICT (job_id) DO NOTHING "
                    f"RETURNING id"
                )
                with self.conn.cursor() as cur:
                    cur.execute(insert_query, values)
                    result = cur.fetchone()
                    if result:
                        if job_dict.get("apply_url"):
                            print(f"      💾 [NEON DB] Job {job_id} SAVED with external link!")
                        return result[0]
                    return 1  # Successfully inserted or already exists
            except Exception as e:
                print(f"      ⚠️ Neon DB save error for {job_id}: {e}")
                return None

        # Supabase REST API Fallback
        elif self.backend_type == "supabase_rest":
            try:
                url = f"{self.supabase_url}/rest/v1/{self.table_name}"
                r = requests.post(url, headers=self.rest_headers, json=job_dict, timeout=10)
                if r.status_code in [200, 201]:
                    if job_dict.get("apply_url"):
                        print(f"      💾 [SUPABASE] Job {job_id} SAVED with external link!")
                    data = r.json()
                    return data[0].get("id") if data and isinstance(data, list) else 1
                return None
            except Exception as e:
                print(f"      ⚠️ Supabase REST save error for {job_id}: {e}")
                return None

        return None

    def save_jobs_batch(self, jobs: List[dict]) -> Dict[str, int]:
        """Save multiple jobs in batch to Neon PostgreSQL (or fallback)."""
        results = {"success": 0, "failed": 0, "duplicate": 0}

        if self.offline_mode or not jobs:
            if jobs:
                print(f"\n📊 Running in offline mode - database skipped")
                results["failed"] = len(jobs)
            return results

        db_name = "Neon DB" if self.backend_type == "neon_postgres" else "Supabase"
        print(f"\n💾 Saving {len(jobs)} jobs to {db_name} ('{self.table_name}' table)...")

        # Neon PostgreSQL Fast Batch Insert
        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            success_count = 0
            duplicate_count = 0
            failed_count = 0

            for job_dict in jobs:
                job_id = job_dict.get("job_id")
                try:
                    if job_id and self.job_exists(job_id):
                        duplicate_count += 1
                        continue

                    columns = list(job_dict.keys())
                    values = [job_dict[col] for col in columns]
                    placeholders = ["%s"] * len(columns)

                    insert_query = (
                        f"INSERT INTO {self.table_name} ({', '.join(columns)}) "
                        f"VALUES ({', '.join(placeholders)}) "
                        f"ON CONFLICT (job_id) DO NOTHING "
                        f"RETURNING id"
                    )
                    with self.conn.cursor() as cur:
                        cur.execute(insert_query, values)
                        res = cur.fetchone()
                        if res:
                            success_count += 1
                            if job_dict.get("apply_url"):
                                print(f"      💾 [NEON DB] Job {job_id} SAVED with external link!")
                        else:
                            duplicate_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"      ⚠️ Neon DB batch insert error {job_id}: {e}")

            print(f"\n📊 {db_name} Results:")
            print(f"   ✅ Successfully saved: {success_count}/{len(jobs)}")
            if duplicate_count:
                print(f"   🔄 Duplicates skipped: {duplicate_count}")

            results["success"] = success_count
            results["failed"] = failed_count
            results["duplicate"] = duplicate_count
            return results

        # REST API Mode Fallback
        else:
            success_count = 0
            for job_dict in jobs:
                try:
                    record_id = self.save_job(job_dict)
                    if record_id:
                        success_count += 1
                except Exception:
                    pass

            print(f"\n📊 Database Results:")
            print(f"   ✅ Successfully saved: {success_count}/{len(jobs)}")

            results["success"] = success_count
            results["failed"] = len(jobs) - success_count
            return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get scraping statistics from the database."""
        if self.offline_mode or not self.initialized:
            return {}

        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            try:
                with self.conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    total = cur.fetchone()[0]
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name} WHERE apply_url IS NOT NULL")
                    external = cur.fetchone()[0]
                return {"total_jobs": total, "external_links": external}
            except Exception as e:
                print(f"❌ Error getting statistics: {e}")
                return {}

        elif self.backend_type == "supabase_rest":
            try:
                h = self.rest_headers.copy()
                h["Prefer"] = "count=exact"
                h["Range"] = "0-0"
                r_total = requests.get(f"{self.supabase_url}/rest/v1/{self.table_name}?select=id", headers=h, timeout=10)
                cr = r_total.headers.get("content-range", "")
                total = int(cr.split("/")[-1]) if "/" in cr else 0

                r_ext = requests.get(f"{self.supabase_url}/rest/v1/{self.table_name}?select=id&apply_url=not.is.null", headers=h, timeout=10)
                cr_ext = r_ext.headers.get("content-range", "")
                external = int(cr_ext.split("/")[-1]) if "/" in cr_ext else 0

                return {"total_jobs": total, "external_links": external}
            except Exception as e:
                print(f"❌ Error getting statistics: {e}")
                return {}

        return {}

    # --- Progress Tracking Methods ---

    def ensure_progress_row_exists(self):
        """Ensure the progress tracking row exists in Neon DB."""
        if self.offline_mode or not self.initialized:
            return

        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {self.progress_table} (id, last_index) "
                        f"VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
                    )
            except Exception as e:
                print(f"⚠️ Error ensuring progress row: {e}")

        elif self.backend_type == "supabase_rest":
            try:
                url = f"{self.supabase_url}/rest/v1/{self.progress_table}?id=eq.1&select=id"
                r = requests.get(url, headers=self.rest_headers, timeout=10)
                if r.status_code == 200 and len(r.json()) == 0:
                    insert_url = f"{self.supabase_url}/rest/v1/{self.progress_table}"
                    h = self.rest_headers.copy()
                    h["Prefer"] = "return=minimal"
                    requests.post(insert_url, headers=h, json={"id": 1, "last_index": 0}, timeout=10)
            except Exception as e:
                print(f"⚠️ Error ensuring progress row: {e}")

    def get_progress(self) -> int:
        """Get the last scraped keyword index checkpoint."""
        if self.offline_mode or not self.initialized:
            return 0

        self.ensure_progress_row_exists()

        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            try:
                with self.conn.cursor() as cur:
                    cur.execute(f"SELECT last_index FROM {self.progress_table} WHERE id = 1")
                    result = cur.fetchone()
                    return result[0] if result else 0
            except Exception as e:
                print(f"⚠️ Error getting progress: {e}")
                return 0

        elif self.backend_type == "supabase_rest":
            try:
                url = f"{self.supabase_url}/rest/v1/{self.progress_table}?id=eq.1&select=last_index"
                r = requests.get(url, headers=self.rest_headers, timeout=10)
                if r.status_code == 200 and r.json():
                    return r.json()[0]["last_index"]
                return 0
            except Exception as e:
                print(f"⚠️ Error getting progress: {e}")
                return 0

        return 0

    def update_progress(self, index: int):
        """Update the last scraped keyword index checkpoint in Neon DB."""
        if self.offline_mode or not self.initialized:
            return

        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE {self.progress_table} SET last_index = %s, updated_at = NOW() WHERE id = 1",
                        (index,)
                    )
                print(f"✅ Progress updated in Neon DB → {index}")
            except Exception as e:
                print(f"⚠️ Failed to update progress: {e}")

        elif self.backend_type == "supabase_rest":
            try:
                url = f"{self.supabase_url}/rest/v1/{self.progress_table}?id=eq.1"
                h = self.rest_headers.copy()
                h["Prefer"] = "return=minimal"
                r = requests.patch(url, headers=h, json={"last_index": index}, timeout=10)
                if r.status_code in [200, 204]:
                    print(f"✅ Progress updated → {index}")
                else:
                    print(f"⚠️ Failed to update progress: {r.text[:100]}")
            except Exception as e:
                print(f"⚠️ Failed to update progress: {e}")

    # --- ApplyUS CRM Active Clients Sync & Keyword Extraction ---

    def save_active_clients_to_db(self, clients: List[Dict[str, Any]]) -> int:
        """Save / update active clients into Neon PostgreSQL."""
        if not clients or self.offline_mode or not self.initialized:
            return 0

        saved = 0
        if self.backend_type == "neon_postgres":
            self._ensure_connection()
            for c in clients:
                try:
                    lead_id = c.get("lead_id") or c.get("id")
                    if not lead_id:
                        continue
                    insert_query = f"""
                        INSERT INTO {self.active_clients_table} (
                            lead_id, subscription_id, subscription_status, company_id,
                            first_name, last_name, full_name, email, phone_number,
                            domain, desired_job_titles, skills,
                            client_experience_in_years, client_experience_in_months,
                            target_role_level, work_location, city, state, country,
                            resume_filename, raw_data, synced_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, NOW()
                        ) ON CONFLICT (lead_id) DO UPDATE SET
                            subscription_status = EXCLUDED.subscription_status,
                            full_name = EXCLUDED.full_name,
                            domain = EXCLUDED.domain,
                            desired_job_titles = EXCLUDED.desired_job_titles,
                            skills = EXCLUDED.skills,
                            client_experience_in_years = EXCLUDED.client_experience_in_years,
                            target_role_level = EXCLUDED.target_role_level,
                            country = EXCLUDED.country,
                            raw_data = EXCLUDED.raw_data,
                            synced_at = NOW();
                    """
                    values = (
                        str(lead_id),
                        c.get("subscription_id"),
                        c.get("subscription_status"),
                        c.get("company_id"),
                        c.get("first_name"),
                        c.get("last_name"),
                        c.get("full_name"),
                        c.get("email"),
                        c.get("phone_number"),
                        c.get("domain"),
                        json.dumps(c.get("desired_job_titles") or []),
                        json.dumps(c.get("skills") or []),
                        c.get("client_experience_in_years"),
                        c.get("client_experience_in_months"),
                        c.get("target_role_level"),
                        c.get("work_location"),
                        c.get("city"),
                        c.get("state"),
                        c.get("country"),
                        c.get("resume_filename"),
                        json.dumps(c),
                    )
                    with self.conn.cursor() as cur:
                        cur.execute(insert_query, values)
                        saved += 1
                except Exception as e:
                    print(f"⚠️ Error saving client {c.get('lead_id')}: {e}")

            if saved:
                print(f"💾 Saved/updated {saved} active client(s) in Neon DB ('{self.active_clients_table}' table)")
        return saved

    def fetch_active_clients_from_db(self) -> List[Dict[str, Any]]:
        """Retrieve cached active clients from Neon DB if CRM API is unreachable."""
        if self.offline_mode or not self.initialized or self.backend_type != "neon_postgres":
            return []
        self._ensure_connection()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor if HAS_PSYCOPG2 else None) as cur:
                cur.execute(f"SELECT * FROM {self.active_clients_table} ORDER BY id ASC")
                rows = cur.fetchall()
                clients = []
                for row in rows:
                    if isinstance(row, dict):
                        raw = row.get("raw_data")
                        if isinstance(raw, dict):
                            clients.append(raw)
                        elif isinstance(raw, str):
                            try:
                                clients.append(json.loads(raw))
                            except Exception:
                                clients.append(row)
                        else:
                            clients.append(row)
                    else:
                        clients.append(row)
                return clients
        except Exception as e:
            print(f"⚠️ Error reading active clients from Neon DB: {e}")
            return []

    def fetch_and_sync_active_clients(self, domain_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Hit the CRM active clients endpoint (https://api.applyus.org/api/clients/active)
        using INTERNAL_SERVICE_API_KEY from .env, and persist results to Neon DB."""
        endpoint_path = os.getenv("CRM_ENDPOINT_PATH", self.crm_endpoint_path).strip()
        if not endpoint_path.startswith("/"):
            endpoint_path = "/" + endpoint_path
        backend_url = (os.getenv("CRM_BACKEND_URL") or self.crm_backend_url).strip().rstrip("/")
        api_url = f"{backend_url}{endpoint_path}"
        api_key = (os.getenv("INTERNAL_SERVICE_API_KEY") or self.crm_api_key).strip()
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        params = {}
        if domain_filter:
            params["domain"] = domain_filter

        print(f"📡 Fetching active clients from CRM API: {api_url}...")
        clients = []
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # 30s timeout handles Render cold starts smoothly
                response = requests.get(api_url, headers=headers, params=params, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        clients = result.get("data", [])
                        print(f"✅ Successfully fetched {len(clients)} active client(s):")
                        for client in clients:
                            name = client.get("full_name") or f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                            domain = client.get("domain", "N/A")
                            country = client.get("country") or client.get("country_name") or "United States"
                            titles = client.get("desired_job_titles", [])
                            exp = client.get("client_experience_in_years", 0)
                            print(f"   - {name} | {domain} | Country: {country} | Titles: {titles} | Exp: {exp} yrs")
                        break
                    else:
                        print(f"❌ CRM API error response: {result.get('message')}")
                else:
                    print(f"⚠️ CRM API HTTP {response.status_code}: {response.text[:200]}")
            except Exception as e:
                print(f"⚠️ CRM API attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        # Sync to Neon DB if we retrieved clients
        if clients:
            self.save_active_clients_to_db(clients)
            self.active_clients = clients
            return clients

        # Fallback: check if we have cached active clients in Neon DB
        print("⚠️ Attempting fallback to cached active clients in Neon DB...")
        cached = self.fetch_active_clients_from_db()
        if cached:
            print(f"✓ Found {len(cached)} cached active client(s) in Neon DB")
            self.active_clients = cached
            return cached

        return []

    def get_client_search_targets(self, domain_filter: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Fetch active clients and extract unique (keyword, country) search targets.
        Strict deduplication rule:
          - If two or more clients share the same country and desired job title/domain,
            take that pair ONLY ONCE and scrape it only once.
          - If clients have the same job title but different countries (e.g. 'Data Analyst' in
            'United States' vs 'Ireland'), both must be scraped under their respective country.
          - Uniquely key every search target as: (keyword.strip().lower(), country.strip().lower()).
        """
        clients = self.fetch_and_sync_active_clients(domain_filter=domain_filter)
        if not clients:
            return []

        default_country = os.getenv("LOCATION", "United States").strip() or "United States"
        targets: List[Dict[str, str]] = []
        seen = set()

        for client in clients:
            # 1. Location / Country: read 'country' (or 'country_name'), default to 'United States'
            raw_country = client.get("country") or client.get("country_name")
            country_clean = str(raw_country).strip() if raw_country else default_country
            if not country_clean:
                country_clean = default_country

            # 2. Keywords / Job Titles: desired_job_titles list (fallback to domain if titles are empty)
            raw_titles = client.get("desired_job_titles")
            titles = []
            if isinstance(raw_titles, list):
                titles = [t for t in raw_titles if t and str(t).strip()]
            elif isinstance(raw_titles, str) and raw_titles.strip():
                titles = [raw_titles.strip()]

            # Fallback to domain if titles are empty
            if not titles and client.get("domain"):
                domain_val = str(client.get("domain")).strip()
                if domain_val:
                    titles = [domain_val]

            # 3. Deduplicate strictly by (keyword.strip().lower(), country.strip().lower())
            for t in titles:
                kw_clean = str(t).strip()
                if not kw_clean:
                    continue
                dedup_key = (kw_clean.lower(), country_clean.lower())
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    targets.append({
                        "keyword": kw_clean,
                        "country": country_clean,
                    })

        return targets

    def get_client_search_keywords(self, domain_filter: Optional[str] = None) -> List[str]:
        """Extract unique search keywords directly from active clients' desired_job_titles (backwards compatibility)."""
        targets = self.get_client_search_targets(domain_filter=domain_filter)
        keywords = []
        seen = set()
        for t in targets:
            kw = t["keyword"]
            if kw.lower() not in seen:
                seen.add(kw.lower())
                keywords.append(kw)
        return keywords

    # --- Primary Function / Domain Extraction Methods (Source Database Fallback) ---

    def get_primary_functions(self, table_name: str = None) -> List[str]:
        """Fetch search keywords / primary functions.
        Primary source: ApplyUS CRM active clients API (synced to Neon DB).
        Fallback source: Source onboarding_submissions table.
        """
        # 1. Try ApplyUS CRM active clients first
        try:
            client_keywords = self.get_client_search_keywords()
            if client_keywords:
                return client_keywords
        except Exception as e:
            print(f"⚠️ Error getting keywords from active clients API: {e}")

        target_table = table_name or self.source_table
        functions = []

        # 2. Direct PostgreSQL on Source Database (if SOURCE_DATABASE_URL is provided)
        if self.source_database_url and HAS_PSYCOPG2:
            try:
                print(f"📡 Connecting to Source Database (PostgreSQL)...")
                with psycopg2.connect(self.source_database_url) as src_conn:
                    with src_conn.cursor() as cur:
                        cur.execute(
                            f"SELECT DISTINCT primary_function FROM {target_table} "
                            f"WHERE primary_function IS NOT NULL AND TRIM(primary_function) != ''"
                        )
                        rows = cur.fetchall()
                        for r in rows:
                            val = r[0] if isinstance(r, (list, tuple)) else (r.get("primary_function") if isinstance(r, dict) else None)
                            if val and str(val).strip():
                                functions.append(str(val).strip())
                if functions:
                    print(f"✓ Retrieved {len(functions)} primary function(s) from Source DB (Postgres)")
                    return sorted(list(set(functions)))
            except Exception as e:
                print(f"⚠️ Error fetching primary_function from Source DB (Postgres): {e}")

        # 2. REST API on Source Database (via SOURCE_SUPABASE_URL & SOURCE_SUPABASE_KEY)
        if self.source_supabase_url and self.source_supabase_key:
            try:
                print(f"📡 Fetching primary functions from Source REST API: {self.source_supabase_url} (table: '{target_table}')...")
                url = f"{self.source_supabase_url}/rest/v1/{target_table}?select=primary_function&primary_function=not.is.null"
                r = requests.get(url, headers=self.source_rest_headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    for row in data:
                        val = row.get("primary_function")
                        if val and str(val).strip():
                            functions.append(str(val).strip())
                    if functions:
                        print(f"✓ Retrieved {len(functions)} primary function(s) from Source Supabase REST API")
                        return sorted(list(set(functions)))
                else:
                    print(f"⚠️ Error fetching primary_function from Source Supabase (REST {r.status_code}): {r.text[:150]}")
            except Exception as e:
                print(f"⚠️ Error fetching primary_function from Source Supabase (REST): {e}")

        # 3. Fallback to Target Database connection if source table exists in the target DB
        if not functions and self.initialized and not self.offline_mode:
            if self.backend_type == "neon_postgres":
                self._ensure_connection()
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(
                            f"SELECT DISTINCT primary_function FROM {target_table} "
                            f"WHERE primary_function IS NOT NULL AND TRIM(primary_function) != ''"
                        )
                        rows = cur.fetchall()
                        for r in rows:
                            val = r[0] if isinstance(r, (list, tuple)) else (r.get("primary_function") if isinstance(r, dict) else None)
                            if val and str(val).strip():
                                functions.append(str(val).strip())
                except Exception:
                    pass

        # Deduplicate while preserving unique set
        unique_functions = []
        seen = set()
        for fn in functions:
            if fn not in seen:
                seen.add(fn)
                unique_functions.append(fn)

        return unique_functions


# Full backward compatibility aliases across existing imports
SupabaseManager = NeonDatabaseManager
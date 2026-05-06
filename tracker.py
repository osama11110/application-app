import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = "applications.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            site         TEXT NOT NULL,
            url          TEXT NOT NULL,
            company      TEXT,
            title        TEXT,
            location     TEXT,
            status       TEXT NOT NULL,
            match_score  INTEGER DEFAULT 0,
            applied_at   TEXT,
            notes        TEXT,
            UNIQUE(site, url)
        )
    """)
    # Migrate existing DBs that predate the location column
    try:
        conn.execute("ALTER TABLE applications ADD COLUMN location TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def has_applied(site: str, url: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id FROM applications WHERE site=? AND url=?", (site, url)
    ).fetchone()
    conn.close()
    return row is not None


def record_application(site: str, url: str, company: str, title: str,
                       status: str, match_score: int = 0, location: str = "", notes: str = ""):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO applications
               (site, url, company, title, location, status, match_score, applied_at, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (site, url, company, title, location, status, match_score,
             datetime.now().isoformat(), notes)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"DB record error: {e}")
    finally:
        conn.close()


def get_daily_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().date().isoformat()
    count = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE applied_at LIKE ? AND status='applied'",
        (f"{today}%",)
    ).fetchone()[0]
    conn.close()
    return count


def get_summary() -> dict:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT site, status, COUNT(*) as cnt
        FROM applications GROUP BY site, status ORDER BY site
    """).fetchall()
    conn.close()
    summary: dict = {}
    for site, status, cnt in rows:
        summary.setdefault(site, {})[status] = cnt
    return summary

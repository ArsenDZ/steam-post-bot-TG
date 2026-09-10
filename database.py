"""
Слой работы с SQLite: список администраторов и черновики/посты.
"""
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    steam_app_id TEXT,
    game_name TEXT,
    steam_url TEXT,
    image_url TEXT,
    image_local_path TEXT,
    original_text TEXT,
    draft_text TEXT,
    status TEXT NOT NULL DEFAULT 'draft',  -- draft | preview | published | cancelled
    created_at TEXT NOT NULL,
    published_at TEXT
);
"""


@dataclass
class PostRecord:
    id: int
    admin_id: int
    steam_app_id: Optional[str]
    game_name: Optional[str]
    steam_url: Optional[str]
    image_url: Optional[str]
    image_local_path: Optional[str]
    original_text: Optional[str]
    draft_text: Optional[str]
    status: str
    created_at: str
    published_at: Optional[str]


class Database:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------- Admins ----------

    def seed_admins(self, user_ids: List[int]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for uid in user_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, NULL, ?)",
                    (uid, now),
                )

    def add_admin(self, user_id: int, added_by: int) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                (user_id, added_by, now),
            )
            return cur.rowcount > 0

    def remove_admin(self, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            return cur.rowcount > 0

    def list_admins(self) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM admins ORDER BY added_at").fetchall()
            return [r["user_id"] for r in rows]

    def is_admin(self, user_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row is not None

    # ---------- Posts ----------

    def create_post(
        self,
        admin_id: int,
        steam_app_id: Optional[str],
        game_name: Optional[str],
        steam_url: Optional[str],
        image_url: Optional[str],
        image_local_path: Optional[str],
        original_text: Optional[str],
        draft_text: Optional[str],
        status: str = "draft",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO posts
                    (admin_id, steam_app_id, game_name, steam_url, image_url,
                     image_local_path, original_text, draft_text, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (admin_id, steam_app_id, game_name, steam_url, image_url,
                 image_local_path, original_text, draft_text, status, now),
            )
            return cur.lastrowid

    def update_draft_text(self, post_id: int, draft_text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE posts SET draft_text = ? WHERE id = ?", (draft_text, post_id)
            )

    def update_status(self, post_id: int, status: str) -> None:
        with self._connect() as conn:
            if status == "published":
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE posts SET status = ?, published_at = ? WHERE id = ?",
                    (status, now, post_id),
                )
            else:
                conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))

    def get_post(self, post_id: int) -> Optional[PostRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            return PostRecord(**dict(row)) if row else None

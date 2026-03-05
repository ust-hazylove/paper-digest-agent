from __future__ import annotations
import os, sqlite3, hashlib, re
from typing import Optional, Tuple
from .arxiv import Paper

def _norm_title(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return t

def _title_hash(title: str) -> str:
    return hashlib.sha256(_norm_title(title).encode("utf-8")).hexdigest()

class PaperStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS seen (
          key TEXT PRIMARY KEY,
          first_seen TEXT
        );
        """)
        self.conn.commit()

    def make_key(self, p: Paper) -> str:
        if p.arxiv_id:
            return f"arxiv:{p.arxiv_id}"
        return f"title:{_title_hash(p.title)}"

    def is_seen(self, key: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM seen WHERE key=? LIMIT 1", (key,))
        return cur.fetchone() is not None

    def mark_seen(self, key: str, first_seen_iso: str):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO seen(key, first_seen) VALUES(?, ?)", (key, first_seen_iso))
        self.conn.commit()

    def close(self):
        self.conn.close()

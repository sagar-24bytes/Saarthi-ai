import sqlite3
import os
import sys
from pathlib import Path

# Resolve DB_PATH relative to the executable directory if packaged,
# or the project root directory if running as a script.
if getattr(sys, 'frozen', False):
    DB_PATH = os.path.join(os.path.dirname(sys.executable), "memory.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS memory (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS allowed_folders (
        path TEXT PRIMARY KEY
    )
    """)

    conn.commit()
    conn.close()


def add_allowed_folder(path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO allowed_folders (path) VALUES (?)", (path,))
    conn.commit()
    conn.close()


def remove_allowed_folder(path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM allowed_folders WHERE path = ?", (path,))
    conn.commit()
    conn.close()


def get_allowed_folders() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT path FROM allowed_folders")
        rows = cur.fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def set_memory(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO memory (key, value)
    VALUES (?, ?)
    ON CONFLICT(key)
    DO UPDATE SET value = excluded.value
    """, (key, value))

    conn.commit()
    conn.close()


def get_memory(key: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT value FROM memory WHERE key = ?", (key,))
    row = cur.fetchone()

    conn.close()

    if row:
        return row[0]

    return None

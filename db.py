# -*- coding: utf-8 -*-
"""SQLite 数据层：签到项、通知配置、签到日志"""
import sqlite3
import json
import os
import threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sign.db")

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'POST',
    headers TEXT DEFAULT '',
    cookie TEXT DEFAULT '',
    body TEXT DEFAULT '',
    schedule_time TEXT NOT NULL DEFAULT '08:00',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_status TEXT DEFAULT '',
    last_time TEXT DEFAULT '',
    last_response TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notify_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    app_id TEXT DEFAULT '',
    app_secret TEXT DEFAULT '',
    user_openid TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    item_name TEXT,
    status TEXT NOT NULL,
    http_code INTEGER,
    response TEXT DEFAULT '',
    trigger_type TEXT DEFAULT 'manual',
    notify_status TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _lock, get_conn() as conn:
        conn.executescript(SCHEMA)
        # 通知配置保底一行
        conn.execute(
            "INSERT OR IGNORE INTO notify_config (id, enabled) VALUES (1, 0)"
        )
        conn.commit()


# ---------------- 签到项 ----------------

def row_to_item(row):
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    return d


def list_items():
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
    return [row_to_item(r) for r in rows]


def get_item(item_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_item(row) if row else None


def create_item(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO items (name, url, method, headers, cookie, body, schedule_time, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", "未命名签到"),
                data["url"],
                data.get("method", "POST").upper(),
                data.get("headers", "") or "",
                data.get("cookie", "") or "",
                data.get("body", "") or "",
                data.get("schedule_time", "08:00"),
                1 if data.get("enabled", True) else 0,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid


def update_item(item_id, data):
    fields = []
    values = []
    for key in ("name", "url", "method", "headers", "cookie", "body", "schedule_time"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if "enabled" in data:
        fields.append("enabled = ?")
        values.append(1 if data["enabled"] else 0)
    if not fields:
        return
    values.append(item_id)
    with _lock, get_conn() as conn:
        conn.execute(f"UPDATE items SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()


def delete_item(item_id):
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()


def update_item_result(item_id, status, response):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, get_conn() as conn:
        conn.execute(
            "UPDATE items SET last_status = ?, last_time = ?, last_response = ? WHERE id = ?",
            (status, now, (response or "")[:500], item_id),
        )
        conn.commit()


# ---------------- 通知配置 ----------------

def get_notify_config():
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM notify_config WHERE id = 1").fetchone()
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    return d


def save_notify_config(data):
    with _lock, get_conn() as conn:
        conn.execute(
            """INSERT INTO notify_config (id, enabled, app_id, app_secret, user_openid)
               VALUES (1, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   enabled = excluded.enabled,
                   app_id = excluded.app_id,
                   app_secret = excluded.app_secret,
                   user_openid = excluded.user_openid""",
            (
                1 if data.get("enabled") else 0,
                data.get("app_id", ""),
                data.get("app_secret", ""),
                data.get("user_openid", ""),
            ),
        )
        conn.commit()


# ---------------- 日志 ----------------

def add_log(item_id, item_name, status, http_code=None, response="", trigger_type="manual", notify_status=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO logs (item_id, item_name, status, http_code, response, trigger_type, notify_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, item_name, status, http_code, (response or "")[:1000], trigger_type, notify_status, now),
        )
        conn.commit()
        return cur.lastrowid


def list_logs(limit=50):
    with _lock, get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

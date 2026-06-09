import sqlite3
import os
import json
from datetime import datetime

DATABASE_PATH = os.path.join("data", "mom_assistant.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            audio_path TEXT,
            transcript TEXT,
            summary TEXT,
            status TEXT NOT NULL DEFAULT 'processing'
        )
    """)
    conn.commit()
    conn.close()

def create_meeting(title, audio_path=None, duration=0, status="processing"):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_str = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO meetings (title, date, duration, audio_path, status) VALUES (?, ?, ?, ?, ?)",
        (title, date_str, duration, audio_path, status)
    )
    conn.commit()
    meeting_id = cursor.lastrowid
    conn.close()
    return meeting_id

def get_meetings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, date, duration, audio_path, status FROM meetings ORDER BY date DESC")
    meetings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return meetings

def get_meeting(meeting_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        meeting = dict(row)
        # Parse summary JSON if it exists
        if meeting["summary"]:
            try:
                meeting["summary"] = json.loads(meeting["summary"])
            except json.JSONDecodeError:
                pass
        return meeting
    return None

def update_meeting_status(meeting_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE meetings SET status = ? WHERE id = ?", (status, meeting_id))
    conn.commit()
    conn.close()

def update_meeting_data(meeting_id, transcript, summary_dict, duration=None, status="completed"):
    conn = get_db_connection()
    cursor = conn.cursor()
    summary_json = json.dumps(summary_dict)
    if duration is not None:
        cursor.execute(
            "UPDATE meetings SET transcript = ?, summary = ?, duration = ?, status = ? WHERE id = ?",
            (transcript, summary_json, duration, status, meeting_id)
        )
    else:
        cursor.execute(
            "UPDATE meetings SET transcript = ?, summary = ?, status = ? WHERE id = ?",
            (transcript, summary_json, status, meeting_id)
        )
    conn.commit()
    conn.close()

def delete_meeting(meeting_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch audio path to delete the file
    cursor.execute("SELECT audio_path FROM meetings WHERE id = ?", (meeting_id,))
    row = cursor.fetchone()
    audio_path = row["audio_path"] if row else None
    
    cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()
    
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except OSError:
            pass

def rename_meeting(meeting_id, title):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE meetings SET title = ? WHERE id = ?", (title, meeting_id))
    conn.commit()
    conn.close()


import sqlite3 as sqlite
from datetime import datetime
DATABASE_NAME = 'schedule_assistant.db'

def get_db_connection():
    connection = sqlite.connect(DATABASE_NAME)
    connection.row_factory = sqlite.Row
    return connection

def init_db():
    with get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        location TEXT,
                        reminder_minutes INTEGER,
                        is_notified INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                       )
                       ''')
        connection.commit()
        print("Khoi tao database thanh cong!")

def add_event(event_data: dict):
    with get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute('''
                       INSERT INTO events (event, start_time, end_time, location, reminder_minutes)
                       VALUES (:event, :start_time, :end_time, :location, :reminder_minutes)
                       ''',
                       {
                           "event": event_data.get("event"),
                           "start_time": event_data.get("start_time"),
                           "end_time": event_data.get("end_time"),
                           "location": event_data.get("location"),
                           "reminder_minutes": event_data.get("reminder_minutes")
                       }
                       )
        connection.commit()
        return cursor.lastrowid
    
def get_events_for_range(start_date: str, end_date: str):
    with get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
                       "SELECT * FROM events WHERE start_time BETWEEN ? AND ?",
                        (start_date, end_date)
                       )
        return [dict(row) for row in cursor.fetchall()]

def get_all_events():
    with get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
                        "SELECT * FROM events ORDER BY start_time ASC"
                    )
        return [dict(row) for row in cursor.fetchall()]

def delete_event(event_id: int):
    with get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
                        "DELETE FROM events WHERE id = ?",
                        (event_id,)
                       ) 
        connection.commit()

def update_event(event_id: int, updated_data: dict):
    with get_db_connection() as connection:
        cursor = connection.cursor()
        cursor.execute('''
                       UPDATE events
                       SET event = :event,
                           start_time = :start_time,
                           end_time = :end_time,
                           location = :location,
                           reminder_minutes = :reminder_minutes
                       WHERE id = :id
                       ''',
                       {
                           "event": updated_data.get("event"),
                           "start_time": updated_data.get("start_time"),
                           "end_time": updated_data.get("end_time"),
                           "location": updated_data.get("location"),
                           "reminder_minutes": updated_data.get("reminder_minutes"),
                           "id": event_id
                       }
                       )
        connection.commit()
def get_events_to_notify(now_iso: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM events
            WHERE 
                is_notified = 0 
                AND reminder_minutes IS NOT NULL
                AND datetime(start_time, '-' || reminder_minutes || ' minutes') <= ?
            """,
            (now_iso,)
        )
        return [dict(row) for row in cursor.fetchall()]

def set_event_notified(event_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE events SET is_notified = 1 WHERE id = ?", (event_id,))
        conn.commit()
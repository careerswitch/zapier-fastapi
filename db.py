import sqlite3
import os
from typing import List, Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "logs.db")


def init_db():
    """Initialize the database with required tables"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Create main error logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zap_name TEXT NOT NULL,
                error_message TEXT NOT NULL,
                explanation TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'unresolved',
                UNIQUE(zap_name, error_message, timestamp)
            )
        """
        )

        # Create indexes for better performance
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_status ON error_logs(status)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_zap_name ON error_logs(zap_name)
        """
        )

        conn.commit()


def insert_error_log(
    zap_name: str, error_message: str, explanation: Optional[str] = None
) -> int:
    """Insert a new error log into the database"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO error_logs (zap_name, error_message, explanation)
                VALUES (?, ?, ?)
            """,
                (zap_name, error_message, explanation),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            print("⚠️ Duplicate log entry skipped")
            return -1


def get_all_logs(limit: int = 1000) -> List[Dict]:
    """Retrieve all error logs from the database"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, zap_name, error_message, explanation, 
                   strftime('%Y-%m-%d %H:%M:%S', timestamp) as timestamp, 
                   status
            FROM error_logs
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def update_log_status(log_id: int, new_status: str) -> bool:
    """Update the status of a specific log"""
    valid_statuses = ["unresolved", "resolved", "dismissed"]
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE error_logs 
            SET status = ? 
            WHERE id = ?
        """,
            (new_status, log_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def clear_all_logs() -> int:
    """Delete all logs from the database"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM error_logs")
        conn.commit()
        return cursor.rowcount


def get_logs_by_status(status: str) -> List[Dict]:
    """Get logs filtered by status"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, zap_name, error_message, explanation, 
                   strftime('%Y-%m-%d %H:%M:%S', timestamp) as timestamp, 
                   status
            FROM error_logs
            WHERE status = ?
            ORDER BY timestamp DESC
        """,
            (status,),
        )
        return [dict(row) for row in cursor.fetchall()]

import sqlite3
import json
import threading
from datetime import datetime
from typing import Dict, Any, List

DB_PATH = "system_monitor.db"


class Database:
    def __init__(self):
        self.conn = None
        self.session_id = None
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        try:
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(monitoring_sessions)")
            columns = [col[1] for col in cursor.fetchall()]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT,
                    end_time TEXT,
                    username TEXT,
                    cpu_model TEXT,
                    cpu_load REAL,
                    cpu_temp REAL,
                    ram_total REAL,
                    ram_used REAL,
                    ram_percent REAL,
                    gpu_model TEXT,
                    gpu_temp REAL,
                    gpu_load REAL,
                    os_name TEXT,
                    computer_name TEXT,
                    motherboard_model TEXT,
                    bios_version TEXT
                )
            """)
            if 'motherboard_model' not in columns:
                cursor.execute("ALTER TABLE monitoring_sessions ADD COLUMN motherboard_model TEXT")
            if 'bios_version' not in columns:
                cursor.execute("ALTER TABLE monitoring_sessions ADD COLUMN bios_version TEXT")
            self.conn.commit()
        except Exception as e:
            print(f"DB init error: {e}")

    def start_session(self, username: str = ""):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO monitoring_sessions (start_time, username, os_name, computer_name)
                    VALUES (?, ?, ?, ?)
                """, (datetime.now().isoformat(), username, __import__('platform').system(), __import__('socket').gethostname()))
                self.session_id = cursor.lastrowid
                self.conn.commit()
                return self.session_id
            except Exception as e:
                print(f"Session start error: {e}")
                return None

    def end_session(self):
        if self.session_id:
            with self.lock:
                try:
                    cursor = self.conn.cursor()
                    cursor.execute("UPDATE monitoring_sessions SET end_time = ? WHERE id = ?",
                                   (datetime.now().isoformat(), self.session_id))
                    self.conn.commit()
                except Exception as e:
                    print(f"Session end error: {e}")

    def save_data(self, data: Dict[str, Any]):
        if not self.session_id:
            self.start_session()
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE monitoring_sessions 
                    SET cpu_model=?, cpu_load=?, cpu_temp=?, 
                        ram_total=?, ram_used=?, ram_percent=?,
                        gpu_model=?, gpu_temp=?, gpu_load=?,
                        motherboard_model=?, bios_version=?
                    WHERE id=?
                """, (
                    str(data.get('cpu_model', '')),
                    float(data.get('cpu_load', 0)),
                    float(data.get('cpu_temp', 0)),
                    float(data.get('ram_total', 0)),
                    float(data.get('ram_used', 0)),
                    float(data.get('ram_percent', 0)),
                    str(data.get('gpu_model', '')),
                    float(data.get('gpu_temp', 0)),
                    float(data.get('gpu_load', 0)),
                    str(data.get('motherboard_model', '')),
                    str(data.get('bios_version', '')),
                    self.session_id
                ))
                self.conn.commit()
            except Exception as e:
                print(f"Save data error: {e}")

    def get_all_sessions(self, limit: int = 10):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT id, start_time, end_time, username, 
                           COALESCE(cpu_load, 0) as cpu_load, 
                           COALESCE(ram_percent, 0) as ram_percent 
                    FROM monitoring_sessions 
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                return [{'id': r[0], 'start_time': r[1], 'end_time': r[2],
                         'username': r[3], 'cpu_load': r[4] or 0, 'ram_percent': r[5] or 0} for r in rows]
            except Exception as e:
                print(f"Get sessions error: {e}")
                return []

    def export_to_json(self, filepath: str):
        with self.lock:
            try:
                data = {'sessions': self.get_all_sessions(100), 'export_date': datetime.now().isoformat()}
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False, default=str)
                return True
            except Exception as e:
                print(f"Export error: {e}")
                return False

    def close(self):
        with self.lock:
            if self.conn:
                self.end_session()
                self.conn.close()
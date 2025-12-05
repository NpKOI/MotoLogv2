# migrate_add_last_read.py
import sqlite3
from datetime import datetime

def run():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()

    try:
        # Add last_read column to group_members with NULL default (will set in app)
        c.execute('ALTER TABLE group_members ADD COLUMN last_read TEXT')
        conn.commit()
        print("Added last_read column to group_members.")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print("last_read column already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    run()
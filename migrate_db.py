import sqlite3
from datetime import datetime

DB = 'moto_log.db'

def column_exists(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

def run():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Add is_private to bikes if missing
    try:
        if not column_exists(conn, 'bikes', 'is_private'):
            c.execute("ALTER TABLE bikes ADD COLUMN is_private INTEGER DEFAULT 0")
            print("Added column bikes.is_private")
    except sqlite3.OperationalError:
        print("Could not add column bikes.is_private")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    run()
import sqlite3
from datetime import datetime

def add_events_tables():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()

    try:
        # Events table - core event information
        c.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                event_date TEXT NOT NULL,
                location_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                category TEXT NOT NULL,
                max_participants INTEGER,
                cover_image TEXT,
                status TEXT DEFAULT 'upcoming',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_local INTEGER DEFAULT 1,
                FOREIGN KEY (creator_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Event participants junction table
        c.execute('''
            CREATE TABLE IF NOT EXISTS event_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                UNIQUE(event_id, user_id),
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        print("✅ Events tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_events_tables()
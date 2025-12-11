# migrate_add_events_local.py
# Run this in PowerShell to add is_local column to existing events table:
# python migrate_add_events_local.py

import sqlite3

def migrate_add_is_local():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()
    
    try:
        # Add is_local column if it doesn't exist
        c.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in c.fetchall()]
        
        if 'is_local' not in columns:
            c.execute('ALTER TABLE events ADD COLUMN is_local INTEGER DEFAULT 1')
            print("✅ Added is_local column to events table")
        else:
            print("ℹ️ is_local column already exists")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Migration error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_add_is_local()
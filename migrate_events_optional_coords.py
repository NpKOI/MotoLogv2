# migrate_events_optional_coords.py
import sqlite3

def migrate_optional_coords():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()
    
    try:
        # Check if latitude/longitude are NOT NULL, if so we need to handle this carefully
        # SQLite doesn't support dropping NOT NULL constraints easily, so we'll document this
        # For new installations, coordinates are already optional in the schema
        
        # Add city column if it doesn't exist (extracted from location_name)
        c.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in c.fetchall()]
        
        if 'city' not in columns:
            c.execute('ALTER TABLE events ADD COLUMN city TEXT')
            print("✅ Added city column to events table")
        else:
            print("ℹ️ city column already exists")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Migration error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_optional_coords()
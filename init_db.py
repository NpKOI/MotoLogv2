import sqlite3

def init_db():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()

    # Drop existing tables (WARNING: destroys data)
    c.execute('DROP TABLE IF EXISTS rides')
    c.execute('DROP TABLE IF EXISTS bike_maintenance')
    c.execute('DROP TABLE IF EXISTS bikes')
    c.execute('DROP TABLE IF EXISTS maintenance')
    c.execute('DROP TABLE IF EXISTS users')

    # Users table with profile and emergency fields
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            country TEXT NOT NULL,
            profile_pic TEXT,
            bio TEXT,
            emergency_name TEXT,
            emergency_phone TEXT
        )
    ''')

    # Bikes table - users can have multiple bikes (image column added)
    c.execute('''
        CREATE TABLE bikes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            make_model TEXT,
            year INTEGER,
            odo REAL DEFAULT 0,
            image TEXT,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Bike maintenance history
    c.execute('''
        CREATE TABLE bike_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bike_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            date TEXT,
            notes TEXT,
            FOREIGN KEY (bike_id) REFERENCES bikes (id)
        )
    ''')

    # General maintenance (user-level reminders)
    c.execute('''
        CREATE TABLE maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            due_date TEXT,
            last_changed TEXT,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Rides table: link to bike_id and tags (comma-separated)
    c.execute('''
        CREATE TABLE rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bike_id INTEGER,
            date TEXT NOT NULL,
            distance REAL NOT NULL,
            time REAL NOT NULL,
            description TEXT,
            tags TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (bike_id) REFERENCES bikes (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == '__main__':
    init_db()
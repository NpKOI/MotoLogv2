import sqlite3

def run():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()

    # Drop existing group tables (if they exist) to recreate cleanly
    c.execute('DROP TABLE IF EXISTS group_messages')
    c.execute('DROP TABLE IF EXISTS group_members')
    c.execute('DROP TABLE IF EXISTS groups')

    # Recreate groups table with all columns
    c.execute('''
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            profile_pic TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
    ''')

    # Recreate group_members
    c.execute('''
        CREATE TABLE group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            added_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(group_id) REFERENCES groups(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Recreate group_messages
    c.execute('''
        CREATE TABLE group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(group_id) REFERENCES groups(id),
            FOREIGN KEY(sender_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Group tables recreated successfully.")

if __name__ == '__main__':
    run()
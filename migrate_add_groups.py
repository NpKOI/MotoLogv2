# migrate_add_groups.py
import sqlite3

def run():
    conn = sqlite3.connect('moto_log.db')
    c = conn.cursor()

    # groups: id, name, owner_id, profile_pic, created_at
    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            profile_pic TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
    ''')

    # group_members: id, group_id, user_id, added_at
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            added_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(group_id) REFERENCES groups(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # group_messages: id, group_id, sender_id, content, created_at
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_messages (
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
    print("Group tables created (if not existed).")

if __name__ == '__main__':
    run()
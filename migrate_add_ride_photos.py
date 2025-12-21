#!/usr/bin/env python3
"""
Migration: Add photos column to rides table
"""

import sqlite3
import os

DB_PATH = 'moto_log.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database {DB_PATH} not found")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    cur = conn.cursor()
    
    try:
        cur.execute('ALTER TABLE rides ADD COLUMN photos TEXT DEFAULT "[]"')
        print('✅ Added column "photos" to rides table')
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print('⏭️  Column "photos" already exists')
        else:
            print(f'❌ Error adding column "photos": {e}')
    
    conn.commit()
    conn.close()
    print('✅ Migration complete!')
    return True

if __name__ == '__main__':
    migrate()
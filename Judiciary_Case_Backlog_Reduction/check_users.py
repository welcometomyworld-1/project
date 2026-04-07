import sqlite3
import os

DB_PATH = r'c:\Users\MSI-1\Downloads\hackfest11 (2)\hackfest11\hackfest\backend\data\court.db'

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, role, verification_status FROM users")
    users = c.fetchall()
    print(f"Users found: {len(users)}")
    for u in users:
        print(u)
    conn.close()
else:
    print("DB not found")

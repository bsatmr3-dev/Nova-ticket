import sqlite3
import os

db_path = "database/tickets.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Print table schema
    cursor.execute("PRAGMA table_info(tickets)")
    columns = cursor.fetchall()
    print("Schema for 'tickets':")
    for col in columns:
        print(dict(col))
        
    cursor.execute("SELECT * FROM tickets")
    rows = cursor.fetchall()
    print(f"\nTotal tickets found: {len(rows)}")
    for row in rows:
        d = dict(row)
        print("\nRow data:", d)
        print("Value types:")
        for k, v in d.items():
            print(f"  {k}: {v} (type: {type(v).__name__})")
    conn.close()
else:
    print("Database not found at database/tickets.db")


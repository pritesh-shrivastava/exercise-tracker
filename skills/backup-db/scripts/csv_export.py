#!/usr/bin/env python3
"""Export workouts table to CSV. Fallback when sqlite3 CLI isn't available."""
import sqlite3, csv, sys, os

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(repo, 'data', 'workouts.sqlite')
out_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/workouts.csv'

db = sqlite3.connect(db_path)
cur = db.execute('SELECT * FROM workouts')
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
with open(out_path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(cols)
    w.writerows(rows)
print(f'Exported {len(rows)} rows to {out_path}')
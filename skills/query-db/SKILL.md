---
name: query-db
description: Use when the user wants to see the database contents, show the table, browse rows, peek at data, or inspect workouts in the SQLite DB.
version: 1.0.0
---

## When to use

When the user asks:
- "show the database", "show the table", "show rows", "show me the db"
- "peek at the data", "what's in the database", "browse workouts"
- Any request to view raw table contents

## Procedure

1. Query all rows (or with a LIMIT if the user asks for top N):

```bash
uv run python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/workouts.sqlite')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT logged_at, workout_date, workout_type, exercise, variation, sets, reps, weight_kg, equipment, per_hand, source FROM workouts ORDER BY id').fetchall()
for r in rows:
    d = dict(r)
    print(json.dumps(d))
"
```

2. Format the output as a table for Telegram. Exclude these columns:
   - `id`
   - `raw_text`
   - `details`

3. Show the row count at the end.

## Pitfalls

- **Exclude columns**: `id`, `raw_text`, and `details` should never appear in output.
- **Dumbbell weight display**: `weight_kg` stores total weight. If `per_hand=1`, mention the per-hand value in parentheses.
- **Telegram has no table syntax** — use key: value pairs per row or a structured list. Markdown `##` headers work.
- Large tables: ask if they want top N or all rows.

## Verification

Output shows the queried columns in a readable format with row count.
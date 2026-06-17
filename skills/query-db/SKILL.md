---
name: query-db
description: Use when the user wants to see raw database contents, show the table, browse rows, peek at data, or inspect workouts in the SQLite DB. For normal same-day corrections, prefer the web form Today page.
version: 1.1.0
---

## When to use

When the user asks:
- "show the database", "show the table", "show rows", "show me the db"
- "peek at the data", "what's in the database", "browse workouts"
- "top 5", "top N", "last 5", "last N" (any request to view raw table rows)
- Any request to view raw table contents

## Procedure

For same-day edits/deletes, first point the user to the private web form `Today` page:

```text
http://<vps-tailscale-ip>:8765/today
```

For raw inspection, query SQLite directly.

1. Query all rows (or with a LIMIT if the user asks for top N):

```bash
cd /home/azureuser/exercise-tracker && uv run python -c "
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
   - `source`

3. **Hide `variation`** if the value is `"default"` — only show it when it's `flat`, `incline`, or `decline`.

4. Show the row count at the end.

## Pitfalls

- **Exclude columns**: `id`, `raw_text`, `details`, and `source` should never appear in output.
- **Hide default variation**: skip `variation` when it's `"default"`. Show it only for bench angles (`flat`, `incline`, `decline`).
- **Dumbbell weight display**: `weight_kg` stores total weight. If `per_hand=1`, mention the per-hand value in parentheses.
- **Telegram has no table syntax** — use key: value pairs per row or a structured list. Markdown `##` headers work.
- Large tables: ask if they want top N or all rows.

## Verification

Output shows the queried columns in a readable format with row count.

# exercise-tracker

Personal workout tracker. Hermes Agent is the Telegram interface. Python + SQLite. No external runtime dependencies.

## Quick commands

```bash
uv run python log_workout.py "squats 3x5 @ 100kg"   # log a workout
uv run python summary.py                              # recent activity
uv run python summary.py --prs                        # personal records by body part
uv run pytest                                         # run tests
uv run ruff check .                                   # lint
uv run mypy tracker/ summary.py log_workout.py        # type check
```

## Project structure

```
tracker/          — core library (parser, normalizer, core DB helpers, PR reports)
scripts/          — one-off utilities (normalize_existing.py, restore_db.sh)
tests/            — pytest suite (test_parser.py, test_reports.py)
skills/           — Hermes agent SKILL.md definitions
log_workout.py    — CLI entry point for logging
summary.py        — CLI entry point for summaries and PRs
memory_template.md — seed for ~/.hermes/memories/MEMORY.md
```

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore

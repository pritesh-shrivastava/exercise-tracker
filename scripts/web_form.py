#!/usr/bin/env python3
"""Backwards-compatible entrypoint.

The web form implementation moved to `tracker/web_form.py`.

This wrapper keeps existing systemd units / docs that run
`python scripts/web_form.py` working.
"""

from __future__ import annotations

from tracker.web_form import main


if __name__ == "__main__":
    raise SystemExit(main())

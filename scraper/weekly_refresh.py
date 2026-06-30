# -*- coding: utf-8 -*-
"""Scheduled weekly job: refresh Grab & Go's price/stock, idempotently
replace its section of index.html, validate, and auto-commit+push only if
validation passes and something actually changed.

Grab & Go is perishable/fresh-leaning and genuinely sensitive to K-Ruoka's
weekly campaign-price rotation (confirmed live: general "Etuhinta" offers
roll over the Sun-night/Mon-morning boundary), which is why this runs
Monday morning -- see cron schedule. K-Ruoka's own recipe catalog and
Sauces (shelf-stable condiments) change far less often and were split out
to monthly_refresh.py instead, partly to keep this run shorter (less time
spent hitting k-ruoka.fi per week == lower Cloudflare/rate-limit exposure).

The Grab & Go list itself is now built from the full catalog nutrition
snapshot (build_grabgo_from_catalog.py, run against the much heavier
monthly catalog scrape -- see monthly_refresh.py) rather than a handful of
narrow search terms, since nutrition doesn't change week to week. This
job only refreshes price/stock for that existing list and drops anything
delisted or out of stock; it doesn't re-derive the list from scratch.

Runs each pipeline stage as its own subprocess (rather than importing,
since a couple of these started life as one-off analysis scripts without
a callable main()) so a crash in one stage doesn't poison the next, and
its output is visible in the log either way."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
from git_sync import safe_push

GRABGO_PIPELINE = ["refresh_grabgo_prices.py", "insert_grabgo.py"]


def run_step(script):
    print(f"\n=== {script} ===")
    result = subprocess.run([sys.executable, script], cwd=str(SCRAPER_DIR))
    if result.returncode != 0:
        raise RuntimeError(f"{script} failed with exit code {result.returncode}")


def run_git(args, **kwargs):
    print(f"$ git {' '.join(args)}")
    return subprocess.run(["git", *args], cwd=str(REPO_ROOT), **kwargs)


def main():
    sys.path.insert(0, str(SCRAPER_DIR))
    from scraper import startup_jitter
    startup_jitter()

    for script in GRABGO_PIPELINE:
        run_step(script)

    print("\n=== validating ===")
    import validate_index
    ok, errors = validate_index.validate()
    if not ok:
        print("VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        print("Reverting index.html, not committing")
        run_git(["checkout", "--", "index.html"])
        sys.exit(1)
    print("OK")

    print("\n=== checking for actual changes ===")
    diff = run_git(["diff", "--quiet", "--", "index.html"])
    if diff.returncode == 0:
        print("No changes to index.html -- nothing to commit")
        return

    print("\n=== committing and pushing ===")
    run_git(["add", "index.html", "scraper/grabgo_recommendations.json"], check=True)
    msg = "Weekly Grab & Go refresh (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
    run_git(["-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com",
             "commit", "-m", msg], check=True)
    safe_push(REPO_ROOT)


if __name__ == "__main__":
    main()

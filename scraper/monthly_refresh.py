# -*- coding: utf-8 -*-
"""Scheduled monthly job: re-run the K-Ruoka recipe-catalog pipeline
(re-crawl their recipes, remap ingredients, rebuild recipe objects) and the
Sauces pipeline (re-search candidates, revisit each for nutrition/price,
rescore), idempotently replace both sections of index.html, validate, and
auto-commit+push only if validation passes and something actually changed.

Split out from weekly_refresh.py: neither of these is genuinely
time-sensitive week to week (a new K-Ruoka recipe appearing, or a
shelf-stable condiment's price/stock shifting, is rare), so checking them
every single week was extra load on k-ruoka.fi for no real freshness gain
-- and a shorter weekly run means less weekly Cloudflare/rate-limit
exposure for the genuinely volatile stuff (Grab & Go).

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

RECIPE_PIPELINE = [
    "scrape_recipes.py", "analyze_coverage.py", "select_batch.py",
    "build_kruoka_recipes.py", "insert_kruoka_recipes.py",
]
SAUCES_PIPELINE = [
    "scrape_sauces_candidates.py", "scrape_sauces_details.py",
    "build_sauces.py", "insert_sauces.py",
]


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

    for script in RECIPE_PIPELINE:
        run_step(script)
    # a deliberate cooldown between pipelines rather than running both
    # back-to-back -- spreads this month's load over a longer window
    # instead of one continuous multi-hour session against k-ruoka.fi
    import time
    print("\nCooldown between pipelines...")
    time.sleep(600)
    for script in SAUCES_PIPELINE:
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
    run_git(["add", "index.html", "scraper/kruoka_recipes.json",
             "scraper/sauces_recommendations.json"], check=True)
    msg = "Monthly recipe + sauces refresh (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
    run_git(["-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com",
             "commit", "-m", msg], check=True)
    safe_push(REPO_ROOT)


if __name__ == "__main__":
    main()

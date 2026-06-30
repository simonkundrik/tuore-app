# -*- coding: utf-8 -*-
"""Scheduled monthly job: re-crawl the full store catalog (name/price/
stock/category across all 13 food categories), enrich any genuinely new
product with nutrition, then rebuild Grab & Go from the refreshed
catalog -- keeps both the "healthiest" ranking data and the Grab & Go
pool current as K-Ruoka's range changes, rather than staying frozen at
the one-time snapshot from when this was first built.

scrape_full_catalog.py now preserves nutrition enrichment for any EAN
already checked in a previous run, so in steady state this only spends
real time on whatever's genuinely new since last month -- the original
multi-day pass against the whole 7,266-product catalog was a one-time
cost, not a recurring one. Still, a month with a large genuine catalog
change could take a while, so this runs on its own staggered cadence
(15th of the month) rather than alongside monthly_refresh.py's recipe +
sauces pipeline (1st of the month) to avoid both heavy jobs overlapping
on a sub-1GB-RAM VM.

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

PIPELINE = [
    "scrape_full_catalog.py", "scrape_full_catalog_nutrition.py",
    "build_grabgo_from_catalog.py", "insert_grabgo.py",
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
    from scraper import startup_jitter
    startup_jitter()

    for script in PIPELINE:
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
    msg = "Monthly catalog + Grab & Go refresh (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
    run_git(["-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com",
             "commit", "-m", msg], check=True)
    safe_push(REPO_ROOT)


if __name__ == "__main__":
    main()

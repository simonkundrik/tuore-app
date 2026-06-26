# -*- coding: utf-8 -*-
"""Scheduled weekly job: re-run the full recipe pipeline (re-crawl K-Ruoka's
recipe catalog, remap ingredients, rebuild recipe objects) and the full
Grab & Go pipeline (re-search candidates, revisit each for nutrition/price,
rescore), idempotently replace both sections of index.html, validate, and
auto-commit+push only if validation passes and something actually changed.

Runs each pipeline stage as its own subprocess (rather than importing,
since a couple of these started life as one-off analysis scripts without
a callable main()) so a crash in one stage doesn't poison the next, and
its output is visible in the log either way."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRAPER_DIR = Path(__file__).parent

RECIPE_PIPELINE = [
    "scrape_recipes.py", "analyze_coverage.py", "select_batch.py",
    "build_kruoka_recipes.py", "insert_kruoka_recipes.py",
]
GRABGO_PIPELINE = [
    "scrape_grabgo_candidates.py", "scrape_grabgo_details.py",
    "build_grabgo.py", "insert_grabgo.py",
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
    for script in RECIPE_PIPELINE:
        run_step(script)
    for script in GRABGO_PIPELINE:
        run_step(script)

    print("\n=== validating ===")
    sys.path.insert(0, str(SCRAPER_DIR))
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
             "scraper/grabgo_recommendations.json"], check=True)
    msg = "Weekly recipe + Grab & Go refresh (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
    run_git(["-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com",
             "commit", "-m", msg], check=True)
    run_git(["push", "origin", "main"], check=True)
    print("Pushed.")


if __name__ == "__main__":
    main()

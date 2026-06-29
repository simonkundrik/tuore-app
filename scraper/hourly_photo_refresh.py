# -*- coding: utf-8 -*-
"""Scheduled hourly job: fetch a batch of up to 50 Unsplash stock photos for
recipes still missing one, patch index.html, validate, and auto-commit+push
only if validation passes and something actually changed. Capped at 50/run
to stay under Unsplash's 50-requests/hour free-tier limit with headroom.

Unsplash's API guidelines ask for non-automated use (see fetch_recipe_photos.py);
running this on an hourly cron is a deliberate, explicit exception made to
clear the existing photo backlog without manual babysitting. To keep that
exception scoped to the backlog rather than becoming a standing auto-fetcher
for every future recipe, this job removes its own crontab entry once no
recipe is left missing a photo."""
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
from git_sync import safe_push


def run_step(args):
    print(f"\n=== {' '.join(args)} ===")
    result = subprocess.run([sys.executable, *args], cwd=str(SCRAPER_DIR))
    if result.returncode != 0:
        raise RuntimeError(f"{args[0]} failed with exit code {result.returncode}")


def run_git(args, **kwargs):
    print(f"$ git {' '.join(args)}")
    return subprocess.run(["git", *args], cwd=str(REPO_ROOT), **kwargs)


def backlog_remaining():
    sys.path.insert(0, str(SCRAPER_DIR))
    import fetch_recipe_photos
    return len(fetch_recipe_photos.find_meal_ids_missing_photo())


def disable_self():
    print("\n=== backlog cleared -- removing this job's own crontab entry ===")
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [l for l in result.stdout.splitlines() if "hourly_photo_refresh.py" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    print("Done -- this job will not run again until re-scheduled manually")


def main():
    if backlog_remaining() == 0:
        print("No recipes missing a photo -- nothing to do")
        disable_self()
        return

    run_step(["fetch_recipe_photos.py", "--limit", "50"])
    run_step(["insert_recipe_photos.py"])

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
    else:
        print("\n=== committing and pushing ===")
        run_git(["add", "index.html", "scraper/recipe_stock_photos.json"], check=True)
        msg = "Hourly recipe photo refresh (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
        run_git(["-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com",
                 "commit", "-m", msg], check=True)
        safe_push(REPO_ROOT)

    if backlog_remaining() == 0:
        disable_self()


if __name__ == "__main__":
    main()

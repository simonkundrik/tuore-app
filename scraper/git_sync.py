# -*- coding: utf-8 -*-
"""Shared safe-push helper for every scraper script that auto-commits and
pushes its own output from the VM. Pulls (merge, not rebase) before
pushing so a push never silently fails just because the dev machine
pushed unrelated work in between this script's scheduled runs.

Confirmed this exact failure mode hit write_admin_status.py's cron job
for real, twice: it kept committing locally every 10 minutes but failing
to push (non-fast-forward) for over an hour each time, with nothing
surfacing the failure anywhere a human would see it until the dashboard
was checked by hand and found stale. daily_refresh.py/weekly_refresh.py/
monthly_refresh.py had the identical unprotected push and were equally
exposed, just not yet caught live."""
import subprocess


def safe_push(repo_root, branch="main"):
    """Pulls (merge) then pushes. Returns True on success. Never leaves
    the repo in a half-merged state -- if the pull itself fails (e.g. a
    real conflict, not just a routine divergence), aborts the merge and
    gives up for this run, so the next scheduled run starts from a clean
    state instead of compounding the problem."""
    pull = subprocess.run(["git", "pull", "--no-rebase", "origin", branch],
                           cwd=str(repo_root), capture_output=True, text=True)
    if pull.returncode != 0:
        print("git pull failed, aborting merge and skipping push this run:")
        print(pull.stdout, pull.stderr)
        subprocess.run(["git", "merge", "--abort"], cwd=str(repo_root))
        return False

    push = subprocess.run(["git", "push", "origin", branch],
                           cwd=str(repo_root), capture_output=True, text=True)
    if push.returncode != 0:
        print("git push failed even after a successful pull:")
        print(push.stdout, push.stderr)
        return False

    print("Pushed.")
    return True

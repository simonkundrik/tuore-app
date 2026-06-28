# -*- coding: utf-8 -*-
"""Writes admin_status.json -- a small status snapshot of every scraper
pipeline (catalog nutrition enrichment, ingredient stock/price, Grab & Go,
Sauces, recipe catalog size) for the hidden admin.html dashboard. Meant to
run every few minutes via cron so the dashboard shows near-live progress
during a long-running scrape like the catalog enrichment, not just
whatever was true the last time something finished and committed normally.

Only commits+pushes when the status actually changed since last write, so
quiet periods between scrapes don't spam the commit history."""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRAPER_DIR = Path(__file__).parent
STATUS_PATH = REPO_ROOT / "admin_status.json"


def safe_load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def mtime_iso(path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except Exception:
        return None


def catalog_status():
    path = SCRAPER_DIR / "full_catalog_raw.json"
    data = safe_load(path)
    if data is None:
        return None
    checked = sum(1 for i in data if i.get("nutritionChecked"))
    with_nutrition = sum(1 for i in data if i.get("nutrition"))
    errors = sum(1 for i in data if i.get("nutritionError"))
    return {
        "total": len(data), "checked": checked, "withNutrition": with_nutrition,
        "errors": errors, "lastFileUpdate": mtime_iso(path),
    }


def running_scrape_info():
    """Checks whether the catalog scrape is currently running, and if so,
    tails its most recently modified log file for live progress -- this is
    what makes the dashboard "near-live" rather than just a last-finished
    snapshot, without needing any server or new endpoint."""
    try:
        out = subprocess.run(["pgrep", "-f", "scrape_full_catalog_nutrition.py"],
                              capture_output=True, text=True).stdout.strip()
        running = bool(out)
    except Exception:
        running = False
    if not running:
        return {"running": False}

    logs = sorted(SCRAPER_DIR.glob("catalog_nutrition_full*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return {"running": True}
    log_path = logs[-1]
    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    progress_line = next((l for l in reversed(tail) if "this run (" in l), None)
    memory_line = next((l for l in reversed(tail) if "memory check" in l), None)
    return {
        "running": True, "logFile": log_path.name,
        "lastProgressLine": progress_line.strip() if progress_line else None,
        "lastMemoryLine": memory_line.strip() if memory_line else None,
        "logLastUpdate": mtime_iso(log_path),
    }


def stock_status():
    data = safe_load(SCRAPER_DIR / "stock_data.json")
    if data is None:
        return None
    products = data.get("products", {})
    confident = sum(1 for v in products.values() if v.get("confident"))
    no_match = sum(1 for v in products.values() if not v.get("match"))
    return {
        "scrapedAt": data.get("scrapedAt"), "total": len(products),
        "confident": confident, "noMatch": no_match,
    }


def list_status(filename):
    path = SCRAPER_DIR / filename
    data = safe_load(path)
    if data is None:
        return None
    return {"count": len(data), "lastFileUpdate": mtime_iso(path)}


def recipe_catalog_status():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    meals = len(re.findall(r"\{id:'", html))
    p_dict = len(re.findall(r'\n\w+:\{"nm":', html))
    return {"meals": meals, "pDictIngredients": p_dict}


# how long a running scrape can go with no new log line before we call it
# "stuck" rather than just slow -- generously above the longest normal gap
# (a single retried page load, or the 90s inter-batch cooldown)
STUCK_AFTER_MIN = 15


def compute_health(catalog, running):
    """Surfaces two failure modes admin.html can't tell apart from the raw
    fields alone: "stuck" (process alive, but no log progress in a long
    time -- the exact pattern that needed manual SSH diagnosis earlier in
    this project) and "idle_incomplete" (process died, e.g. the
    FailureRateGuard tripped, and nobody restarted it yet)."""
    if catalog is None:
        return {"status": "unknown", "message": "No catalog data yet"}
    remaining = catalog["total"] - catalog["checked"]

    if running and running.get("running"):
        stale_min = None
        log_update = running.get("logLastUpdate")
        if log_update:
            try:
                dt = datetime.fromisoformat(log_update)
                stale_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
            except Exception:
                pass
        if stale_min is not None and stale_min > STUCK_AFTER_MIN:
            return {"status": "stuck", "staleMinutes": round(stale_min, 1),
                    "message": f"No log progress in {stale_min:.0f} min while marked running"}
        return {"status": "running",
                "staleMinutes": round(stale_min, 1) if stale_min is not None else None,
                "message": "Healthy"}

    if remaining <= 0:
        return {"status": "idle_complete", "message": "All products checked"}
    return {"status": "idle_incomplete", "remaining": remaining,
            "message": f"Not running, {remaining} product(s) still need checking"}


def main():
    status = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "catalogNutrition": catalog_status(),
        "runningScrape": running_scrape_info(),
        "ingredientStock": stock_status(),
        "grabAndGo": list_status("grabgo_recommendations.json"),
        "sauces": list_status("sauces_recommendations.json"),
        "recipeCatalog": recipe_catalog_status(),
    }
    status["scrapeHealth"] = compute_health(status["catalogNutrition"], status["runningScrape"])

    old = safe_load(STATUS_PATH)
    # skip the commit if nothing meaningful changed since last write --
    # generatedAt always differs, so compare everything else
    comparable_old = {k: v for k, v in (old or {}).items() if k != "generatedAt"}
    comparable_new = {k: v for k, v in status.items() if k != "generatedAt"}
    if comparable_old == comparable_new:
        print("No change since last status write -- skipping commit")
        return

    json.dump(status, open(STATUS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Wrote {STATUS_PATH}")

    subprocess.run(["git", "add", "admin_status.json"], cwd=str(REPO_ROOT), check=True)
    msg = "Update admin status snapshot (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
    result = subprocess.run(
        ["git", "-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com", "commit", "-m", msg],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("Nothing to commit:", result.stdout, result.stderr)
        return
    subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO_ROOT), check=True)
    print("Pushed.")


if __name__ == "__main__":
    main()

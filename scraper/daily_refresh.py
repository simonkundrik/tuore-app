# -*- coding: utf-8 -*-
"""Scheduled daily job: re-scrape stock/price/alternates for the 109
P-dict ingredients, patch index.html, validate, and auto-commit+push only
if validation passes and something actually changed. Designed to run
unattended via cron on the Oracle VM -- never pushes broken data, never
creates empty commits."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRAPER_DIR = Path(__file__).parent

sys.path.insert(0, str(SCRAPER_DIR))
from git_sync import safe_push


def run(cmd, **kwargs):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(kwargs.pop('cwd', REPO_ROOT)), **kwargs)


def main():
    print("=== daily_refresh: scraping fresh stock data ===")
    from scraper import (launch_chrome, ensure_store_selected, raw_search, pick_best_match,
                          startup_jitter, jittered_wait, FailureRateGuard)
    from playwright.sync_api import sync_playwright
    import json
    from datetime import datetime, timezone

    startup_jitter()

    all_defs = json.load(open(SCRAPER_DIR / "all_search_defs.json", encoding="utf-8"))
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9333")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            guard = FailureRateGuard(max_failure_rate=0.4, min_samples=15)
            products = {}
            for i, (key, ing) in enumerate(all_defs.items(), 1):
                candidates = raw_search(page, ing["search"])
                match, confident = pick_best_match(candidates, ing["include"], ing["exclude"])
                guard.record(match is not None)
                passing = [c for c in candidates
                           if any(kw.lower() in c["name"].lower() for kw in ing["include"])
                           and not any(kw.lower() in c["name"].lower() for kw in ing["exclude"])]
                alts = [c for c in passing if match is None or c["ean"] != match["ean"]][:2]
                products[key] = {"match": match, "confident": confident,
                                  "searchTerm": ing["search"], "alternates": alts}
                if i % 25 == 0:
                    print(f"  {i}/{len(all_defs)}")
                jittered_wait(page, 300, 700)

            stock_path = SCRAPER_DIR / "stock_data.json"
            existing = json.load(open(stock_path, encoding="utf-8"))
            existing["products"] = products
            existing["scrapedAt"] = datetime.now(timezone.utc).isoformat()
            json.dump(existing, open(stock_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"Saved {stock_path}")
    finally:
        chrome_proc.terminate()

    print("\n=== patching P dict ===")
    import patch_p_dict
    changed = patch_p_dict.main()
    if not changed:
        print("No updates applied -- nothing to validate or commit")
        return

    print("\n=== validating ===")
    import validate_index
    ok, errors = validate_index.validate()
    if not ok:
        print("VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        print("Reverting index.html, not committing")
        run(["git", "checkout", "--", "index.html"])
        sys.exit(1)
    print("OK")

    print("\n=== checking for actual changes ===")
    diff = run(["git", "diff", "--quiet", "--", "index.html"])
    if diff.returncode == 0:
        print("No changes to index.html (scrape matched existing data) -- nothing to commit")
        return

    print("\n=== committing and pushing ===")
    run(["git", "add", "index.html", "scraper/stock_data.json"], check=True)
    msg = "Daily stock/price refresh (automated)\n\nCo-Authored-By: Tuore Scraper <noreply@example.com>"
    run(["git", "-c", "user.name=Tuore Scraper", "-c", "user.email=you@example.com",
         "commit", "-m", msg], check=True)
    safe_push(REPO_ROOT)


if __name__ == "__main__":
    main()

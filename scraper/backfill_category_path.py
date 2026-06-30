# -*- coding: utf-8 -*-
"""Backfills K-Ruoka's own real category path (e.g.
"leivat-keksit-ja-leivonnaiset/leivat/nakkileivat-ja-hapankorput") onto
each product already in full_catalog_raw.json, for the subset of products
build_grabgo_from_catalog.py actually draws from. Resumable -- only looks
up EANs still missing a path -- so it's cheap to run as part of the
monthly catalog refresh too, where it'll only ever see genuinely new
products after this first backfill.

Real feedback: classify_group() in build_grabgo_from_catalog.py was
guessing a product's real type (bread vs cookie vs pastry vs savory
snack) from keywords in its name, and kept missing items a human would
classify correctly at a glance (bread without "leipä" in its name, etc).
K-Ruoka's own search API already returns each product's full category
tree, including exactly this distinction (live-confirmed: "leivat" /
"nakkileivat-ja-hapankorput" / "suolaiset-valipalat" / "leivonnaiset" /
"keksit-ja-pikkuleivat" / "riisikakut" are real, separate subcategories
under the single broad "leivat-keksit-ja-leivonnaiset" top category) --
classifying off that directly is far more reliable than reconstructing
it from product names.

Doesn't touch the category-crawl-and-scroll machinery in
scrape_full_catalog.py at all (that approach turned out fragile -- a
live test run found 0 results for a whole category, which would have
silently wiped its existing data before a safety guard was added).
Instead, reuses the proven EAN-search-and-match pattern from
refresh_grabgo_prices.py: search the bare EAN, take the exact match,
read product.category.path directly from that response. Same batch +
Chrome-restart + checkpoint resilience after a first unbatched test
run of a different script lost progress on a dropped CDP connection."""
import json
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
from scraper import launch_chrome, ensure_store_selected, startup_jitter, jittered_wait, FailureRateGuard
from playwright.sync_api import sync_playwright

CATALOG_PATH = SCRAPER_DIR / "full_catalog_raw.json"
CATEGORY_GROUPS = {
    'hedelmat-ja-vihannekset', 'maito-juusto-munat-ja-rasvat',
    'leivat-keksit-ja-leivonnaiset', 'makeiset-ja-naposteltavat', 'valmisruoka',
}
BATCH_SIZE = 100
MAX_BATCH_RETRIES = 3


def search_category_path(page, ean):
    results = []

    def on_response(response):
        if "product-search/" in response.url and "suggestions" not in response.url:
            try:
                results.append(response.json())
            except Exception:
                pass

    page.on("response", on_response)
    page.goto(f"https://www.k-ruoka.fi/kauppa/tuotehaku?haku={ean}", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    page.remove_listener("response", on_response)

    if not results:
        return None
    for hit in results[0].get("result", []):
        p = hit.get("product", {})
        if p.get("ean") == ean:
            return p.get("category", {}).get("path")
    return None


def process_batch(batch, guard):
    chrome_proc = launch_chrome()
    found = 0
    processed = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9333")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            for item in batch:
                path = search_category_path(page, item['ean'])
                guard.record(path is not None)
                if path:
                    item['categoryPath'] = path
                    found += 1
                processed += 1
                jittered_wait(page, 300, 700)
    except Exception as e:
        print(f"  batch interrupted after {processed}/{len(batch)}: {e}")
    finally:
        chrome_proc.terminate()
    return found, processed


def main():
    startup_jitter()
    catalog = json.load(open(CATALOG_PATH, encoding="utf-8"))
    by_ean = {item['ean']: item for item in catalog}

    todo = [item for item in catalog if item.get('categorySlug') in CATEGORY_GROUPS
            and item.get('nutrition') and item.get('price') is not None and item.get('unitPrice')
            and not item.get('categoryPath')]
    print(f"{len(todo)} relevant products still need a category path")

    guard = FailureRateGuard(max_failure_rate=0.4, min_samples=20)
    remaining = list(todo)
    total_found = 0

    while remaining:
        batch = remaining[:BATCH_SIZE]
        retries = 0
        while True:
            print(f"\n=== batch of {len(batch)}, {len(remaining)} remaining overall ===")
            found, processed = process_batch(batch, guard)
            total_found += found
            remaining = remaining[len(batch):] if processed == len(batch) else batch[processed:] + remaining[len(batch):]
            json.dump(list(by_ean.values()), open(CATALOG_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  {found} found this batch, {total_found} total so far, {len(remaining)} left; checkpoint saved")
            if processed == len(batch):
                break
            retries += 1
            if retries >= MAX_BATCH_RETRIES:
                print(f"  gave up on this batch after {retries} retries -- "
                      f"{len(remaining)} items left without a category path, will retry next run")
                remaining = remaining[len(batch) - processed:]
                break
            batch = batch[processed:]

    print(f"\nFinished: {total_found}/{len(todo)} products got a category path")


if __name__ == "__main__":
    main()

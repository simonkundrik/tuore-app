# -*- coding: utf-8 -*-
"""Weekly: refreshes price/stock for the existing Grab & Go list (built by
build_grabgo_from_catalog.py from the full catalog nutrition snapshot)
without re-scraping nutrition -- nutrition facts don't change week to
week, but price and stock genuinely do (K-Ruoka's weekly campaign-price
rotation), which is the whole reason Grab & Go runs on a weekly cadence
at all.

Looks each item up by EAN via the same raw_search() free-text search
already used elsewhere (confirmed live: searching the bare EAN string
returns that exact product as the top hit) -- much lighter than visiting
each product's own detail page, since this only needs price/stock, not
the nutrition panel. Items no longer in stock are dropped; items no
longer found at all (delisted) are dropped too. Value-related badges
('Great value') are recomputed since they depend on price; health-related
badges are left as-is since nutrition didn't change.

A live test run of the first version of this script crashed mid-batch
(TargetClosedError -- the CDP connection died) around item 150/896 with
no checkpointing, losing all progress. Fixed with the same shape of fix
scrape_full_catalog_nutrition.py already uses for its much heavier job:
process in batches, restart Chrome between them, and checkpoint to disk
after every batch so a crash loses at most one batch's worth of work
rather than the whole run."""
import json
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
from scraper import launch_chrome, ensure_store_selected, raw_search, startup_jitter, jittered_wait, FailureRateGuard
from playwright.sync_api import sync_playwright

DATA_PATH = SCRAPER_DIR / "grabgo_recommendations.json"
BATCH_SIZE = 100
MAX_BATCH_RETRIES = 3


def percentile_rank(value, all_values, lower_is_better=False):
    if not all_values:
        return 50
    sorted_vals = sorted(all_values, reverse=lower_is_better)
    better_count = sum(1 for v in sorted_vals if (v <= value if lower_is_better else v >= value))
    return round(100 * (1 - better_count / len(sorted_vals)) + 100 / len(sorted_vals))


def recompute_badges(item):
    n = item
    badges = []
    if item['healthPct'] >= 75:
        badges.append('Healthy pick')
    if item['valuePct'] >= 75 and len(badges) < 2:
        badges.append('Great value')
    if (n.get('protein100') or 0) >= 12 and len(badges) < 2:
        badges.append('High protein')
    if (n.get('sugar100') or 0) <= 3 and len(badges) < 2:
        badges.append('Low sugar')
    if not badges:
        badges.append('Worth a look')
    item['badges'] = badges[:2]


def process_batch(batch, guard):
    """Refreshes price/stock for one batch under a single Chrome session.
    Returns (kept, processed_count) -- processed_count < len(batch) means
    Chrome died partway, so the caller knows which items still need a
    retry rather than assuming the whole batch finished."""
    chrome_proc = launch_chrome()
    kept = []
    processed = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9333")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            for item in batch:
                candidates = raw_search(page, item['ean'])
                match = next((c for c in candidates if c['ean'] == item['ean']), None)
                guard.record(match is not None)
                if match and match.get('inStockAtStore'):
                    item['price'] = match['price']
                    item['unit'] = match.get('unit')
                    item['unitPrice'] = match.get('unitPrice')
                    item['unitPriceUnit'] = match.get('unitPriceUnit')
                    kept.append(item)
                processed += 1
                jittered_wait(page, 300, 700)
    except Exception as e:
        print(f"  batch interrupted after {processed}/{len(batch)}: {e}")
    finally:
        chrome_proc.terminate()
    return kept, processed


def checkpoint(kept_so_far, not_yet_processed):
    # not-yet-processed items keep whatever price/stock they already had
    # from last week -- stale, but never worse than dropping them outright
    json.dump(kept_so_far + not_yet_processed, open(DATA_PATH, "w", encoding="utf-8"), ensure_ascii=False)


def main():
    startup_jitter()
    items = json.load(open(DATA_PATH, encoding="utf-8"))
    print(f"Refreshing price/stock for {len(items)} items")

    guard = FailureRateGuard(max_failure_rate=0.4, min_samples=20)
    kept = []
    remaining = list(items)

    while remaining:
        batch = remaining[:BATCH_SIZE]
        retries = 0
        while True:
            print(f"\n=== batch of {len(batch)}, {len(remaining)} remaining overall ===")
            batch_kept, processed = process_batch(batch, guard)
            kept.extend(batch_kept)
            remaining = remaining[len(batch):] if processed == len(batch) else batch[processed:] + remaining[len(batch):]
            checkpoint(kept, remaining)
            print(f"  {len(kept)} kept so far, {len(remaining)} left to check")
            if processed == len(batch):
                break
            retries += 1
            if retries >= MAX_BATCH_RETRIES:
                print(f"  gave up on this batch after {retries} retries -- "
                      f"{len(remaining)} items left with stale price/stock, will retry next run")
                remaining = remaining[len(batch) - processed:]
                break
            batch = batch[processed:]

    print(f"\nFinished checking; {len(kept)} confirmed in stock, "
          f"{len(items) - len(kept) - len(remaining)} delisted/out of stock, "
          f"{len(remaining)} left unchecked (stale)")

    final = kept + remaining
    prices = [i['unitPrice'] for i in final if i.get('unitPrice')]
    for item in final:
        if item.get('unitPrice'):
            item['valuePct'] = percentile_rank(item['unitPrice'], prices, lower_is_better=True)
        recompute_badges(item)

    json.dump(final, open(DATA_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Saved {DATA_PATH} ({len(final)} total items)")


if __name__ == "__main__":
    main()

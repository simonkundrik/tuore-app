# -*- coding: utf-8 -*-
"""Enriches full_catalog_raw.json (7,266 products, name/price/stock only)
with nutrition + ingredients text, visiting each product's own detail page
-- same parsing as scrape_grabgo_details.py/scrape_sauces_details.py, at
catalog scale. This is by far the heaviest single scrape this project has
run, so it's deliberately paced harder than the others:

- Processes in fixed-size batches with a cooldown between them, rather
  than one continuous multi-hour session.
- Saves the whole catalog back to disk after every batch, not just at
  the end -- a crash or interruption loses at most one batch's worth of
  work, not hours of it.
- Resumable: skips any product already marked nutritionChecked, so
  re-running (after a crash, or split across days) picks up where it
  left off instead of starting over.
- Uses the shared startup_jitter/jittered_wait/FailureRateGuard from
  scraper.py.
- Self-healing against memory creep: restarts Chrome every batch
  regardless, AND checks available memory/swap every MEMORY_CHECK_EVERY
  items, ending the current batch early (well before the 400-item
  boundary) the moment swap has grown too much *since this Chrome
  session started* (not an absolute threshold -- the VM's baseline swap
  usage drifts over time for reasons unrelated to this script, e.g.
  376MB resting swap was observed right after a fresh Chrome launch on
  2026-06-28, which made an earlier absolute-300MB threshold fire on
  almost every batch and throttle the run far below even the original
  degraded pace). Discovered live: a single Chrome session running
  5.5+ hours across thousands of page loads pushed VM swap past 500MB,
  degrading pace from ~800 items/20min to ~100 items/30min with no hard
  errors -- nothing for the FailureRateGuard to catch, since pages were
  still loading, just slower. This check catches that pattern
  automatically instead of needing a human to notice the slowdown.
- Does NOT block images/fonts/media, even though we only ever read
  page.inner_text("body") and never anything visual -- tried that
  (2026-06-28) to cut load time/memory, and every single page load
  immediately started timing out at domcontentloaded. Unlike Budget
  Bytes, k-ruoka.fi sits behind Cloudflare specifically, and a real
  browser that mysteriously stops loading most of its own page's
  resources is exactly the kind of behavioral signal bot detection on a
  protected site can act on, even though the JS-visible fingerprint
  (navigator.*, automation flags) never changed. Reverted; the memory/
  pace work here is limited to things that don't touch network behavior
  (Chrome's own background-service flags, the per-batch memory check).

Run with an optional --limit N to do a bounded test batch first."""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from scraper import (launch_chrome, ensure_store_selected, startup_jitter, jittered_wait,
                      FailureRateGuard, get_memory_stats)
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
CATALOG_PATH = Path(__file__).parent / "full_catalog_raw.json"
BATCH_SIZE = 400
COOLDOWN_SECONDS = 90
CHECKPOINT_EVERY = 100
MEMORY_CHECK_EVERY = 25
MIN_AVAILABLE_MB = 250
MAX_SWAP_GROWTH_MB = 200  # vs the swap level measured right after this Chrome session launched


def parse_ingredients_text(text):
    idx = text.find('Ainesosat')
    if idx == -1:
        return None
    block = text[idx + len('Ainesosat'):idx + len('Ainesosat') + 1500]
    end = len(block)
    for marker in ('Allergeenit', 'E-koodit', 'Alkuperämaa', 'Ravintosisältö'):
        m = block.find(marker)
        if m != -1:
            end = min(end, m)
    ingredients = block[:end].strip()
    return ingredients or None


def fetch_off_data(ean):
    try:
        url = (f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
               f"?fields=nutriments,ingredients_text_fi,ingredients_text")
        req = urllib.request.Request(url, headers={"User-Agent": "TuoreApp/1.0 (personal recipe app)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get("status") != 1:
            return None, None
        product = data.get("product", {})
        n = product.get("nutriments", {})
        kcal = n.get("energy-kcal_100g")
        nutrition = None
        if kcal is not None:
            nutrition = {
                'kcal100': kcal, 'fat100': n.get('fat_100g'), 'fatSat100': n.get('saturated-fat_100g'),
                'carbs100': n.get('carbohydrates_100g'), 'sugar100': n.get('sugars_100g'),
                'fiber100': n.get('fiber_100g'), 'protein100': n.get('proteins_100g'),
                'salt100': n.get('salt_100g'),
            }
        ingredients = product.get('ingredients_text_fi') or product.get('ingredients_text') or None
        return nutrition, ingredients
    except Exception:
        return None, None


def fi_num(s):
    return float(s.replace(',', '.').replace(' ', ''))


def parse_nutrition(text):
    idx = text.find('Ravintosisältö')
    if idx == -1:
        return None
    block = text[idx:idx + 700]
    if 'Energia' not in block:
        return None

    def grab(pattern):
        m = re.search(pattern, block)
        return fi_num(m.group(1)) if m else None

    kcal = grab(r'Energia\s*[\d\s]+kJ\s*/\s*([\d,]+)\s*kcal')
    fat = grab(r'(?<!tyydyttynyttä\t)Rasva\s*([\d,]+)\s*g')
    fat_sat = grab(r'josta tyydyttynyttä\s*([\d,]+)\s*g')
    carbs = grab(r'Hiilihydraatit\s*([\d,]+)\s*g')
    sugar = grab(r'josta sokereita\s*([\d,]+)\s*g')
    fiber = grab(r'Ravintokuitu\s*([\d,]+)\s*g')
    protein = grab(r'Proteiini\s*([\d,]+)\s*g')
    salt = grab(r'Suola\s*([\d,]+)\s*g')
    if kcal is None or protein is None:
        return None
    return {
        'kcal100': kcal, 'fat100': fat, 'fatSat100': fat_sat, 'carbs100': carbs,
        'sugar100': sugar, 'fiber100': fiber, 'protein100': protein, 'salt100': salt,
    }


def load_product_page(page, ean):
    page.goto(f"https://www.k-ruoka.fi/kauppa/tuote/x-{ean}", wait_until="domcontentloaded", timeout=15000)
    jittered_wait(page, 300, 600)
    try:
        page.get_by_text("Ravintosisältö", exact=True).first.click(timeout=4000)
        page.wait_for_timeout(500)
    except Exception:
        pass
    try:
        page.get_by_text("Tuotetiedot", exact=True).first.click(timeout=3000)
        page.wait_for_timeout(400)
    except Exception:
        pass
    return page.inner_text("body")


def process_item(page, item):
    ean = item['ean']
    try:
        text = load_product_page(page, ean)
    except Exception as e1:
        # one retry after a short pause -- distinguishes a real block
        # (fails again) from a one-off network/render hiccup (succeeds)
        print(f"  retrying {ean} after error: {e1}")
        time.sleep(2)
        try:
            text = load_product_page(page, ean)
        except Exception as e2:
            print(f"  FAILED {ean} (retry also failed): {e2}")
            item['nutritionChecked'] = True
            item['nutritionError'] = str(e2)
            return False

    nutrition = parse_nutrition(text)
    ingredients_text = parse_ingredients_text(text)
    off_used = False
    if not nutrition or not ingredients_text:
        off_nutrition, off_ingredients = fetch_off_data(ean)
        if not nutrition and off_nutrition:
            nutrition = off_nutrition
            off_used = True
        if not ingredients_text and off_ingredients:
            ingredients_text = off_ingredients
        time.sleep(0.3)

    item['nutrition'] = nutrition
    item['nutritionSource'] = 'openfoodfacts' if off_used else ('kruoka' if nutrition else None)
    item['ingredientsText'] = ingredients_text
    item['nutritionChecked'] = True
    # the page loaded and we got a real product page -- whether nutrition
    # data actually exists for this specific product is a separate
    # question (niche brands genuinely lack it on both K-Ruoka and OFF)
    # and varies naturally by category, so it's not a sign of blocking.
    # the guard should only fire on real technical failures (the except
    # branch above), not on "this product has no nutrition panel".
    return True


def main():
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    startup_jitter()
    catalog = json.load(open(CATALOG_PATH, encoding="utf-8"))
    todo = [i for i, item in enumerate(catalog) if not item.get('nutritionChecked')]
    print(f"{len(catalog)} total products, {len(todo)} still need nutrition")
    if limit:
        todo = todo[:limit]
        print(f"--limit {limit}: processing only {len(todo)} this run")

    # A fresh Chrome process per batch, not one Chrome for the whole
    # multi-hour run -- a long-lived Chrome session's memory usage creeps
    # up over thousands of page navigations, eventually pushing the VM
    # into swap and silently degrading every subsequent page load (this
    # is exactly what happened: pace dropped from ~800 items/20min to
    # ~100 items/30min as swap usage climbed past 500MB). Restarting
    # Chrome every batch keeps memory bounded regardless of total run
    # length, at the cost of one extra ~5-10s launch per batch.
    #
    # `pos` (not a fixed batch slice) tracks overall progress, so a batch
    # that ends early on memory pressure doesn't skip or duplicate work --
    # the next batch just picks up exactly where this one stopped.
    pos = 0
    done_this_run = 0
    while pos < len(todo):
        chrome_proc = launch_chrome()
        batch_processed = 0
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
                ctx = browser.contexts[0]
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                ensure_store_selected(page)
                _, baseline_swap = get_memory_stats()

                guard = FailureRateGuard(max_failure_rate=0.3, min_samples=15)
                while pos < len(todo) and batch_processed < BATCH_SIZE:
                    idx = todo[pos]
                    ok = process_item(page, catalog[idx])
                    guard.record(ok)
                    pos += 1
                    batch_processed += 1
                    done_this_run += 1

                    if done_this_run % 25 == 0:
                        with_nutrition = sum(1 for i in todo[:pos] if catalog[i].get('nutrition'))
                        print(f"  {done_this_run}/{len(todo)} this run "
                              f"({with_nutrition}/{pos} with nutrition so far)")
                    # checkpoint every CHECKPOINT_EVERY items, not just once
                    # per (much larger) batch -- a crash mid-batch should
                    # lose at most this many items' worth of work, not 400
                    if done_this_run % CHECKPOINT_EVERY == 0:
                        json.dump(catalog, open(CATALOG_PATH, "w", encoding="utf-8"), ensure_ascii=False)
                        print(f"Checkpoint saved after {done_this_run}/{len(todo)} this run")
                    # self-healing memory check: end this batch early (well
                    # before the BATCH_SIZE boundary) the moment available
                    # memory/swap crosses a threshold, rather than waiting
                    # for a human to notice the pace has degraded
                    if done_this_run % MEMORY_CHECK_EVERY == 0:
                        avail, swap = get_memory_stats()
                        if avail is not None:
                            growth = (swap - baseline_swap) if baseline_swap is not None else 0
                            print(f"  memory check: available={avail:.0f}MB swap={swap:.0f}MB "
                                  f"(+{growth:.0f}MB since this Chrome session launched)")
                            if avail < MIN_AVAILABLE_MB or growth > MAX_SWAP_GROWTH_MB:
                                print("  memory pressure detected -- ending this batch early to restart Chrome")
                                break
        finally:
            chrome_proc.terminate()

        json.dump(catalog, open(CATALOG_PATH, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"Checkpoint saved after {done_this_run}/{len(todo)}")

        if pos < len(todo):
            print(f"Cooldown {COOLDOWN_SECONDS}s before next batch...")
            time.sleep(COOLDOWN_SECONDS)

    total_with_nutrition = sum(1 for item in catalog if item.get('nutrition'))
    print(f"\nDone. {total_with_nutrition}/{len(catalog)} products now have nutrition data.")


if __name__ == "__main__":
    main()

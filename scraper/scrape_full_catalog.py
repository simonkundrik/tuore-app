# -*- coding: utf-8 -*-
"""Crawls every product across the store's 13 real food categories
(everything except 'Juomat' [drinks] and the non-food departments like
pets/cosmetics/electronics), via the same kr-api/v2/product-search/
endpoint raw_search() already uses for free-text search -- just
parameterized by categoryPath instead of a query string.

Confirmed by testing: a direct fetch() to this endpoint -- even issued
from inside the already-loaded page's own JS context -- gets rejected
with a 409 "Client version is too old" (the same protection
scrape_recipes.py's docstring already documents: the endpoint expects
a client-version header/cookie the page's own JS sets up during real
hydration, which a synthetic fetch bypasses). Also confirmed: a plain
page.goto() to a category's URL only renders a bare SPA shell (this
site's category routing needs real client-side navigation, not a
fresh page load).

So this uses the exact same scroll-and-capture pattern already proven
reliable for the full recipe catalog (scrape_recipes.py): click into
the category via the site's own "Tuoteryhmät" panel, then scroll to
trigger the SPA's own pagination requests, capturing each one's
product-search response as it naturally happens.

This is the broad listing pass only (name/EAN/price/stock/category) --
nutrition enrichment is a separate, much more expensive step layered
on top, since OFF-first + K-Ruoka-fallback across ~7,300 products is
realistically hours, not something to run as part of the regular
weekly refresh. Intended for a separate, slower (monthly) cadence."""
import json
import time
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
OUT_PATH = Path(__file__).parent / "full_catalog_raw.json"
MAX_SCROLLS = 150
STALL_LIMIT = 6

# confirmed via live survey on 2026-06-27 -- excludes 'Juomat' (drinks)
# and non-food departments (pets, cosmetics, electronics, etc.). Finnish
# label text must match the category panel's tab text exactly (substring
# match) for the click-by-text lookup to find the right tab.
CATEGORIES = [
    "Hedelmät ja vihannekset",
    "Leivät, keksit ja leivonnaiset",
    "Liha ja kasviproteiinit",
    "Kala ja merenelävät",
    "Valmisruoka",
    "Maito, juusto, munat ja rasvat",
    "Kuivat elintarvikkeet ja leivonta",
    "Säilykkeet, keitot ja ateria-ainekset",
    "Öljyt, etikat ja salaattikastikkeet",
    "Mausteet ja maustaminen",
    "Texmex ja maailman maut",
    "Pakasteet",
    "Makeiset ja naposteltavat",
]


def extract_row(hit, category_slug, category_label_fi):
    p = hit.get("product", {})
    pricing = p.get("mobilescan", {}).get("pricing", {}).get("normal", {})
    return {
        "ean": p.get("ean"),
        "name": p.get("localizedName", {}).get("finnish") or "",
        "brand": p.get("brand", {}).get("name"),
        "price": pricing.get("price"),
        "unit": pricing.get("unit"),
        "unitPrice": pricing.get("unitPrice", {}).get("value"),
        "unitPriceUnit": pricing.get("unitPrice", {}).get("unit"),
        "inStockAtStore": p.get("availability", {}).get("store"),
        "isAvailable": p.get("isAvailable"),
        "categorySlug": category_slug,
        "categoryLabel": category_label_fi,
    }


def crawl_category(page, label):
    """Opens the category panel, selects this category, clicks through
    to its full listing, then scrolls until no new products appear or
    the site's own reported totalHits is reached. Returns a dict keyed
    by EAN (de-duplicating any product the API repeats across pages)."""
    page.goto("https://www.k-ruoka.fi/kauppa/tuotehaku", wait_until="domcontentloaded", timeout=75000)
    page.wait_for_timeout(2000)
    page.eval_on_selector(".product-categories-label-desktop",
                           "el => el.closest('button, [role=button], a')?.click() || el.click()")
    page.wait_for_timeout(1500)
    tab_clicked = page.evaluate(f"""() => {{
        const tabs = Array.from(document.querySelectorAll('button[role=tab]'));
        const t = tabs.find(e => e.textContent.includes({label!r}));
        if (t) {{ t.click(); return true; }}
        return false;
    }}""")
    if not tab_clicked:
        print(f"  WARNING: could not find tab for {label!r}, skipping")
        return {}, 0
    page.wait_for_timeout(1200)

    products = {}
    total_hits = None
    category_slug = None

    def on_response(response):
        nonlocal total_hits, category_slug
        if "product-search" not in response.url or "categoryPath" not in response.url:
            return
        try:
            data = response.json()
        except Exception:
            return
        if total_hits is None:
            total_hits = data.get("totalHits")
            category_slug = data.get("categoryPath")
        for hit in data.get("result", []):
            row = extract_row(hit, category_slug, label)
            if row["ean"]:
                products[row["ean"]] = row

    page.on("response", on_response)
    page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('a'));
        const target = all.find(e => e.textContent.trim() === 'Näytä kaikki');
        if (target) target.click();
    }""")
    page.wait_for_timeout(3000)

    stall = 0
    last_count = 0
    for i in range(MAX_SCROLLS):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(700)
        if len(products) == last_count:
            stall += 1
            if stall >= STALL_LIMIT:
                break
        else:
            stall = 0
        last_count = len(products)
        if total_hits and len(products) >= total_hits:
            break

    page.remove_listener("response", on_response)
    return products, total_hits


def main():
    chrome_proc = launch_chrome()
    all_products = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            for label in CATEGORIES:
                products, total_hits = crawl_category(page, label)
                all_products.update(products)
                print(f"{label}: collected {len(products)} (site reports totalHits={total_hits})")

            print(f"\nTotal unique products across all categories: {len(all_products)}")
            json.dump(list(all_products.values()), open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"Saved {OUT_PATH}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

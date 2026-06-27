# -*- coding: utf-8 -*-
"""Crawls every product across the store's 13 real food categories
(everything except 'Juomat' [drinks] and the non-food departments like
pets/cosmetics/electronics), via the same kr-api/v2/product-search/
endpoint raw_search() already uses for free-text search -- just
parameterized by categoryPath instead of a query string, with
pagination (each category typically has hundreds of products, far more
than fit on one page).

Unlike a normal page navigation to a category URL (which only renders a
bare shell -- this SPA's category routing needs real client-side nav,
confirmed by testing), pagination is done via a direct fetch() call
issued from inside the already-loaded page's JS context. This reuses
the same session/cookies/Cloudflare clearance the page itself has
without needing to click through the category UI for every single
page -- only the categories themselves need confirming once (already
done; see CATEGORIES below), not every offset within them.

This is the broad, infrequent (monthly) full-catalog pass: it gets
name/EAN/price/category/stock for everything, cheaply. Nutrition is a
separate, much more expensive step (build_full_catalog.py) layered on
top of this raw listing, not fetched here."""
import json
import time
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, STORE_ID
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
OUT_PATH = Path(__file__).parent / "full_catalog_raw.json"
PAGE_LIMIT = 100

# confirmed via live survey on 2026-06-27 -- excludes 'Juomat' (drinks)
# and non-food departments (pets, cosmetics, electronics, etc.)
CATEGORIES = {
    "hedelmat-ja-vihannekset": "Hedelmät ja vihannekset",
    "leivat-keksit-ja-leivonnaiset": "Leivät, keksit ja leivonnaiset",
    "liha-ja-kasviproteiinit": "Liha ja kasviproteiinit",
    "kala-ja-merenelavat": "Kala ja merenelävät",
    "valmisruoka": "Valmisruoka",
    "maito-juusto-munat-ja-rasvat": "Maito, juusto, munat ja rasvat",
    "kuivat-elintarvikkeet-ja-leivonta": "Kuivat elintarvikkeet ja leivonta",
    "sailykkeet-keitot-ja-ateria-ainekset": "Säilykkeet, keitot ja ateria-ainekset",
    "oljyt-etikat-ja-salaattikastikkeet": "Öljyt, etikat ja salaattikastikkeet",
    "mausteet-ja-maustaminen": "Mausteet ja maustaminen",
    "texmex-ja-maailman-maut": "Texmex ja maailman maut",
    "pakasteet": "Pakasteet",
    "makeiset-ja-naposteltavat": "Makeiset ja naposteltavat",
}


def fetch_category_page(page, category_slug, offset):
    url = (f"https://www.k-ruoka.fi/kr-api/v2/product-search/"
           f"?offset={offset}&language=fi&categoryPath={category_slug}"
           f"&storeId={STORE_ID}&limit={PAGE_LIMIT}&discountFilter=false&isTosTrOffer=false")
    return page.evaluate(
        "(url) => fetch(url, {credentials: 'include'}).then(r => r.json())", url
    )


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


def main():
    chrome_proc = launch_chrome()
    all_products = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            for slug, label in CATEGORIES.items():
                offset = 0
                total_hits = None
                category_count = 0
                while total_hits is None or offset < total_hits:
                    data = fetch_category_page(page, slug, offset)
                    if total_hits is None:
                        total_hits = data.get("totalHits", 0)
                        print(f"{label} ({slug}): totalHits={total_hits}")
                    hits = data.get("result", [])
                    if not hits:
                        break
                    for hit in hits:
                        row = extract_row(hit, slug, label)
                        ean = row["ean"]
                        if ean:
                            all_products[ean] = row
                            category_count += 1
                    offset += PAGE_LIMIT
                    page.wait_for_timeout(400)
                print(f"  -> collected {category_count} rows")

            print(f"\nTotal unique products across all categories: {len(all_products)}")
            json.dump(list(all_products.values()), open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"Saved {OUT_PATH}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

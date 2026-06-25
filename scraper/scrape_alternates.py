"""Re-scrapes all 109 ingredients, but this time keeps up to 2 real alternate
products per ingredient (different brand/size/pack that still matches the same
include/exclude filter) alongside the primary pick, so the app can fall back to
a genuinely available substitute when the primary product is out of stock."""
import json
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, raw_search, pick_best_match
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
ALL_DEFS = json.load(open(Path(__file__).parent / "all_search_defs.json", encoding="utf-8"))


def main():
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            products = {}
            for i, (key, ing) in enumerate(ALL_DEFS.items(), 1):
                candidates = raw_search(page, ing["search"])
                match, confident = pick_best_match(candidates, ing["include"], ing["exclude"])
                passing = [c for c in candidates
                           if any(kw.lower() in c["name"].lower() for kw in ing["include"])
                           and not any(kw.lower() in c["name"].lower() for kw in ing["exclude"])]
                alts = [c for c in passing if match is None or c["ean"] != match["ean"]][:2]
                products[key] = {
                    "match": match, "confident": confident, "searchTerm": ing["search"],
                    "alternates": alts,
                }
                print(f"{i:3d}/{len(ALL_DEFS)} {key:16s} primary={match['name'] if match else '-'!r:50s} "
                      f"alts={len(alts)} ({'in stock' if match and match['inStockAtStore'] else 'OUT' if match else '-'})")

            out_path = Path(__file__).parent / "stock_data.json"
            existing = json.load(open(out_path, encoding="utf-8"))
            existing["products"] = products
            from datetime import datetime, timezone
            existing["scrapedAt"] = datetime.now(timezone.utc).isoformat()
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print("\nSaved", out_path)

            no_alt_but_oos = [k for k, v in products.items()
                               if v["match"] and not v["match"]["inStockAtStore"] and not v["alternates"]]
            if no_alt_but_oos:
                print("Out of stock with NO alternate found:", no_alt_but_oos)
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

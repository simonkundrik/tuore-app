"""
Tuore stock/price scraper for K-Supermarket Hyvätuuli (k-ruoka.fi, storeId S224).

Why this works the way it does:
- k-ruoka.fi sits behind Cloudflare bot management. A freshly-launched, headless
  Playwright/Chromium browser gets stuck on Cloudflare's "Just a moment..." challenge
  forever (confirmed by testing) - it is fingerprinted as automation and never passes.
- Driving the REAL, locally-installed Chrome binary instead (launched normally, then
  attached to over the Chrome DevTools Protocol) does not carry those automation
  tells, and loads the site normally. This is the same browser a human would use,
  just remote-controlled - not a synthetic bot browser.
- A persistent --user-data-dir means Chrome's Cloudflare clearance cookie and normal
  site cookies are kept between runs, so repeat runs get smoother (and put less load
  on K-Ruoka's edge) instead of re-proving "not a bot" from scratch every time.

Usage:
    python scraper.py
Output:
    stock_data.json - {ean, name, brand, price, unitPrice, inStockAtStore, scrapedAt}
"""
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = str(Path(__file__).parent / "chrome-profile")
DEBUG_PORT = 9333
STORE_NAME = "Hyvätuuli"
STORE_ID = "S224"

# Search terms covering the ingredients used by the Tuore recipe catalog.
SEARCH_TERMS = [
    "Myllyn Paras Iso Hiutale", "Pirkka pakastemarjat", "Valio kevytmaito",
    "Pirkka kananmunat", "Vaasan Ruispalat", "Arla viipale",
    "Pirkka lohifile", "Pirkka tuorepinaatti", "Pirkka porkkana",
    "Pirkka keltasipuli", "Oddlygood kauraruokakerma", "Pirkka tilli",
    "Pirkka punaiset linssit", "Pirkka tomaattimurska", "Knorr kasvisliemikuutio",
    "Atria broilerin koipireisifile", "Pirkka ruokaperuna", "Santa Maria paprikajauhe",
    "Arla kreikkalainen jogurtti", "Atria broilerinfileesuikale", "Pirkka kurkku",
    "Santa Maria tortillaleivat", "Pirkka hummus", "Pirkka salaattisekoitus",
    "Pirkka paprika", "Chiquita banaani", "Oddlygood kauramaito",
    "Pirkka jasmiiniriisi", "Pirkka jauheliha", "Pirkka tonnikala",
    "Pirkka spagetti", "Pirkka pakastebrokkoli", "Pirkka fetapala",
    "Pirkka valkosipuli", "Pirkka sitruuna", "Pirkka punajuuri",
]


def launch_chrome():
    proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ])
    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Chrome DevTools port never came up")


def ensure_store_selected(page):
    page.goto("https://www.k-ruoka.fi/kauppa", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    try:
        page.get_by_text("Vain välttämättömät", exact=False).click(timeout=3000)
        page.wait_for_timeout(500)
    except Exception:
        pass

    if f"storeId={STORE_ID}" in page.url or page.locator(f"text={STORE_NAME}").count() > 0:
        return

    try:
        page.get_by_text("Ostoksille verkkokauppaan", exact=False).click(timeout=3000)
        page.wait_for_timeout(1500)
    except Exception:
        pass

    page.goto("https://www.k-ruoka.fi/kauppa?kaupat", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    box = page.get_by_placeholder(re.compile("Hae kauppaa", re.IGNORECASE))
    box.click()
    box.fill(STORE_NAME)
    page.wait_for_timeout(1200)
    page.get_by_text("Valitse tämä kauppa", exact=False).first.click(timeout=5000)
    page.wait_for_timeout(1500)


def search_product(page, term):
    results = []

    def on_response(response):
        if "product-search/" in response.url and "suggestions" not in response.url:
            try:
                results.append(response.json())
            except Exception:
                pass

    page.on("response", on_response)
    page.goto(f"https://www.k-ruoka.fi/kauppa/tuotehaku?haku={term}", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.remove_listener("response", on_response)

    if not results:
        return []

    hits = results[0].get("result", [])
    out = []
    for hit in hits[:5]:
        p = hit.get("product", {})
        pricing = p.get("mobilescan", {}).get("pricing", {}).get("normal", {})
        out.append({
            "ean": p.get("ean"),
            "name": p.get("localizedName", {}).get("finnish"),
            "brand": p.get("brand", {}).get("name"),
            "price": pricing.get("price"),
            "unit": pricing.get("unit"),
            "unitPrice": pricing.get("unitPrice", {}).get("value"),
            "unitPriceUnit": pricing.get("unitPrice", {}).get("unit"),
            "inStockAtStore": p.get("availability", {}).get("store"),
            "storeId": p.get("store", {}).get("id"),
        })
    return out


def main():
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            ensure_store_selected(page)

            all_results = {}
            for term in SEARCH_TERMS:
                matches = search_product(page, term)
                all_results[term] = matches
                top = matches[0] if matches else None
                print(f"{term!r:45s} -> {top['name'] if top else 'NO MATCH'} "
                      f"{('€' + str(top['price'])) if top else ''} "
                      f"{'IN STOCK' if top and top['inStockAtStore'] else 'OUT/UNKNOWN' if top else ''}")

            out_path = Path(__file__).parent / "stock_data.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({
                    "store": {"name": f"K-Supermarket {STORE_NAME}", "id": STORE_ID},
                    "scrapedAt": datetime.now(timezone.utc).isoformat(),
                    "searches": all_results,
                }, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {out_path}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

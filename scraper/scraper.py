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

Matching strategy:
- Free-text search ranks by relevance, not by what we actually meant - "Pirkka
  pakastebrokkoli" can come back top-ranked as washed potatoes. Each ingredient
  below carries required/excluded keywords; we scan the top results and pick the
  first one that actually satisfies them, and flag it "uncertain" if none do
  (falling back to the top hit) so a bad match is visible rather than silent.

Usage:
    python scraper.py
Output:
    stock_data.json - one row per app ingredient key with product, price, and
    in-store availability for K-Supermarket Hyvätuuli.
"""
import atexit
import json
import os
import platform
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

IS_WINDOWS = platform.system() == "Windows"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe" if IS_WINDOWS else "/usr/bin/google-chrome-stable"
PROFILE_DIR = str(Path(__file__).parent / "chrome-profile")
DEBUG_PORT = 9333
XVFB_DISPLAY = ":99"
STORE_NAME = "Hyvätuuli"
STORE_ID = "S224"

# key matches the product id used in the app's data model (see index.html's P dict).
# include/exclude keywords are matched against the Finnish product name, lowercased.
INGREDIENTS = [
    {"key": "oats",         "search": "Myllyn Paras hiutale",         "include": ["hiutale"],      "exclude": []},
    {"key": "berries",      "search": "pakastemarjat",                "include": ["marja"],         "exclude": []},
    {"key": "milk",         "search": "kevytmaito",                   "include": ["maito"],         "exclude": ["kaura"]},
    {"key": "eggs",         "search": "kananmunat",                   "include": ["kananmuna"],     "exclude": []},
    {"key": "bread",        "search": "ruispalat",                    "include": ["ruisp"],         "exclude": []},
    {"key": "cheese",       "search": "juustoviipale",                "include": ["viipale"],       "exclude": []},
    {"key": "salmon",       "search": "lohifile",                     "include": ["lohi"],          "exclude": []},
    {"key": "spinach",      "search": "tuorepinaatti",                "include": ["pinaatti"],      "exclude": []},
    {"key": "carrot",       "search": "porkkana",                     "include": ["porkkana"],      "exclude": []},
    {"key": "onion",        "search": "keltasipuli",                  "include": ["sipuli"],        "exclude": ["valkosipuli"]},
    {"key": "oatcream",     "search": "kauraruokakerma",              "include": ["kerma"],         "exclude": []},
    {"key": "dill",         "search": "tilli",                        "include": ["tilli"],         "exclude": []},
    {"key": "lentils",      "search": "punaiset linssit",             "include": ["linssi"],        "exclude": []},
    {"key": "tomato",       "search": "tomaattimurska",               "include": ["tomaattimurska"],"exclude": []},
    {"key": "stockcube",    "search": "kasvisliemikuutio",            "include": ["liemikuutio"],   "exclude": []},
    {"key": "chicken",      "search": "broilerin koipireisifile",     "include": ["koipireisi"],    "exclude": []},
    {"key": "potato",       "search": "ruokaperuna",                  "include": ["peruna"],        "exclude": []},
    {"key": "paprika",      "search": "paprikajauhe",                 "include": ["paprikajauhe"],  "exclude": []},
    {"key": "yogurt",       "search": "kreikkalainen jogurtti",       "include": ["jogurtti"],      "exclude": []},
    {"key": "cookedchicken","search": "broilerinfileesuikale",        "include": ["suikale"],       "exclude": []},
    {"key": "cucumber",     "search": "kurkku",                       "include": ["kurkku"],        "exclude": ["mauste", "viipaleet"]},
    {"key": "tortilla",     "search": "tortillaleivat",               "include": ["tortilla"],      "exclude": []},
    {"key": "hummus",       "search": "hummus",                       "include": ["hummus"],        "exclude": []},
    {"key": "salad",        "search": "salaattisekoitus",             "include": ["salaatti"],      "exclude": []},
    {"key": "pepper",       "search": "paprika",                      "include": ["paprika"],       "exclude": ["jauhe", "murska"]},
    {"key": "banana",       "search": "banaani",                      "include": ["banaani"],       "exclude": []},
    {"key": "plantmilk",    "search": "kauramaito",                   "include": ["kauramaito"],    "exclude": []},
    {"key": "rice",         "search": "jasmiiniriisi",                "include": ["riisi"],         "exclude": []},
    {"key": "mince",        "search": "naudan jauheliha",             "include": ["jauheliha"],     "exclude": []},
    {"key": "tuna",         "search": "tonnikala",                    "include": ["tonnikala"],     "exclude": []},
    {"key": "pasta",        "search": "spagetti",                     "include": ["spagetti"],      "exclude": ["jauheliha"]},
    {"key": "broccoli",     "search": "pakastebrokkoli",              "include": ["brokkoli"],      "exclude": []},
    {"key": "feta",         "search": "fetapala",                     "include": ["feta"],          "exclude": []},
    {"key": "garlic",       "search": "valkosipuli",                  "include": ["valkosipuli"],   "exclude": ["murska", "tomaatti"]},
    {"key": "lemon",        "search": "sitruuna",                     "include": ["sitruuna"],      "exclude": ["vesi", "kivennäis"]},
    {"key": "beetroot",     "search": "punajuuri",                    "include": ["punajuuri"],     "exclude": ["salaatti"]},
    {"key": "oliveoil",     "search": "oliiviöljy",                   "include": ["oliiviöljy"],    "exclude": []},
]


def _ensure_xvfb():
    """On a headless Linux box (the Oracle VM) Chrome needs a real display to
    run non-headlessly -- Xvfb fakes one. Windows has a real display already."""
    lock_file = Path(f"/tmp/.X99-lock")
    if lock_file.exists():
        return  # already running from a previous/concurrent launch
    xvfb_proc = subprocess.Popen(
        ["Xvfb", XVFB_DISPLAY, "-screen", "0", "1280x800x24"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    atexit.register(xvfb_proc.terminate)
    time.sleep(2)


def launch_chrome():
    env = None
    extra_flags = []
    if not IS_WINDOWS:
        _ensure_xvfb()
        env = {**os.environ, "DISPLAY": XVFB_DISPLAY}
        extra_flags = ["--disable-gpu", "--disable-dev-shm-usage"]
    proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        *extra_flags,
        "about:blank",
    ], env=env)
    for _ in range(90):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Chrome DevTools port never came up")


def dismiss_cookie_banner(page):
    """The OneTrust consent banner blocks pointer events on everything
    beneath it until dismissed. A profile that's already consented once
    (e.g. the long-lived local dev profile) never sees it again, but a
    fresh profile (a new VM, a clean chrome-profile dir) hits it -- and it
    mounts asynchronously, sometimes a couple seconds after page load, so
    a one-shot `.count()` check right after navigation is a race: it can
    read 0 a moment before the banner actually appears. Use Playwright's
    own wait_for instead of polling .count() on a guess."""
    reject_btn = page.locator("#onetrust-reject-all-handler")
    try:
        reject_btn.wait_for(state="visible", timeout=6000)
    except Exception:
        return  # banner never showed up -- nothing to dismiss
    try:
        reject_btn.click(timeout=3000)
        page.locator("#onetrust-consent-sdk").wait_for(state="hidden", timeout=3000)
    except Exception:
        pass


def ensure_store_selected(page):
    page.goto("https://www.k-ruoka.fi/kauppa", wait_until="domcontentloaded", timeout=75000)
    page.wait_for_timeout(1500)
    dismiss_cookie_banner(page)

    if f"storeId={STORE_ID}" in page.url or page.locator(f"text={STORE_NAME}").count() > 0:
        return

    try:
        page.get_by_text("Ostoksille verkkokauppaan", exact=False).click(timeout=3000)
        page.wait_for_timeout(1500)
    except Exception:
        pass

    page.goto("https://www.k-ruoka.fi/kauppa?kaupat", wait_until="domcontentloaded", timeout=75000)
    page.wait_for_timeout(1000)
    dismiss_cookie_banner(page)
    box = page.get_by_placeholder(re.compile("Hae kauppaa", re.IGNORECASE))
    box.click()
    box.fill(STORE_NAME)
    page.wait_for_timeout(1200)
    page.get_by_text("Valitse tämä kauppa", exact=False).first.click(timeout=5000)
    page.wait_for_timeout(1500)


def raw_search(page, term):
    results = []

    def on_response(response):
        if "product-search/" in response.url and "suggestions" not in response.url:
            try:
                results.append(response.json())
            except Exception:
                pass

    page.on("response", on_response)
    page.goto(f"https://www.k-ruoka.fi/kauppa/tuotehaku?haku={term}", wait_until="domcontentloaded", timeout=75000)
    page.wait_for_timeout(2500)
    page.remove_listener("response", on_response)

    if not results:
        return []

    hits = results[0].get("result", [])
    out = []
    for hit in hits[:10]:
        p = hit.get("product", {})
        pricing = p.get("mobilescan", {}).get("pricing", {}).get("normal", {})
        out.append({
            "ean": p.get("ean"),
            "name": p.get("localizedName", {}).get("finnish") or "",
            "brand": p.get("brand", {}).get("name"),
            "price": pricing.get("price"),
            "unit": pricing.get("unit"),
            "unitPrice": pricing.get("unitPrice", {}).get("value"),
            "unitPriceUnit": pricing.get("unitPrice", {}).get("unit"),
            "inStockAtStore": p.get("availability", {}).get("store"),
            "storeId": p.get("store", {}).get("id"),
        })
    return out


def pick_best_match(candidates, include, exclude):
    for c in candidates:
        name = c["name"].lower()
        if any(kw.lower() in name for kw in include) and not any(kw.lower() in name for kw in exclude):
            return c, True
    return (candidates[0], False) if candidates else (None, False)


def main():
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            ensure_store_selected(page)

            products = {}
            for ing in INGREDIENTS:
                candidates = raw_search(page, ing["search"])
                match, confident = pick_best_match(candidates, ing["include"], ing["exclude"])
                products[ing["key"]] = {
                    "match": match,
                    "confident": confident,
                    "searchTerm": ing["search"],
                }
                status = "OK" if confident else ("UNCERTAIN" if match else "NO MATCH")
                print(f"{ing['key']:14s} [{status:9s}] -> {match['name'] if match else '-'} "
                      f"{('€' + str(match['price'])) if match else ''} "
                      f"{'IN STOCK' if match and match['inStockAtStore'] else 'OUT' if match else ''}")

            out_path = Path(__file__).parent / "stock_data.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({
                    "store": {"name": f"K-Supermarket {STORE_NAME}", "id": STORE_ID},
                    "scrapedAt": datetime.now(timezone.utc).isoformat(),
                    "products": products,
                }, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {out_path}")

            uncertain = [k for k, v in products.items() if v["match"] and not v["confident"]]
            missing = [k for k, v in products.items() if not v["match"]]
            if uncertain:
                print(f"Uncertain matches (verify manually): {uncertain}")
            if missing:
                print(f"No match at all: {missing}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

"""Crawls k-ruoka.fi's recipe search API (kr-api/v1/search) to pull the full
catalog of real Finnish recipes -- name, structured ingredient list, real
per-serving macros, prep time, diet tags, and recipe photo id.

Drives genuine scroll events on the live /reseptit page (rather than calling
the API directly) because the endpoint rejects bare fetches with a
"Client version is too old" 409 -- it expects whatever client-version
header/cookie the page's own JS sets up during real hydration. Scrolling
makes the site's own code fire the requests, which we just listen for.

Keeps 'instructions' (K-Ruoka's own written cooking steps) in the raw dump
for our own reference/QA only -- recipes_raw.json is gitignored and never
committed; only a derived, translated, ingredients-mapped subset with our
own freshly-written steps goes into the repo (see build_recipes.py)."""
import json
import time
from pathlib import Path
from scraper import launch_chrome
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
OUT_PATH = Path(__file__).parent / "recipes_raw.json"
MAX_SCROLLS = 220
STALL_LIMIT = 6


def main():
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            recipes = {}
            total_hits = None

            def on_response(response):
                nonlocal total_hits
                if "/kr-api/v1/search" not in response.url:
                    return
                try:
                    body = response.json()
                except Exception:
                    return
                if total_hits is None:
                    total_hits = body.get("totalHits")
                for item in body.get("result", []):
                    r = item.get("recipe", {})
                    rid = r.get("recipeId")
                    if rid and rid not in recipes:
                        recipes[rid] = r

            page.on("response", on_response)
            page.goto("https://www.k-ruoka.fi/reseptit", wait_until="networkidle")
            page.wait_for_timeout(1500)

            stall = 0
            last_count = 0
            for i in range(MAX_SCROLLS):
                page.mouse.wheel(0, 4500)
                page.wait_for_timeout(550)
                if i % 10 == 0:
                    print(f"scroll {i}: {len(recipes)} unique recipes so far (totalHits={total_hits})")
                if len(recipes) == last_count:
                    stall += 1
                    if stall >= STALL_LIMIT:
                        print(f"no new recipes for {STALL_LIMIT} scrolls in a row, stopping")
                        break
                else:
                    stall = 0
                last_count = len(recipes)
                if total_hits and len(recipes) >= total_hits:
                    print("reached totalHits, stopping")
                    break

            print(f"\nDone. {len(recipes)} unique recipes collected (site reports totalHits={total_hits})")
            with open(OUT_PATH, "w", encoding="utf-8") as f:
                json.dump(list(recipes.values()), f, ensure_ascii=False)
            print(f"Saved {OUT_PATH}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

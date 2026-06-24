import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333


def wait_for_cdp():
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json/version", timeout=1)
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("CDP never came up")


def main():
    wait_for_cdp()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.k-ruoka.fi/", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        title = page.title()
        body_snippet = page.inner_text("body")[:300]
        page.screenshot(path="scraper/cf_test_screenshot.png")

        blocked = "Just a moment" in title or "moment" in title.lower() or "Cloudflare" in body_snippet

        result = {
            "title": title,
            "blocked_by_cloudflare": blocked,
            "body_snippet": body_snippet,
            "tested_from": "github-actions-runner",
        }
        with open("scraper/cf_test_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

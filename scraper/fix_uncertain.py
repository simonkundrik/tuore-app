import json
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, raw_search, pick_best_match
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333

FIXES = [
    {"key": "chicken",   "search": "koipireisi",        "include": ["koipireisi"], "exclude": []},
    {"key": "plantmilk", "search": "kauramaito",         "include": ["kauramaito", "kaurajuoma"], "exclude": []},
    {"key": "broccoli",  "search": "brokkoli",           "include": ["brokkoli"],  "exclude": []},
]


def main():
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            out_path = Path(__file__).parent / "stock_data.json"
            data = json.load(open(out_path, encoding="utf-8"))

            for fix in FIXES:
                candidates = raw_search(page, fix["search"])
                match, confident = pick_best_match(candidates, fix["include"], fix["exclude"])
                data["products"][fix["key"]] = {"match": match, "confident": confident, "searchTerm": fix["search"]}
                print(fix["key"], "->", match["name"] if match else "NO MATCH", "confident:", confident)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("patched", out_path)
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

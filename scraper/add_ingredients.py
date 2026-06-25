import json
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, raw_search, pick_best_match
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333

NEW_INGREDIENTS = [
    {"key": "mushroom",     "search": "herkkusieni",   "include": ["sieni"],                  "exclude": []},
    {"key": "sweetpotato",  "search": "bataatti",       "include": ["bataatti"],               "exclude": []},
    {"key": "halloumi",     "search": "halloumi",       "include": ["halloumi"],               "exclude": []},
    {"key": "prawns",       "search": "katkarapu",      "include": ["katkarapu"],              "exclude": []},
    {"key": "coconutmilk",  "search": "kookosmaito",    "include": ["kookosmaito"],            "exclude": []},
    {"key": "currypaste",   "search": "currytahna",     "include": ["curry"],                  "exclude": []},
    {"key": "leek",         "search": "purjo",          "include": ["purjo"],                  "exclude": []},
    {"key": "soysauce",     "search": "soijakastike",   "include": ["soija"],                  "exclude": []},
    {"key": "peanutbutter", "search": "maapähkinävoi",  "include": ["pähkinävoi"],             "exclude": []},
    {"key": "quinoa",       "search": "quinoa",         "include": ["quinoa", "kvinoa"],       "exclude": []},
    {"key": "chorizo",      "search": "chorizo",        "include": ["chorizo"],                "exclude": []},
    {"key": "pita",         "search": "pitaleipä",      "include": ["pita"],                   "exclude": []},
    {"key": "avocado",      "search": "avokado",        "include": ["avokado"],                "exclude": []},
    {"key": "rahka",        "search": "rahka",          "include": ["rahka"],                  "exclude": []},
    {"key": "apple",        "search": "omena",          "include": ["omena"],                  "exclude": []},
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

            for ing in NEW_INGREDIENTS:
                candidates = raw_search(page, ing["search"])
                match, confident = pick_best_match(candidates, ing["include"], ing["exclude"])
                data["products"][ing["key"]] = {"match": match, "confident": confident, "searchTerm": ing["search"]}
                status = "OK" if confident else ("UNCERTAIN" if match else "NO MATCH")
                print(f"{ing['key']:14s} [{status:9s}] -> {match['name'] if match else '-'} "
                      f"{('€' + str(match['price'])) if match else ''}")

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("saved", out_path)
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

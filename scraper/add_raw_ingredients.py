import json
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, raw_search, pick_best_match
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333

NEW_INGREDIENTS = [
    {"key": "beef",         "search": "naudan ulkofile",  "include": ["ulkofile"],            "exclude": []},
    {"key": "pork",         "search": "porsaan sisäfile", "include": ["sisäfile"],            "exclude": []},
    {"key": "whitefish",    "search": "kalafile",         "include": ["kala"],                 "exclude": []},
    {"key": "sausage",      "search": "nakki",            "include": ["nakki"],                "exclude": []},
    {"key": "bacon",        "search": "pekoni",           "include": ["pekoni"],               "exclude": []},
    {"key": "tofu",         "search": "tofu",             "include": ["tofu"],                 "exclude": []},
    {"key": "cream",        "search": "ruokakerma",       "include": ["ruokakerma"],           "exclude": ["kaura"]},
    {"key": "butter",       "search": "Valio voi",        "include": ["voi"],                  "exclude": ["pähkinävoi"]},
    {"key": "mozzarella",   "search": "mozzarella",       "include": ["mozzarella"],           "exclude": []},
    {"key": "freshtomato",  "search": "tomaatti",         "include": ["tomaatti"],             "exclude": ["murska", "kastike", "mehu"]},
    {"key": "cabbage",      "search": "valkokaali",       "include": ["valkokaali"],           "exclude": []},
    {"key": "cauliflower",  "search": "kukkakaali",       "include": ["kukkakaali"],           "exclude": []},
    {"key": "eggplant",     "search": "munakoiso",        "include": ["munakoiso"],            "exclude": []},
    {"key": "zucchini",     "search": "kesäkurpitsa",     "include": ["kesäkurpitsa"],         "exclude": []},
    {"key": "sweetcorn",    "search": "maissi",           "include": ["maissi"],               "exclude": ["naksu", "popcorn"]},
    {"key": "peas",         "search": "herne",            "include": ["herne"],                "exclude": ["keitto"]},
    {"key": "orange",       "search": "appelsiini",       "include": ["appelsiini"],           "exclude": []},
    {"key": "blueberries",  "search": "mustikka",         "include": ["mustikka"],             "exclude": ["mehu", "jogurtti"]},
    {"key": "strawberries", "search": "mansikka",         "include": ["mansikka"],             "exclude": ["jogurtti", "mehu"]},
    {"key": "chickpeas",    "search": "kikherne",         "include": ["kikherne"],             "exclude": []},
    {"key": "couscous",     "search": "couscous",         "include": ["couscous", "kuskus"],   "exclude": []},
    {"key": "blackbeans",   "search": "mustapapu",        "include": ["papu"],                 "exclude": []},
    {"key": "basil",        "search": "basilika",         "include": ["basilika"],             "exclude": []},
    {"key": "parsley",      "search": "persilja",         "include": ["persilja"],             "exclude": []},
    {"key": "cumin",        "search": "juustokumina",     "include": ["kumina"],               "exclude": []},
    {"key": "cinnamon",     "search": "kaneli",           "include": ["kaneli"],               "exclude": []},
    {"key": "chiliflakes",  "search": "chilihiutale",     "include": ["chili"],                "exclude": []},
    {"key": "honey",        "search": "hunaja",           "include": ["hunaja"],               "exclude": []},
    {"key": "vinegar",      "search": "viinietikka",      "include": ["etikka"],               "exclude": []},
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

import json
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, raw_search, pick_best_match
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333

NEW_INGREDIENTS = [
    {"key": "turkey",       "search": "kalkkuna",          "include": ["kalkkuna"],    "exclude": []},
    {"key": "lamb",         "search": "karitsan ulkofile",  "include": ["karitsa"],     "exclude": []},
    {"key": "herring",      "search": "silakka",           "include": ["silakka"],     "exclude": []},
    {"key": "mussels",      "search": "simpukka",          "include": ["simpukka"],    "exclude": []},
    {"key": "parmesan",     "search": "parmesan",          "include": ["parmesan"],    "exclude": []},
    {"key": "ricotta",      "search": "ricotta",           "include": ["ricotta"],     "exclude": []},
    {"key": "skyr",         "search": "skyr",              "include": ["skyr"],        "exclude": []},
    {"key": "radish",       "search": "retiisi",           "include": ["retiisi"],     "exclude": []},
    {"key": "fennel",       "search": "fenkoli",           "include": ["fenkoli"],     "exclude": []},
    {"key": "asparagus",    "search": "parsa",             "include": ["parsa"],       "exclude": []},
    {"key": "kale",         "search": "lehtikaali",        "include": ["lehtikaali"],  "exclude": []},
    {"key": "rutabaga",     "search": "lanttu",            "include": ["lanttu"],      "exclude": []},
    {"key": "pumpkin",      "search": "kurpitsa",          "include": ["kurpitsa"],    "exclude": ["kesäkurpitsa"]},
    {"key": "barley",       "search": "ohrasuurimo",       "include": ["ohra"],        "exclude": []},
    {"key": "buckwheat",    "search": "tattari",           "include": ["tattari"],     "exclude": []},
    {"key": "breadcrumbs",  "search": "korppujauho",       "include": ["korppujauho"], "exclude": []},
    {"key": "pineapple",    "search": "ananas",            "include": ["ananas"],      "exclude": []},
    {"key": "mango",        "search": "mango",             "include": ["mango"],       "exclude": []},
    {"key": "raspberries",  "search": "vadelma",           "include": ["vadelma"],     "exclude": ["jogurtti", "mehu"]},
    {"key": "almonds",      "search": "manteli",           "include": ["manteli"],     "exclude": []},
    {"key": "walnuts",      "search": "saksanpähkinä",     "include": ["saksanpähkinä"], "exclude": []},
    {"key": "sesameseeds",  "search": "seesaminsiemen",    "include": ["seesami"],     "exclude": []},
    {"key": "pesto",        "search": "pesto",             "include": ["pesto"],       "exclude": []},
    {"key": "mayo",         "search": "majoneesi",         "include": ["majoneesi"],   "exclude": []},
    {"key": "tahini",       "search": "tahini",            "include": ["tahini"],      "exclude": []},
    {"key": "flour",        "search": "vehnäjauho",        "include": ["jauho"],       "exclude": []},
    {"key": "vanilla",      "search": "vaniljasokeri",     "include": ["vanilja"],     "exclude": []},
    {"key": "darkchocolate","search": "tumma suklaa",      "include": ["suklaa"],      "exclude": []},
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

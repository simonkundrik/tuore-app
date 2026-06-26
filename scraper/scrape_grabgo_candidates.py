# -*- coding: utf-8 -*-
"""Stage 1 of the grab-and-go pipeline: gather candidate ready-to-eat
products (name/price/ean/brand) via the same free-text product search
already proven reliable for ingredient scraping (raw_search), using
curated Finnish search terms per food group."""
import json
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected, raw_search
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
OUT_PATH = Path(__file__).parent / "grabgo_candidates_raw.json"

SEARCH_TERMS = {
    "fresh_fruit": ["banaani", "omena", "appelsiini", "päärynä", "mandariini",
                    "mango", "ananas", "vesimeloni", "viinirypäle", "kiivi"],
    "berries": ["mansikka", "mustikka", "vadelma", "karpalo", "marjasekoitus"],
    "raw_veg_snack": ["minikurkku", "cocktailtomaatti", "kirsikkatomaatti",
                       "minipaprika", "porkkanaviipale"],
    "dairy_snack": ["jogurtti", "skyr", "raejuusto", "kefir"],
    "ready_meals": ["mikroateria", "salaattiateria", "wrap", "kebab",
                     "hampurilainen", "hotdog", "pizza", "kolmioleipä", "paniini",
                     "mikrokeitto"],
    "nuts_snacks": ["manteli", "pähkinä", "cashew", "pistaasi", "snackpähkinä"],
    "dips": ["hummus", "guacamole", "tahinidippi"],
    "healthy_snacks": ["proteiinipatukka", "proteiinisipsit", "kasvissipsit",
                        "proteiinipallot", "riisikakku"],
}


def main():
    chrome_proc = launch_chrome()
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            candidates = {}
            for group, terms in SEARCH_TERMS.items():
                for term in terms:
                    hits = raw_search(page, term)
                    n_new = 0
                    for h in hits:
                        ean = h.get("ean")
                        if not ean:
                            continue
                        if ean not in candidates:
                            candidates[ean] = h
                            candidates[ean]["group"] = group
                            candidates[ean]["searchTerm"] = term
                            n_new += 1
                    print(f"{group:18s} {term:20s} -> {len(hits):2d} hits, {n_new:2d} new")

            print(f"\nTotal unique candidates: {len(candidates)}")
            json.dump(list(candidates.values()), open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"Saved {OUT_PATH}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()

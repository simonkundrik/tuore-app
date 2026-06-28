# -*- coding: utf-8 -*-
"""Turns real Fork To Spoon air-fryer recipes (forktospoon_airfryer_raw.json,
scraped JSON-LD) into Tuore recipes. Same no-text-copied policy as
build_airfryer_recipes.py: the real recipe name is kept (a fact), every
step sentence is freshly written.

Unlike the Budget Bytes batches, this site carries no aggregateRating at
all (confirmed by sampling several pages before scraping) -- there is no
review-count/rating gate available. "Healthy" here is enforced entirely
through nutrition thresholds instead: a calorie cap, plus saturated fat
and sodium caps using the richer nutrition fields this site's schema
exposes that Budget Bytes' didn't.

Every recipe in this raw file came from the site's own air-fryer
category, so equip is set to ['airfryer'] directly rather than inferred --
no archetype classifier needed for cooking method here."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from recipe_lib import (existing_ids, make_id, price_per_serving, is_vegan, is_veg,
    is_lowcarb, is_lowfat, is_lowcal, BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR, protein_icon, MEAT_FISH)
from build_airfryer_recipes import (clean_ingredient, match_ingredient, parse_iso_minutes,
    parse_yield, parse_num, frac_for, air_fryer_steps, real_temp_c, PROTEIN_TEMP_DEFAULT)
from generate_from_foodcom import PROTEIN_SET, VEGAN_PROTEIN, veg_of, has_body

# "protein" in this codebase's PROTEIN_SET includes eggs, which defeats any
# dessert filter that just checks "no protein" -- nearly every baked treat
# (cupcakes, brittle, cinnamon bread) contains eggs as a binder. REAL_PROTEIN
# excludes eggs specifically so a dish needs actual meat/fish/legume protein
# or a real vegetable to count as a savory "real meal" body.
REAL_PROTEIN = MEAT_FISH | VEGAN_PROTEIN
DESSERT_SIGNAL = {'vanilla', 'darkchocolate', 'honey', 'peanutbutter', 'cinnamon', 'walnuts',
    'almonds', 'oats', 'apple', 'orange', 'banana', 'blueberries', 'strawberries',
    'raspberries', 'mango', 'pineapple'}
# backstop for desserts the ingredient-based check structurally can't catch --
# things like "cake mix" or "sprinkles" aren't real products, so they map to
# nothing and leave no ingredient-level signal at all (caught live: "Air Fryer
# Cake Mix Cookies (3 Ingredients)" mapped only to eggs+oil). The recipe's own
# title is a more reliable tell here than ingredients ever could be. Bare
# "cake"/"cakes" deliberately excluded -- fish cakes, crab cakes, salmon
# cakes, rice cakes are real savory dishes.
DESSERT_NAME_WORDS = ('cookie', 'cupcake', 'cake mix', 'brittle', 'fudge', 'brownie', 'pie', 'tart',
    'candy', 'dessert', 'frosting', 'icing', 'donut', 'doughnut', "s'mores", 'smores', 'cheesecake',
    'pudding', 'custard', 'marshmallow', 'crumble', 'cobbler', 'sprinkles')
# the category crawl picked up at least one recipe for a completely different
# appliance (an 8-hour "Boiled Peanuts in Crockpot") -- the site's own
# cross-linking/recommendation widgets pull in unrelated content sometimes
WRONG_APPLIANCE_WORDS = ('crockpot', 'crock pot', 'slow cooker')

IN_PATH = Path(__file__).parent / "forktospoon_airfryer_raw.json"
OUT_PATH = Path(__file__).parent / "forktospoon_recipes.json"
MISSING_REPORT_PATH = Path(__file__).parent / "forktospoon_skipped.json"
HTML_PATH = Path(__file__).parent.parent / "index.html"

MAX_KCAL = 550
MAX_SATFAT_G = 8
MAX_SODIUM_MG = 900
MIN_MAPPED_REFS = 2
# no rating signal exists on this site to rank "best" by, and the raw pool
# (1000+) is far past the requested 300-600 -- rank everything that passed
# the health caps by how far under them it sits, and keep only the top slice
TARGET_COUNT = 600


def health_score(kcal, sat_fat, sodium, protein):
    # lower is "healthier" -- a low-sodium dessert otherwise scores
    # identically to a real protein-rich dish, so protein is subtracted to
    # pull substantial meals above light-but-empty ones at the margin
    return (kcal / MAX_KCAL) + (sat_fat or 0) / MAX_SATFAT_G + (sodium or 0) / MAX_SODIUM_MG - protein / 30


def existing_airfryer_bucket_sets(html):
    """Scoped to only existing air-fryer-tagged meals, not the whole catalog --
    these recipes are specifically meant to fill out the dedicated Air Fryer
    carousel, so an ingredient combo that's already a skillet/pasta dish
    elsewhere shouldn't block a genuinely different air-fryer version of it."""
    sets = set()
    start = html.index("\nlet meals=[") + len("\nlet meals=[")
    end = html.index("\n];\n", start)
    for chunk in html[start:end].split("{id:'")[1:]:
        if "'airfryer'" not in chunk:
            continue
        # don't require the array to be the object's last field -- K-Ruoka-
        # sourced meals have a trailing photo:'...' after ing, so a closing
        # "]}" requirement silently misses every one of them
        m = re.search(r"ing:\[(.*?)\]", chunk)
        if not m:
            continue
        refs = tuple(sorted(set(re.findall(r"ref:'(\w+)'", m.group(1)))))
        if refs:
            sets.add(refs)
    return sets


def main():
    data = json.load(open(IN_PATH, encoding="utf-8"))
    used_ids = set(existing_ids)
    html = HTML_PATH.read_text(encoding="utf-8")
    seen_buckets = existing_airfryer_bucket_sets(html)
    print(f"{len(seen_buckets)} distinct ingredient-bucket combos already in the Air Fryer carousel")

    out = []
    skipped = []

    for d in data:
        r = d["recipe"]
        name = r.get("name", "").strip()

        name_lower = name.lower()
        if any(w in name_lower for w in DESSERT_NAME_WORDS):
            skipped.append({"name": name, "reason": "dessert-coded (name)"})
            continue
        if any(w in name_lower for w in WRONG_APPLIANCE_WORDS):
            skipped.append({"name": name, "reason": "wrong appliance (not actually an air-fryer recipe)"})
            continue

        mapped_refs = []
        missing_new = set()
        unmatched = []
        for ing_line in r.get("recipeIngredient") or []:
            res = match_ingredient(ing_line)
            if res is None:
                cleaned = clean_ingredient(ing_line)
                if cleaned:
                    unmatched.append(cleaned)
                continue
            kind, val = res
            if kind == "existing" and val not in mapped_refs:
                mapped_refs.append(val)
            elif kind == "new":
                missing_new.add(val)

        if len(mapped_refs) < MIN_MAPPED_REFS:
            skipped.append({"name": name, "reason": f"only {len(mapped_refs)} real ingredient(s) in stock",
                             "mapped": mapped_refs, "missing_new_ingredients": sorted(missing_new),
                             "unmatched": unmatched})
            continue
        if not has_body(mapped_refs):
            skipped.append({"name": name, "reason": "no real protein/veg/carb/fruit body",
                             "mapped": mapped_refs, "missing_new_ingredients": sorted(missing_new),
                             "unmatched": unmatched})
            continue

        bucket_key = tuple(sorted(set(mapped_refs)))
        if bucket_key in seen_buckets:
            skipped.append({"name": name, "reason": "duplicate ingredient combo of an existing air-fryer recipe", "mapped": mapped_refs})
            continue

        n = r.get("nutrition") or {}
        kcal = parse_num(n.get("calories"))
        protein = parse_num(n.get("proteinContent"))
        carbs = parse_num(n.get("carbohydrateContent"))
        fat = parse_num(n.get("fatContent"))
        sat_fat = parse_num(n.get("saturatedFatContent"))
        sodium = parse_num(n.get("sodiumContent"))
        if kcal is None or protein is None or carbs is None or fat is None:
            skipped.append({"name": name, "reason": "missing nutrition data"})
            continue
        if kcal < 5:
            # a real single-serving dish is never under 5 kcal -- this is a
            # roundup/listicle page that happened to carry a placeholder
            # Recipe schema (caught one for real: "What To Serve With Ramen
            # (50 Ideas)", nutrition listed as "0.4 kcal"/"0.03 g protein"
            # etc. -- not literally zero, just nonsense), not an actual dish
            skipped.append({"name": name, "reason": f"placeholder nutrition, not a real recipe ({kcal} kcal)"})
            continue
        if kcal > MAX_KCAL:
            skipped.append({"name": name, "reason": f"too calorie-dense ({kcal} kcal/serving)"})
            continue
        if sat_fat is not None and sat_fat > MAX_SATFAT_G:
            skipped.append({"name": name, "reason": f"too much saturated fat ({sat_fat} g/serving)"})
            continue
        if sodium is not None and sodium > MAX_SODIUM_MG:
            skipped.append({"name": name, "reason": f"too much sodium ({sodium} mg/serving)"})
            continue

        refset = set(mapped_refs)
        has_protein_ref = bool(refset & PROTEIN_SET)
        has_veg_ref = bool(veg_of(refset))
        has_real_body = bool(refset & REAL_PROTEIN) or has_veg_ref
        if bool(refset & DESSERT_SIGNAL) and not has_real_body:
            skipped.append({"name": name, "reason": "dessert-coded (sweet ingredient, no real protein/veg body)"})
            continue
        if not has_protein_ref and not has_veg_ref and carbs >= 25 and fat >= 15:
            skipped.append({"name": name, "reason": "treat-like (no protein/veg, high carb+fat)"})
            continue

        servings = parse_yield(r.get("recipeYield")) or 2
        time = parse_iso_minutes(r.get("totalTime"))
        if not time:
            time = (parse_iso_minutes(r.get("prepTime")) or 5) + (parse_iso_minutes(r.get("cookTime")) or 15)
        cook_min = parse_iso_minutes(r.get("cookTime")) or time

        lead_protein = next((ref for ref in mapped_refs if ref in PROTEIN_SET), None)
        default_temp = PROTEIN_TEMP_DEFAULT.get(lead_protein, 200)
        temp_c = real_temp_c(r, default_temp)

        ing = [{"ref": ref, "frac": frac_for(ref)} for ref in mapped_refs]
        pps = price_per_serving([(i["ref"], i["frac"]) for i in ing], servings)

        filters = []
        tags = []
        if is_vegan(mapped_refs):
            filters.append("vegan"); tags.append("Vegan")
        elif is_veg(mapped_refs):
            filters.append("veg"); tags.append("Vegetarian")
        if has_protein_ref and protein >= 18:
            filters.append("protein"); tags.append("Protein")
        if is_lowcarb(mapped_refs):
            filters.append("lowcarb"); tags.append("Low-carb")
        if time <= 15:
            filters.append("quick"); tags.append("Quick")
        if is_lowfat(fat):
            filters.append("lowfat")
        if is_lowcal(kcal):
            filters.append("lowcal")
        if pps < BUDGET_MAX_EUR:
            filters.append("budget")
        if pps < VERYBUDGET_MAX_EUR:
            filters.append("verybudget")
        if not tags:
            tags = ["Quick"] if time <= 15 else ["Hearty"]
        tags = tags[:2]

        mtype = ["snack"] if (kcal < 180 and protein < 10) else ["dinner", "lunch"]
        icon = protein_icon(lead_protein) if lead_protein else ("ti-leaf" if has_veg_ref else "ti-bowl")

        slug = re.sub(r"[^a-z0-9]+", "", name.lower())
        cid = make_id(["f2s", slug], used_ids)

        seen_buckets.add(bucket_key)
        out.append({
            "id": cid, "name": name, "icon": icon, "type": mtype, "filters": filters, "tags": tags,
            "time": int(time), "protein": round(protein), "carbs": round(carbs), "fat": round(fat),
            "kcal": round(kcal), "servings": servings, "equip": ["airfryer"],
            "steps": air_fryer_steps(mapped_refs, temp_c, int(cook_min)), "ing": ing,
            "sourceUrl": d["url"],
            "_healthScore": health_score(kcal, sat_fat, sodium, protein),
        })

    print(f"{len(out)} passed all filters, skipped {len(skipped)}")
    if len(out) > TARGET_COUNT:
        out.sort(key=lambda r: r["_healthScore"])
        cut = out[TARGET_COUNT:]
        out = out[:TARGET_COUNT]
        for r in cut:
            skipped.append({"name": r["name"], "reason": f"past the {TARGET_COUNT} target (ranked by health score)"})
    for r in out:
        del r["_healthScore"]

    print(f"Keeping {len(out)} recipes (target {TARGET_COUNT})")
    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(skipped, open(MISSING_REPORT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saved {OUT_PATH}")
    print(f"Saved skip report -> {MISSING_REPORT_PATH}")
    from collections import Counter
    print("skip reasons:", Counter(re.sub(r"\(.*?\)", "", s["reason"]).strip() for s in skipped))


if __name__ == "__main__":
    main()

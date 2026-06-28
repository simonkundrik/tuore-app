# -*- coding: utf-8 -*-
"""Turns real, rating-validated Budget Bytes "Quick" recipes
(budgetbytes_quick_raw.json, scraped JSON-LD) into Tuore recipes. No text
is copied from Budget Bytes -- the real recipe NAME is kept (a fact, same
precedent as build_airfryer_recipes.py), but every step sentence is
freshly written by the same archetype-aware step generator already used
for the ~800 Food.com-derived recipes (data/generate_from_foodcom.py's
classify()/gen_steps()), driven only by which *real* ingredients (mapped
to the existing P dict) the dish actually uses.

Ingredients that aren't a real K-Supermarket Hyvätuuli product are
dropped; if too few real ingredients remain, the whole recipe is skipped.
Also skipped if its real ingredient-bucket already matches an existing
meal already in index.html -- two pipelines now draw from the same
~110-ingredient pool, so without this check a "Quick" recipe could
generate a near-duplicate of something the Food.com batch already added."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from recipe_lib import (existing_ids, FRAC, is_vegan, is_veg, is_lowcarb,
    price_per_serving, make_id, is_lowfat, is_lowcal, BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR)
from generate_from_foodcom import classify, gen_steps, icon_for, ARCHETYPE_TYPE, has_body, PROTEIN_SET
from build_airfryer_recipes import clean_ingredient, match_ingredient, parse_iso_minutes, parse_yield, parse_num

IN_PATH = Path(__file__).parent / "budgetbytes_quick_raw.json"
OUT_PATH = Path(__file__).parent / "quick_recipes.json"
MISSING_REPORT_PATH = Path(__file__).parent / "quick_skipped.json"
HTML_PATH = Path(__file__).parent.parent / "index.html"

DEFAULT_FRAC = 0.3
RATING_MIN = 4.0
MIN_RATING_COUNT = 5
MAX_KCAL = 700
MAX_MINUTES = 40
MIN_MAPPED_REFS = 2

# classify() only sees the ingredient bucket, not the real method -- it defaults
# a many-vegetable/no-carb/no-meat combo to 'soup' and anything unmatched to
# 'skillet', both of which assume real heat is applied. Unlike the Food.com
# pipeline (bucket-only, no real instructions to check), we *do* have the
# source's real instructions here, so a no-cook recipe (a cold salad/dip) can
# be detected and steered to the 'salad' writer instead of generating fresh
# steps that tell the user to simmer a dish that's actually served cold.
NO_HEAT_OVERRIDE_FROM = {'soup', 'skillet'}
COOK_HEAT_WORDS = re.compile(
    r'\b(boil|simmer|saut[ée]|fry|frying|bak(e|ing)|roast|grill|cook(ing|ed)?|heat(ing)?|'
    r'microwave|broil|steam|poach|sear|toast(ing)?|blanch)\w*\b', re.IGNORECASE)


def frac_for(ref):
    return FRAC.get(ref, DEFAULT_FRAC)


def instructions_text(r):
    return ' '.join(s.get('text', '') for s in (r.get('recipeInstructions') or []) if isinstance(s, dict))


def existing_bucket_sets(html):
    sets = set()
    # don't require the array to be the object's last field -- K-Ruoka-sourced
    # meals have a trailing photo:'...' after ing, so a closing "]}"
    # requirement silently misses every one of them
    for m in re.finditer(r"ing:\[(.*?)\]", html):
        refs = tuple(sorted(set(re.findall(r"ref:'(\w+)'", m.group(1)))))
        if refs:
            sets.add(refs)
    return sets


def main():
    data = json.load(open(IN_PATH, encoding="utf-8"))
    used_ids = set(existing_ids)
    html = HTML_PATH.read_text(encoding="utf-8")
    seen_buckets = existing_bucket_sets(html)
    print(f"{len(seen_buckets)} distinct ingredient-bucket combos already in index.html")

    out = []
    skipped = []

    for d in data:
        r = d['recipe']
        name = r.get('name', '').strip()

        rating_info = r.get('aggregateRating') or {}
        rating = parse_num(rating_info.get('ratingValue'))
        rating_count = parse_num(rating_info.get('ratingCount') or rating_info.get('reviewCount'))
        if rating is not None and rating < RATING_MIN:
            skipped.append({'name': name, 'reason': f'low rating ({rating})'})
            continue
        if rating_count is not None and rating_count < MIN_RATING_COUNT:
            skipped.append({'name': name, 'reason': f'too few reviews ({rating_count})'})
            continue

        mapped_refs = []
        missing_new = set()
        unmatched = []
        for ing_line in r.get('recipeIngredient') or []:
            res = match_ingredient(ing_line)
            if res is None:
                cleaned = clean_ingredient(ing_line)
                if cleaned:
                    unmatched.append(cleaned)
                continue
            kind, val = res
            if kind == 'existing' and val not in mapped_refs:
                mapped_refs.append(val)
            elif kind == 'new':
                missing_new.add(val)

        if len(mapped_refs) < MIN_MAPPED_REFS:
            skipped.append({'name': name, 'reason': f'only {len(mapped_refs)} real ingredient(s) in stock',
                             'mapped': mapped_refs, 'missing_new_ingredients': sorted(missing_new),
                             'unmatched': unmatched})
            continue
        if not has_body(mapped_refs):
            skipped.append({'name': name, 'reason': 'no real protein/veg/carb/fruit body -- only oil/aromatics/seasoning mapped',
                             'mapped': mapped_refs, 'missing_new_ingredients': sorted(missing_new),
                             'unmatched': unmatched})
            continue

        bucket_key = tuple(sorted(set(mapped_refs)))
        if bucket_key in seen_buckets:
            skipped.append({'name': name, 'reason': 'duplicate ingredient combo of an existing recipe', 'mapped': mapped_refs})
            continue

        n = r.get('nutrition') or {}
        kcal = parse_num(n.get('calories'))
        protein = parse_num(n.get('proteinContent'))
        carbs = parse_num(n.get('carbohydrateContent'))
        fat = parse_num(n.get('fatContent'))
        if kcal is None or protein is None or carbs is None or fat is None:
            skipped.append({'name': name, 'reason': 'missing nutrition data'})
            continue
        if kcal > MAX_KCAL:
            skipped.append({'name': name, 'reason': f'too calorie-dense ({kcal} kcal/serving)'})
            continue

        time = parse_iso_minutes(r.get('totalTime'))
        if not time:
            time = (parse_iso_minutes(r.get('prepTime')) or 5) + (parse_iso_minutes(r.get('cookTime')) or 15)
        if time > MAX_MINUTES:
            skipped.append({'name': name, 'reason': f'not actually quick ({time} min)'})
            continue

        servings = parse_yield(r.get('recipeYield')) or 2

        archetype = classify(mapped_refs)
        if archetype in NO_HEAT_OVERRIDE_FROM and not COOK_HEAT_WORDS.search(instructions_text(r)):
            archetype = 'salad'
        steps, equip = gen_steps(archetype, mapped_refs, time)
        mtype = ARCHETYPE_TYPE[archetype]
        icon = icon_for(mapped_refs, archetype)

        ing = [{'ref': ref, 'frac': frac_for(ref)} for ref in mapped_refs]
        pps = price_per_serving([(i['ref'], i['frac']) for i in ing], servings)

        filters = []
        tags = []
        if is_vegan(mapped_refs):
            filters.append('vegan'); tags.append('Vegan')
        elif is_veg(mapped_refs):
            filters.append('veg'); tags.append('Vegetarian')
        has_protein_ref = bool(set(mapped_refs) & PROTEIN_SET)
        if has_protein_ref and protein >= 18:
            filters.append('protein'); tags.append('Protein')
        if is_lowcarb(mapped_refs):
            filters.append('lowcarb'); tags.append('Low-carb')
        if time <= 15:
            filters.append('quick'); tags.append('Quick')
        if is_lowfat(fat):
            filters.append('lowfat')
        if is_lowcal(kcal):
            filters.append('lowcal')
        if pps < BUDGET_MAX_EUR:
            filters.append('budget')
        if pps < VERYBUDGET_MAX_EUR:
            filters.append('verybudget')
        if not tags:
            tags = ['Quick'] if time <= 25 else ['Hearty']
        tags = tags[:2]

        slug = re.sub(r'[^a-z0-9]+', '', name.lower())
        cid = make_id(['bbq', slug], used_ids)

        seen_buckets.add(bucket_key)
        out.append({
            'id': cid, 'name': name, 'icon': icon, 'type': mtype, 'filters': filters, 'tags': tags,
            'time': int(time), 'protein': round(protein), 'carbs': round(carbs), 'fat': round(fat),
            'kcal': round(kcal), 'servings': servings, 'equip': equip,
            'steps': steps, 'ing': ing,
            'sourceRating': rating, 'sourceUrl': d['url'],
        })

    print(f"Built {len(out)} recipes, skipped {len(skipped)}")
    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(skipped, open(MISSING_REPORT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saved {OUT_PATH}")
    print(f"Saved skip report -> {MISSING_REPORT_PATH}")
    from collections import Counter
    print('skip reasons:', Counter(re.sub(r'\(.*?\)', '', s['reason']).strip() for s in skipped))


if __name__ == "__main__":
    main()

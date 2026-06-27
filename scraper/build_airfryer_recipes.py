# -*- coding: utf-8 -*-
"""Turns real, rating-validated Budget Bytes air-fryer recipes (budgetbytes_raw.json,
scraped JSON-LD) into Tuore recipes. No text is copied from Budget Bytes -- only
facts (which real ingredients combine, real nutrition, real ratings, real cook
temp/time) inform the result; every step sentence here is freshly written.
Ingredients that aren't a real K-Supermarket Hyvätuuli product (per the existing
108-ingredient P dict) are dropped from that recipe; if too few real ingredients
remain, the whole recipe is skipped rather than shipped half-empty."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from recipe_lib import (P, existing_ids, T, Cap, M, protein_icon, FRAC,
    is_vegan, is_veg, is_lowcarb, price_per_serving, make_id,
    is_lowfat, is_lowcal, BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR)
from generate_from_foodcom import (PROTEIN_SET, AROMATIC, HERB_SPICE, FINISHING,
    DAIRY, CARBY, FRUIT, veg_of, join_names)
from canon_map import canon, SKIP, TO_EXISTING, TO_NEW

IN_PATH = Path(__file__).parent / "budgetbytes_raw.json"
OUT_PATH = Path(__file__).parent / "airfryer_recipes.json"
MISSING_REPORT_PATH = Path(__file__).parent / "airfryer_skipped.json"

DEFAULT_FRAC = 0.3
RATING_MIN = 4.0
MAX_KCAL = 550
MIN_MAPPED_REFS = 2
# numeric filters don't catch every treat -- this one passed on calories/fat but
# is a cinnamon-sugar fried dessert wrap, not in the spirit of "still healthy"
MANUAL_EXCLUDE = {'Apple Flautas'}

UNIT_WORDS = {
 'tbsp', 'tablespoon', 'tablespoons', 'tsp', 'teaspoon', 'teaspoons', 'cup', 'cups',
 'lb', 'lbs', 'pound', 'pounds', 'oz', 'ounce', 'ounces', 'g', 'gram', 'grams', 'kg',
 'ml', 'l', 'clove', 'cloves', 'can', 'cans', 'package', 'packages', 'slice', 'slices',
 'piece', 'pieces', 'stalk', 'stalks', 'sprig', 'sprigs', 'head', 'heads', 'bunch',
 'bunches', 'pinch', 'dash', 'large', 'small', 'medium', 'whole', 'fresh', 'freshly',
 'chopped', 'minced', 'diced', 'sliced', 'ground', 'crushed', 'grated', 'shredded',
 'to', 'taste', 'of', 'for', 'garnish', 'optional', 'divided', 'extra', 'or', 'and',
 'thinly', 'roughly', 'finely', 'about', 'plus', 'more',
}
ALL_KEYS_BY_LEN = sorted(set(TO_EXISTING) | set(TO_NEW), key=lambda k: (-len(k.split()), -len(k)))


def clean_ingredient(raw):
    s = raw.split('(')[0]
    s = re.sub(r'[¼-¾⅐-⅞]', ' ', s)
    s = re.sub(r'[\d/.\-–]+', ' ', s)
    s = s.lower()
    words = [w.strip(',.') for w in s.split()]
    words = [w for w in words if w and w not in UNIT_WORDS]
    return ' '.join(words).strip()


def match_ingredient(raw):
    clean = clean_ingredient(raw)
    if not clean:
        return None
    for candidate in (clean, clean[:-1] if clean.endswith('s') else clean):
        if candidate in SKIP:
            return None
        if candidate in TO_EXISTING:
            return ('existing', TO_EXISTING[candidate])
        if candidate in TO_NEW:
            return ('new', TO_NEW[candidate])
    for key in ALL_KEYS_BY_LEN:
        if re.search(r'\b' + re.escape(key) + r'\b', clean):
            res = canon(key)
            if res:
                return res
    return None


def parse_iso_minutes(s):
    if not s:
        return None
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def parse_yield(y):
    if isinstance(y, list):
        y = y[0] if y else None
    if not y:
        return None
    m = re.search(r'\d+', str(y))
    return int(m.group()) if m else None


def parse_num(s):
    if s is None:
        return None
    m = re.search(r'[\d.]+', str(s))
    return float(m.group()) if m else None


def real_temp_c(recipe, fallback):
    text = ' '.join(s.get('text', '') for s in recipe.get('recipeInstructions', []) if isinstance(s, dict))
    m = re.search(r'(\d{3})\s*º?\s*F\b', text)
    if m:
        f = int(m.group(1))
        return round((f - 32) * 5 / 9 / 5) * 5
    return fallback


def frac_for(ref):
    return FRAC.get(ref, DEFAULT_FRAC)


def air_fryer_steps(refs, temp_c, cook_min):
    refset = set(refs)
    proteins = [r for r in refs if r in PROTEIN_SET]
    vegs = [r for r in refs if r in veg_of(refset)]
    aromatics = [r for r in refs if r in AROMATIC]
    herbs = [r for r in refs if r in HERB_SPICE]
    finishing = [r for r in refs if r in FINISHING]
    dairy = [r for r in refs if r in DAIRY]
    main = proteins + vegs
    if not main:
        excluded = set(aromatics) | set(herbs) | set(finishing) | set(dairy)
        main = [r for r in refs if r not in excluded] or list(refs)
    season = aromatics + herbs
    steps = [f"Preheat the air fryer to {temp_c}°C."]
    season_txt = f" with {join_names(season)}" if season else ""
    steps.append(f"Toss the {join_names(main)}{season_txt}, season with salt and pepper.")
    cook_min = max(cook_min, 6)
    tail = (f"Air-fry at {temp_c}°C for {max(cook_min-3,3)}-{cook_min} min, "
            "shaking the basket halfway, until cooked through and crisp.")
    finish = finishing + dairy
    if finish:
        tail += f" Finish with {join_names(finish)}."
    steps.append(tail)
    return steps


PROTEIN_TEMP_DEFAULT = {'salmon': 180, 'tuna': 180, 'whitefish': 180, 'prawns': 180,
                         'mussels': 180, 'herring': 180, 'tofu': 200}


def main():
    data = json.load(open(IN_PATH, encoding="utf-8"))
    used_ids = set(existing_ids)
    out = []
    skipped = []

    for d in data:
        r = d['recipe']
        name = r.get('name', '').strip()
        if name in MANUAL_EXCLUDE:
            skipped.append({'name': name, 'reason': 'manual exclude (dessert-coded, not "still healthy")'})
            continue
        rating = (r.get('aggregateRating') or {}).get('ratingValue')
        rating = parse_num(rating)
        if rating is not None and rating < RATING_MIN:
            skipped.append({'name': name, 'reason': f'low rating ({rating})'})
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
        refset = set(mapped_refs)
        has_body_ref = bool(refset & (PROTEIN_SET | CARBY | FRUIT)) or bool(veg_of(refset))
        if not has_body_ref:
            skipped.append({'name': name, 'reason': 'no real protein/veg/carb body -- only oil/aromatics/seasoning mapped',
                             'mapped': mapped_refs, 'missing_new_ingredients': sorted(missing_new),
                             'unmatched': unmatched})
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

        has_protein_ref = bool(refset & PROTEIN_SET)
        has_veg_ref = bool(veg_of(refset))
        if not has_protein_ref and not has_veg_ref and carbs >= 25 and fat >= 15:
            skipped.append({'name': name, 'reason': 'treat-like (no protein/veg, high carb+fat)'})
            continue

        servings = parse_yield(r.get('recipeYield')) or 2
        time = parse_iso_minutes(r.get('totalTime'))
        if not time:
            time = (parse_iso_minutes(r.get('prepTime')) or 5) + (parse_iso_minutes(r.get('cookTime')) or 15)
        cook_min = parse_iso_minutes(r.get('cookTime')) or time

        lead_protein = next((ref for ref in mapped_refs if ref in PROTEIN_SET), None)
        default_temp = PROTEIN_TEMP_DEFAULT.get(lead_protein, 200)
        temp_c = real_temp_c(r, default_temp)

        ing = [{'ref': ref, 'frac': frac_for(ref)} for ref in mapped_refs]
        pps = price_per_serving([(i['ref'], i['frac']) for i in ing], servings)

        filters = []
        tags = []
        if is_vegan(mapped_refs):
            filters.append('vegan'); tags.append('Vegan')
        elif is_veg(mapped_refs):
            filters.append('veg'); tags.append('Vegetarian')
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
            tags = ['Quick'] if time <= 15 else ['Hearty']
        tags = tags[:2]

        mtype = ['snack'] if (kcal < 180 and protein < 10) else ['dinner', 'lunch']
        icon = protein_icon(lead_protein) if lead_protein else ('ti-leaf' if has_veg_ref else 'ti-bowl')

        slug = re.sub(r'[^a-z0-9]+', '', name.lower())
        cid = make_id(['bb', slug], used_ids)

        out.append({
            'id': cid, 'name': name, 'icon': icon, 'type': mtype, 'filters': filters, 'tags': tags,
            'time': int(time), 'protein': round(protein), 'carbs': round(carbs), 'fat': round(fat),
            'kcal': round(kcal), 'servings': servings, 'equip': ['airfryer'],
            'steps': air_fryer_steps(mapped_refs, temp_c, int(cook_min)), 'ing': ing,
            'sourceRating': rating, 'sourceUrl': d['url'],
        })

    print(f"Built {len(out)} recipes, skipped {len(skipped)}")
    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(skipped, open(MISSING_REPORT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saved {OUT_PATH}")
    print(f"Saved skip report -> {MISSING_REPORT_PATH}")


if __name__ == "__main__":
    main()

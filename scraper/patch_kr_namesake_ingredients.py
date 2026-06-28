# -*- coding: utf-8 -*-
"""Same purpose as patch_namesake_ingredients.py, but for K-Ruoka-native
(kr-prefixed) recipes, which use a separate Finnish stem matcher
(map_ingredients.py) rather than canon_map.py. Re-maps ingredients from
each recipe's real source ingredient list (selected_recipes.json, looked
up by recipeId via name_en.py's English-name reverse lookup) and patches
`ing`/`steps`/`filters`/`tags` in place. Macros/photo/id/name untouched."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from recipe_lib import (is_vegan, is_veg, price_per_serving, BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR)
from generate_from_foodcom import classify, gen_steps
from map_ingredients import classify as classify_ingredient
from name_en import NAME_EN

HTML_PATH = Path(__file__).parent.parent / "index.html"
SELECTED_PATH = Path(__file__).parent / "selected_recipes.json"

# (id, english_name) -- found fixable by the map_ingredients.py stem fixes above
TARGETS = [
 ("krsaladgarliclemonmangooliveoilsoysauce", "Whole Roast Chicken"),
 ("krskilletbaconcreamonionpotato", "Ham Casserole"),
 ("krskilletbaconcreamonion", "Easy Ham Casserole"),
 ("krroastbaconflourfreshtomatomozzarellaoliveoilspinach", "Parma Ham & Mozzarella Pizza"),
 ("kreggbreakfastbaconbasileggs", "Microwave Ham Omelet"),
 ("krskilletbaconcreamfreshtomatospinach", "Parma Ham Pizza"),
 ("krskilletasparagusbaconoliveoil", "Asparagus & Parma Ham"),
 ("kreggbreakfastbaconbuttercreameggsfreshtomatooliveoilonion", "Scrambled Eggs & Air-Dried Ham"),
 ("krwrapbaconbreadbuttercheese", "Cheese Melt Ham Sandwich"),
 ("krskilletbaconchickencreamfeta", "Chicken Bacon & Sausages"),
 ("krpastacreameggslemonparmesanpastapeassalmon", "Trout & Bacon Pasta"),
 ("kreggbreakfastappleeggsminceonion", "Apple & Pork Patties"),
 ("kreggbreakfasteggsminceoatsoliveoilpesto", "Pesto Chicken Meatballs"),
 ("krcurrycurrypasteeggsgarlicminceoliveoilyogurt", "Chicken Meatballs"),
 ("krroastblackbeanschiliflakescinnamoncuminminceoliveoiloniontomato", "Chili Con Chicken"),
 ("krroastbasilcarrotcumingarlicminceoliveoiloniontomatovinegar", "Chicken Bolognese"),
]


def steparr(steps):
    return '[' + ','.join(json.dumps(s, ensure_ascii=False) for s in steps) + ']'


def arr(lst):
    return '[' + ','.join(f"'{x}'" for x in lst) + ']'


def ingarr(ing):
    return '[' + ','.join(f"{{ref:'{i['ref']}',frac:{i['frac']}}}" for i in ing) + ']'


def frac_for(ref):
    from build_kruoka_recipes import frac_for as _frac_for
    return _frac_for(ref)


def remap_refs(recipe):
    mapped_refs = []
    for ing in recipe.get('ingredients') or []:
        sp = (ing.get('productSpelling') or {}).get('fi')
        if not sp:
            continue
        kind, val = classify_ingredient(sp)
        if kind == 'mapped' and val and val not in mapped_refs:
            mapped_refs.append(val)
    return mapped_refs


def main():
    name_to_id = {v: k for k, v in NAME_EN.items()}
    selected_by_id = {str(r.get('recipeId')): r for r in json.load(open(SELECTED_PATH, encoding='utf-8'))}

    html = HTML_PATH.read_text(encoding='utf-8')
    start = html.index("\nlet meals=[") + len("\nlet meals=[")
    end = html.index("\n];\n", start)
    chunks = html[start:end].split("{id:'")

    by_id = {}
    for i, chunk in enumerate(chunks[1:], 1):
        mid = chunk.split("'", 1)[0]
        by_id[mid] = i

    patched, unchanged, missing = 0, 0, 0
    for mid, name in TARGETS:
        if mid not in by_id:
            print(f"  SKIP {mid}: not found in index.html")
            missing += 1
            continue
        recipe_id = name_to_id.get(name)
        recipe = selected_by_id.get(str(recipe_id)) if recipe_id else None
        if not recipe:
            print(f"  SKIP {mid}: {name!r} (recipeId {recipe_id}) not found in selected_recipes.json")
            missing += 1
            continue

        new_refs = sorted(set(remap_refs(recipe)))
        if len(new_refs) < 2:
            print(f"  SKIP {mid}: re-mapped to fewer than 2 real ingredients")
            continue

        chunk = chunks[by_id[mid]]
        old_refs_m = re.search(r"ing:\[(.*?)\]", chunk)
        old_refs = re.findall(r"ref:'(\w+)'", old_refs_m.group(1)) if old_refs_m else []
        if set(new_refs) == set(old_refs):
            unchanged += 1
            continue

        time_m = re.search(r"time:(\d+)", chunk)
        time = int(time_m.group(1)) if time_m else 25
        servings_m = re.search(r"servings:(\d+)", chunk)
        servings = int(servings_m.group(1)) if servings_m else 2
        protein_m = re.search(r"protein:(\d+)", chunk)
        protein = int(protein_m.group(1)) if protein_m else 0
        carbs_m = re.search(r"carbs:(\d+)", chunk)
        carbs = int(carbs_m.group(1)) if carbs_m else 99
        kcal_m = re.search(r"kcal:(\d+)", chunk)
        fat_m = re.search(r"fat:(\d+)", chunk)
        kcal = int(kcal_m.group(1)) if kcal_m else 999
        fat = int(fat_m.group(1)) if fat_m else 99

        new_ing = [{'ref': ref, 'frac': frac_for(ref)} for ref in new_refs]
        archetype = classify(new_refs)
        new_steps, _ = gen_steps(archetype, new_refs, time)

        pps = price_per_serving([(i['ref'], i['frac']) for i in new_ing], servings)
        filters = []
        tags = []
        if is_vegan(new_refs):
            filters.append('vegan'); tags.append('Vegan')
        elif is_veg(new_refs):
            filters.append('veg'); tags.append('Vegetarian')
        if protein >= 18:
            filters.append('protein'); tags.append('Protein')
        if carbs <= 15:
            filters.append('lowcarb'); tags.append('Low-carb')
        if time <= 15:
            filters.append('quick'); tags.append('Quick')
        if fat <= 10:
            filters.append('lowfat')
        if kcal <= 400:
            filters.append('lowcal')
        if pps < BUDGET_MAX_EUR:
            filters.append('budget')
        if pps < VERYBUDGET_MAX_EUR:
            filters.append('verybudget')
        if not tags:
            tags = ['Hearty']
        tags = tags[:2]

        new_chunk = chunk
        new_chunk = re.sub(r"filters:\[.*?\]", 'filters:' + arr(filters), new_chunk, count=1)
        new_chunk = re.sub(r"tags:\[.*?\]", 'tags:' + arr(tags), new_chunk, count=1)
        old_steps_block = new_chunk[new_chunk.index('steps:['):new_chunk.index('],ing:') + 1]
        new_chunk = new_chunk.replace(old_steps_block, 'steps:' + steparr(new_steps), 1)
        old_ing_block = re.search(r"ing:\[(.*?)\]", new_chunk).group(0)
        new_chunk = new_chunk.replace(old_ing_block, 'ing:' + ingarr(new_ing), 1)

        chunks[by_id[mid]] = new_chunk
        print(f"  PATCHED {mid}: {sorted(old_refs)} -> {new_refs}")
        patched += 1

    new_body = "{id:'".join(chunks)
    html2 = html[:start] + new_body + html[end:]
    HTML_PATH.write_text(html2, encoding='utf-8')
    print(f"\nPatched {patched}, unchanged {unchanged}, missing/skipped {missing}")


if __name__ == "__main__":
    main()

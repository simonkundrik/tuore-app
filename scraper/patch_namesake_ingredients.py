# -*- coding: utf-8 -*-
"""One-time targeted fix: re-maps ingredients for specific already-shipped
recipes whose name implies an ingredient (sausage, tuna, feta, chorizo,
lamb, prawn, ham, cod) that didn't make it into their real `ing` array --
either because canon_map.py was missing a standalone keyword (e.g. "feta"
alone vs. only "feta cheese") or because the ingredient (ham, cod) hadn't
been onboarded as a real product yet. Both root causes are now fixed in
canon_map.py/recipe_lib.py; this re-runs matching against each affected
recipe's own real source ingredient list and patches `ing`/`steps`/
`filters`/`tags` in place. Macros are untouched -- they come from each
recipe's real source nutrition data, not derived from ingredients, so a
previously-missing ingredient never affected them.

Only touches the specific ids listed below, found by name lookup in their
original raw scrape file. Everything else in each recipe (id/name/macros/
type/icon/equip) stays exactly as it was."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from recipe_lib import (is_vegan, is_veg, is_lowcarb, price_per_serving,
    BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR)
from build_airfryer_recipes import (match_ingredient, parse_iso_minutes, parse_yield,
    frac_for, air_fryer_steps, real_temp_c, PROTEIN_TEMP_DEFAULT)
from build_quick_recipes import NO_HEAT_OVERRIDE_FROM, COOK_HEAT_WORDS, instructions_text
from generate_from_foodcom import classify, gen_steps, PROTEIN_SET

HTML_PATH = Path(__file__).parent.parent / "index.html"
BBQ_RAW = Path(__file__).parent / "budgetbytes_quick_raw.json"
F2S_RAW = Path(__file__).parent / "forktospoon_airfryer_raw.json"

# (id, name, source) -- the recipes confirmed fixable by the canon_map/
# recipe_lib changes above (real product exists, matcher just missed it)
TARGETS = [
 ("bbqgrilledsausageandpeppersfoilpacket", "Grilled Sausage and Peppers Foil Packet", "bbq"),
 ("bbqtunapatties", "Tuna Patties", "bbq"),
 ("bbqchickensausagewhitebeanskillet", "Chicken Sausage White Bean Skillet", "bbq"),
 ("bbqpastawithpeasandham", "Pasta with Peas and Ham", "bbq"),
 ("bbqclassictunapastasalad", "Classic Tuna Pasta Salad", "bbq"),
 ("bbqpastawithsausageandpeppers", "Pasta with Sausage and Peppers", "bbq"),
 ("bbqcheesysausagepasta", "Cheesy Sausage Pasta", "bbq"),
 ("bbqspinachandfetagrilledcheese", "Spinach and Feta Grilled Cheese", "bbq"),
 ("bbqcajunsausageandvegetables", "Cajun Sausage and Vegetables", "bbq"),
 ("bbqcountrysausagegravy", "Country Sausage Gravy", "bbq"),
 ("bbqmediterraneantunasalad", "Mediterranean Tuna Salad", "bbq"),
 ("bbqsausageandeggbreakfastquesadillas", "Sausage and Egg Breakfast Quesadillas", "bbq"),
 ("bbqscrambledeggswithspinachandfeta", "Scrambled Eggs with Spinach and Feta", "bbq"),
 ("bbqsweetandspicytunasalad", "Sweet and Spicy Tuna Salad", "bbq"),
 ("bbqmaplesagebreakfastsausage", "Maple Sage Breakfast Sausage", "bbq"),
 ("bbqspicyorecchiettewithchickensausageandkale", "Spicy Orecchiette with Chicken Sausage and Kale", "bbq"),
 ("bbqspicytunaguacamolebowls", "Spicy Tuna Guacamole Bowls", "bbq"),
 ("bbqspicychorizocheesedip", "Spicy Chorizo Cheese Dip", "bbq"),
 ("bbqspinachandfetaturkeymeatballs", "Spinach and Feta Turkey Meatballs", "bbq"),
 ("bbqcreamytunapastawithpeas", "Creamy Tuna Pasta with Peas", "bbq"),
 ("bbqitaliansausageandwhitebeanskillet", "Italian Sausage and White Bean Skillet", "bbq"),
 ("bbqskilletpastawithsundriedtomatoeswalnutsandfeta", "Skillet Pasta with Sun Dried Tomatoes Walnuts and Feta", "bbq"),
 ("bbqonepotsausageandsundriedtomatopasta", "One Pot Sausage and Sun Dried Tomato Pasta", "bbq"),
 ("bbqsmokedsausagewithpeppersandfarro", "Smoked Sausage with Peppers and Farro", "bbq"),
 ("bbqhawaiianhamquesadillas", "Hawaiian Ham Quesadillas", "bbq"),
 ("bbqspicysausageandbroccolipasta", "Spicy Sausage and Broccoli Pasta", "bbq"),
 ("f2sairfryerprawntoast", "Air Fryer Prawn Toast", "f2s"),
 ("f2seasyairfryertunapatties", "Easy Air Fryer Tuna Patties", "f2s"),
 ("f2sairfryermarinatedbeefkabobs", "Air Fryer Marinated Beef Kabobs", "f2s"),
 ("f2sairfryerchickenandchorizopaella", "Air Fryer Chicken and Chorizo Paella", "f2s"),
 ("f2sairfryercarrotbacon", "Air Fryer Carrot Bacon", "f2s"),
 ("f2sairfryerlambmeatballs", "Air Fryer Lamb Meatballs", "f2s"),
 ("f2sairfryerhamandmozzarellacheesesticks", "Air Fryer Ham and Mozzarella Cheese Sticks", "f2s"),
 ("f2sairfryercopycatpandaexpressbeijingbeef", "Air Fryer Copycat Panda Express Beijing Beef", "f2s"),
 ("f2seasyairfryerhamandeggcups", "Easy Air Fryer Ham and Egg Cups", "f2s"),
 ("f2scopycatjimmydeansausagerecipe", "Copycat Jimmy Dean Sausage Recipe", "f2s"),
 ("f2scodcheeksinpankobreadcrumbs", "Cod Cheeks in Panko Breadcrumbs", "f2s"),
]


def steparr(steps):
    return '[' + ','.join(json.dumps(s, ensure_ascii=False) for s in steps) + ']'


def arr(lst):
    return '[' + ','.join(f"'{x}'" for x in lst) + ']'


def ingarr(ing):
    return '[' + ','.join(f"{{ref:'{i['ref']}',frac:{i['frac']}}}" for i in ing) + ']'


def remap_refs(recipe_ingredient_lines):
    mapped_refs = []
    for line in recipe_ingredient_lines:
        res = match_ingredient(line)
        if res and res[0] == 'existing' and res[1] not in mapped_refs:
            mapped_refs.append(res[1])
    return mapped_refs


def main():
    bbq_by_name = {d['recipe'].get('name'): d for d in json.load(open(BBQ_RAW, encoding='utf-8'))}
    f2s_by_name = {d['recipe'].get('name'): d for d in json.load(open(F2S_RAW, encoding='utf-8'))}

    html = HTML_PATH.read_text(encoding='utf-8')
    start = html.index("\nlet meals=[") + len("\nlet meals=[")
    end = html.index("\n];\n", start)
    chunks = html[start:end].split("{id:'")

    by_id = {}
    for i, chunk in enumerate(chunks[1:], 1):
        mid = chunk.split("'", 1)[0]
        by_id[mid] = i

    patched, unchanged, missing = 0, 0, 0
    for mid, name, source in TARGETS:
        if mid not in by_id:
            print(f"  SKIP {mid}: not found in index.html")
            missing += 1
            continue
        d = (bbq_by_name if source == 'bbq' else f2s_by_name).get(name)
        if not d:
            print(f"  SKIP {mid}: {name!r} not found in {source} raw data")
            missing += 1
            continue
        r = d['recipe']
        new_refs = remap_refs(r.get('recipeIngredient') or [])
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

        new_ing = [{'ref': ref, 'frac': frac_for(ref)} for ref in new_refs]

        if source == 'f2s':
            lead_protein = next((ref for ref in new_refs if ref in PROTEIN_TEMP_DEFAULT), None)
            default_temp = PROTEIN_TEMP_DEFAULT.get(lead_protein, 200)
            temp_c = real_temp_c(r, default_temp)
            cook_min = parse_iso_minutes(r.get('cookTime')) or time
            new_steps = air_fryer_steps(new_refs, temp_c, cook_min)
        else:
            archetype = classify(new_refs)
            if archetype in NO_HEAT_OVERRIDE_FROM and not COOK_HEAT_WORDS.search(instructions_text(r)):
                archetype = 'salad'
            new_steps, _ = gen_steps(archetype, new_refs, time)

        pps = price_per_serving([(i['ref'], i['frac']) for i in new_ing], servings)
        filters = []
        tags = []
        if is_vegan(new_refs):
            filters.append('vegan'); tags.append('Vegan')
        elif is_veg(new_refs):
            filters.append('veg'); tags.append('Vegetarian')
        has_protein_ref = bool(set(new_refs) & PROTEIN_SET)
        if has_protein_ref and protein >= 18:
            filters.append('protein'); tags.append('Protein')
        if is_lowcarb(new_refs):
            filters.append('lowcarb'); tags.append('Low-carb')
        if time <= 15:
            filters.append('quick'); tags.append('Quick')
        kcal_m = re.search(r"kcal:(\d+)", chunk)
        fat_m = re.search(r"fat:(\d+)", chunk)
        kcal = int(kcal_m.group(1)) if kcal_m else 999
        fat = int(fat_m.group(1)) if fat_m else 99
        if fat <= 10:
            filters.append('lowfat')
        if kcal <= 400:
            filters.append('lowcal')
        if pps < BUDGET_MAX_EUR:
            filters.append('budget')
        if pps < VERYBUDGET_MAX_EUR:
            filters.append('verybudget')
        if not tags:
            tags = ['Quick'] if time <= 25 else ['Hearty']
        tags = tags[:2]

        new_chunk = chunk
        new_chunk = re.sub(r"filters:\[.*?\]", 'filters:' + arr(filters), new_chunk, count=1)
        new_chunk = re.sub(r"tags:\[.*?\]", 'tags:' + arr(tags), new_chunk, count=1)
        old_steps_block = new_chunk[new_chunk.index('steps:['):new_chunk.index('],ing:') + 1]
        new_chunk = new_chunk.replace(old_steps_block, 'steps:' + steparr(new_steps), 1)
        old_ing_block = re.search(r"ing:\[(.*?)\]", new_chunk).group(0)
        new_chunk = new_chunk.replace(old_ing_block, 'ing:' + ingarr(new_ing), 1)

        chunks[by_id[mid]] = new_chunk
        print(f"  PATCHED {mid}: {sorted(old_refs)} -> {sorted(new_refs)}")
        patched += 1

    new_body = "{id:'".join(chunks[0:1] + chunks[1:])
    html2 = html[:start] + new_body + html[end:]
    HTML_PATH.write_text(html2, encoding='utf-8')
    print(f"\nPatched {patched}, unchanged {unchanged}, missing/skipped {missing}")


if __name__ == "__main__":
    main()

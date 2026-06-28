# -*- coding: utf-8 -*-
"""Turns the filtered, real-rating-validated Food.com ingredient combinations into
brand new, originally-written Tuore recipes. No text from the dataset is copied --
only the *combination of ingredients* (a fact, not anyone's expression) informs
what we cook; every name/step/description here is freshly authored."""
import sys, json, re
sys.path.insert(0, r"C:\Users\swath\tuore-app\scraper")
from recipe_lib import (P, TITLE, T, Cap, M, FISH, protein_icon, FRAC,
    MEAT_FISH, ANIMAL_NONVEGAN, CARBY, RICHFAT, PROTEIN_G, macro, is_vegan, is_veg,
    is_lowcarb, price_per_serving, make_id,
    is_lowfat, is_lowcal, BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR)

VEGAN_PROTEIN = {'tofu','chickpeas','lentils','blackbeans'}
PROTEIN_SET = MEAT_FISH | VEGAN_PROTEIN | {'eggs'}
AROMATIC = {'garlic','onion'}
HERB_SPICE = {'basil','parsley','dill','cumin','paprika','cinnamon','chiliflakes','vanilla'}
SAUCE_LIQUID = {'soysauce','currypaste','tomato','mayo','pesto','tahini','stockcube','hummus'}
# dairy + other liquids that should never be treated as a "vegetable" to stir-fry
DAIRY = {'cheese','feta','parmesan','mozzarella','halloumi','ricotta','cream','butter','yogurt',
         'skyr','rahka','milk','plantmilk','coconutmilk','oatcream'}
FRUIT = {'apple','orange','mango','pineapple','banana','blueberries','strawberries','raspberries','berries'}
NUTS = {'almonds','walnuts','sesameseeds','peanutbutter','darkchocolate'}
WRAP_BASE = {'tortilla','pita','bread'}
MILKY = {'milk','plantmilk','yogurt','skyr'}
# finishing touches: dressings/drizzles, never the "body" of a dish
FINISHING = {'oliveoil','vegetableoil','lemon','honey','vinegar'}
BATTER_LIKE = {'flour','oats','breadcrumbs'}
SALAD_VEG = {'salad','cucumber','radish','avocado','beetroot','fennel'}
STURDY_VEG = {'broccoli','cauliflower','kale','asparagus','zucchini','eggplant','mushroom',
              'cabbage','leek','pepper','carrot','potato','sweetpotato','pumpkin','rutabaga',
              'spinach','peas','sweetcorn','freshtomato'}
# subset of STURDY_VEG that's actually suited to a 30-40min oven roast (greens/peas wilt/dry out)
ROASTABLE_VEG = STURDY_VEG - {'spinach','kale','peas'}
# delicate proteins that overcook badly at oven-roast timescales
DELICATE_PROTEIN = FISH | {'mussels'}
NON_VEG_ROLE = (PROTEIN_SET | CARBY | HERB_SPICE | SAUCE_LIQUID | DAIRY | AROMATIC | FRUIT |
                 NUTS | WRAP_BASE | FINISHING | BATTER_LIKE)
def veg_of(b):
    return set(b) - NON_VEG_ROLE

def classify(buckets):
    b = set(buckets)
    has_protein_meatfish = bool(b & MEAT_FISH)
    has_protein = bool(b & PROTEIN_SET)
    has_carb = bool(b & CARBY)
    has_pasta = 'pasta' in b
    has_wrapbase = bool(b & WRAP_BASE)
    has_grainbowl_carb = bool(b & {'quinoa','barley','buckwheat','couscous'})
    has_curry = bool(b & {'currypaste','coconutmilk'})
    has_fruit = bool(b & FRUIT)
    has_milky = bool(b & MILKY)
    has_nuts = bool(b & NUTS)
    has_oats = 'oats' in b
    has_eggs = 'eggs' in b
    has_flour_milk = 'flour' in b and ('milk' in b or 'plantmilk' in b)
    has_breading = 'breadcrumbs' in b and bool(b & (MEAT_FISH | {'tofu','halloumi'}))
    has_savory_signal = bool(b & {'soysauce','stockcube','currypaste'})
    veg_body = veg_of(b)

    if has_flour_milk:
        return 'pancake'
    if has_oats and (has_fruit or has_milky) and not has_protein_meatfish:
        return 'porridge'
    has_dressing_signal = bool(b & {'oliveoil','vinegar'})
    if (has_fruit or has_nuts) and not has_protein and not veg_body and not has_carb and not has_dressing_signal:
        return 'smoothie' if (has_milky or has_fruit) else 'bites'
    if has_nuts and has_oats and not has_protein_meatfish and not veg_body and not has_dressing_signal:
        return 'bites'
    if has_breading:
        return 'breaded'
    if has_eggs and not has_pasta and not has_grainbowl_carb and not has_curry and not has_savory_signal and not has_wrapbase:
        return 'eggbreakfast'
    if has_wrapbase:
        base = next(iter(b & WRAP_BASE))
        filling_strength = [x for x in (veg_body | (b & PROTEIN_SET) | (b & SALAD_VEG)) if x != base]
        if base in {'tortilla','pita'} or has_protein or len(filling_strength) >= 2:
            return 'wrap'
        return 'toast'
    if has_pasta:
        return 'pasta'
    if has_curry:
        return 'curry'
    if has_grainbowl_carb:
        return 'grainbowl'
    if not has_carb and not (veg_body & STURDY_VEG) and (veg_body or (b & SALAD_VEG) or has_fruit):
        return 'salad'
    # a stock cube/broth is just as common in a skillet or braise as in an
    # actual soup -- only call it soup if there's no meaty/egg body that
    # would make "blend if you like a smooth soup" nonsensical
    if not has_protein_meatfish and not has_eggs and (
            'stockcube' in b or (veg_body and not has_carb and len(b) >= 5)):
        return 'soup'
    roastable_protein = (b & PROTEIN_SET) - DELICATE_PROTEIN
    if (not (b & DELICATE_PROTEIN)) and (roastable_protein or (veg_body & ROASTABLE_VEG)) and 'oliveoil' in b and len(b) >= 4:
        return 'roast'
    return 'skillet'

def join_names(refs):
    names = [T(r) for r in refs]
    if not names: return 'remaining ingredients'
    if len(names) == 1: return names[0]
    if len(names) == 2: return f"{names[0]} and {names[1]}"
    return ', '.join(names[:-1]) + f" and {names[-1]}"

# the full descriptive phrase to use for a vegetable/aromatic the first time a
# recipe introduces it raw -- proteins are left out since their cut varies too
# much by dish (steak vs. mince vs. strips) to state one default safely.
# Stored as a complete phrase (not just a prefix) since some cuts read
# naturally before the noun ("diced onion") and some after ("broccoli florets")
PREP_HINT = {
 'onion':'diced onion', 'garlic':'minced garlic', 'carrot':'sliced carrot', 'pepper':'sliced pepper',
 'cucumber':'sliced cucumber', 'zucchini':'sliced zucchini', 'eggplant':'cubed eggplant',
 'potato':'cubed potato', 'sweetpotato':'cubed sweet potato', 'mushroom':'sliced mushroom',
 'cabbage':'shredded cabbage', 'leek':'sliced leek', 'broccoli':'broccoli florets',
 'cauliflower':'cauliflower florets', 'freshtomato':'diced tomato', 'beetroot':'diced beetroot',
 'fennel':'sliced fennel', 'asparagus':'trimmed asparagus', 'pumpkin':'cubed pumpkin',
 'rutabaga':'cubed rutabaga',
}
def prep_join(refs):
    names = [PREP_HINT.get(r, T(r)) for r in refs]
    if not names: return 'remaining ingredients'
    if len(names) == 1: return names[0]
    if len(names) == 2: return f"{names[0]} and {names[1]}"
    return ', '.join(names[:-1]) + f" and {names[-1]}"

BODY_ROLES = PROTEIN_SET | CARBY | FRUIT
def has_body(buckets):
    b = set(buckets)
    return bool(b & BODY_ROLES) or bool(veg_of(b))

LOW_PRIORITY_TITLE_WORDS = {'butter','oliveoil'}
def dish_title(buckets, archetype):
    b = [x for x in buckets if x not in LOW_PRIORITY_TITLE_WORDS]
    skip_base = WRAP_BASE if archetype in ('wrap','toast') else set()
    b = [x for x in b if x not in skip_base]
    proteins = [x for x in b if x in PROTEIN_SET]
    carbs = [x for x in b if x in CARBY]
    vegs = [x for x in b if x in veg_of(b)]
    dairy = [x for x in b if x in DAIRY]
    fruit = [x for x in b if x in FRUIT]
    herbs = [x for x in b if x in HERB_SPICE]
    nuts = [x for x in b if x in NUTS]
    sauces = [x for x in b if x in SAUCE_LIQUID]
    # pull from richest-to-thinnest category until we have 2 distinguishing words
    lead = []
    for pool in (proteins, carbs, vegs, fruit, dairy, nuts, herbs, sauces):
        for x in pool:
            if x not in lead:
                lead.append(x)
            if len(lead) >= 2: break
        if len(lead) >= 2: break
    if len(lead) < 2:
        # fall back to the deprioritized words (butter/base) rather than repeat
        fallback = [x for x in list(buckets) if x not in lead]
        for x in fallback:
            if x not in lead:
                lead.append(x)
            if len(lead) >= 2: break
    if not lead: lead = list(buckets)[:2]
    label = ' & '.join(Cap(T(x)) for x in lead[:2])
    SUFFIX = {
        'stirfry':'stir-fry','roast':'bake','soup':'soup','pasta':'pasta','salad':'salad',
        'curry':'curry','eggbreakfast':'scramble','grainbowl':'bowl','smoothie':'smoothie',
        'bites':'energy bites','wrap':'wrap','skillet':'skillet','porridge':'porridge',
        'pancake':'pancakes','breaded':'schnitzel','toast':'toast',
    }
    return f"{label} {SUFFIX.get(archetype,'plate')}"

def gen_steps(archetype, buckets, minutes):
    b = list(buckets)
    proteins = [x for x in b if x in PROTEIN_SET]
    vegs = [x for x in b if x in veg_of(b)]
    carbs = [x for x in b if x in CARBY]
    aromatics = [x for x in b if x in AROMATIC]
    herbs = [x for x in b if x in HERB_SPICE]
    sauces = [x for x in b if x in SAUCE_LIQUID]
    dairy = [x for x in b if x in DAIRY]
    fruit = [x for x in b if x in FRUIT]
    nuts = [x for x in b if x in NUTS]
    extras = [x for x in b if x in FINISHING]
    equip = []
    steps = []

    if archetype == 'pancake':
        eggs = ['eggs'] if 'eggs' in b else []
        liquid = [x for x in b if x in ('milk','plantmilk')]
        extra_dairy = [x for x in dairy if x not in liquid]
        batter_extra = f" and {join_names(extra_dairy)}" if extra_dairy else ""
        steps.append(f"Whisk together the flour, {join_names(liquid+eggs)}{batter_extra} until smooth, with no lumps remaining.")
        meaty_protein = [x for x in proteins if x != 'eggs']
        if meaty_protein:
            steps.append(f"Fry the {join_names(meaty_protein)} in a pan over medium heat until cooked through, then set aside to add back on top later.")
        steps.append("Heat a lightly oiled pan over medium heat. Pour in spoonfuls of the batter and cook 2-3 min per side, flipping once bubbles form on the surface, until golden and set in the centre.")
        topping = fruit+nuts+meaty_protein+[x for x in ('honey',) if x in b]
        if topping:
            steps.append(f"Serve warm, topped with {join_names(topping)}.")
        equip=['pan']
    elif archetype == 'porridge':
        liquid = 'milk' if 'milk' in b else ('plantmilk' if 'plantmilk' in b else None)
        steps.append(f"Bring the {T(liquid)} to a gentle simmer in a pot over medium heat." if liquid else "Heat a splash of water in a pot over medium heat.")
        steps.append(f"Stir in the oats{(' and ' + join_names(herbs)) if herbs else ''}, then reduce the heat to low and cook 3-4 min, stirring occasionally, until thickened.")
        topping = fruit+nuts+extras
        if topping:
            steps.append(f"Top with {join_names(topping)} and serve warm.")
        equip=['pot']
    elif archetype == 'smoothie':
        items = [x for x in b if x not in AROMATIC]
        steps.append(f"Add the {join_names(items)} to a blender, with a splash of water or extra liquid if needed to get it moving.")
        steps.append("Blend on high until smooth and creamy, about 30-60 sec.")
        equip=['blender']
    elif archetype == 'bites':
        steps.append(f"Mash or mix the {join_names(b)} together in a bowl until well combined and the mixture holds together when pressed.")
        steps.append("Roll into small, bite-sized balls and chill in the fridge for at least 20 min to firm up before serving.")
    elif archetype == 'breaded':
        main_protein = [x for x in proteins if x != 'eggs'][:1]
        season_note = f" and {join_names(aromatics)}" if aromatics else ""
        steps.append(f"Season the {join_names(main_protein)} on both sides with salt, pepper{season_note}.")
        if 'eggs' in b:
            steps.append("Beat the eggs in a shallow bowl. Dip each piece of the protein in the egg, then coat thoroughly in the breadcrumbs, pressing gently so they stick.")
        else:
            steps.append("Coat the protein thoroughly in the breadcrumbs, pressing gently so they stick.")
        steps.append("Fry in a pan over medium heat for 3-4 min per side until golden brown and cooked through.")
        topping = dairy+herbs+sauces+extras
        if topping:
            steps.append(f"Serve hot, topped with {join_names(topping)}.")
        equip=['pan']
    elif archetype == 'eggbreakfast':
        lead_extra = aromatics + [x for x in (proteins+vegs) if x != 'eggs']
        if lead_extra:
            steps.append(f"Sauté the {prep_join(lead_extra)} in a pan over medium heat for 3-4 min until softened.")
        flour_note = ' and a spoonful of flour' if 'flour' in b else ''
        steps.append(f"Meanwhile, whisk the eggs{flour_note} with a pinch of salt and pepper until well combined.")
        fold_in = dairy+herbs+sauces+extras
        steps.append("Pour the egg mixture into the pan and cook over medium-low heat, stirring gently, until just set, about 2-3 min.")
        if fold_in:
            steps.append(f"Fold in the {join_names(fold_in)} just before serving.")
        equip=['pan']
    elif archetype == 'toast':
        base = next(x for x in b if x in WRAP_BASE)
        rest = [x for x in b if x != base]
        steps.append(f"Toast the {T(base)} until golden and crisp.")
        steps.append(f"Mix the {join_names(rest)} together in a bowl and spread generously over the toast (warm gently in a pan first if you'd like the topping melted).")
    elif archetype == 'wrap':
        base = next(x for x in b if x in WRAP_BASE)
        fillings = [x for x in b if x != base]
        cookable = [x for x in fillings if x in PROTEIN_SET or x=='halloumi']
        if cookable:
            steps.append(f"Fry the {join_names(cookable)} in a pan over medium heat until cooked through, about 5-8 min.")
            equip=['pan']
        rest = [x for x in fillings if x not in cookable]
        steps.append(f"Spread or layer the {join_names(rest) if rest else join_names(fillings)} over the {T(base)}, leaving a little space at the edges.")
        steps.append("Roll up tightly, tucking in the sides (or fold in half, if using bread), and slice to serve.")
    elif archetype == 'pasta':
        steps.append("Boil the pasta in a large pot of salted water following the pack instructions, until al dente.")
        cookable = [x for x in (proteins+vegs) if x != 'pasta']
        if cookable:
            steps.append(f"Meanwhile, cook the {prep_join(cookable)}{(' with the ' + prep_join(aromatics)) if aromatics else ''} in a pan over medium heat for 4-6 min, stirring occasionally, until cooked through.")
            equip=['pot','pan']
        elif aromatics:
            steps.append(f"Meanwhile, sauté the {prep_join(aromatics)} in a pan over medium heat for 1-2 min until fragrant.")
            equip=['pot','pan']
        else:
            equip=['pot']
        toss_in = dairy + sauces + herbs + extras
        if toss_in:
            steps.append(f"Drain the pasta, reserving a splash of the cooking water, then toss through the {join_names(toss_in)}, loosening with a little of the reserved water if needed.")
        else:
            steps.append("Drain the pasta and toss everything together. Season generously with salt and pepper.")
    elif archetype == 'curry':
        steps.append(f"Sauté the {prep_join(aromatics) if aromatics else 'aromatics'} in a pot over medium heat for 1-2 min until fragrant.")
        if 'currypaste' in b:
            steps.append("Stir in the curry paste and cook for 30 sec, then add the coconut milk and a splash of water.")
        else:
            steps.append("Add the coconut milk and a splash of water.")
        cookable = [x for x in (proteins+vegs) if x not in ('currypaste','coconutmilk')]
        if cookable:
            steps.append(f"Add the {prep_join(cookable)} and simmer over medium-low heat for 12-20 min, stirring occasionally, until cooked through. Serve hot with rice.")
        equip=['pot']
    elif archetype == 'grainbowl':
        grain = next(x for x in b if x in {'quinoa','barley','buckwheat','couscous'})
        steps.append(f"Cook the {T(grain)} in a pot following the pack instructions.")
        cookable = [x for x in (proteins+vegs) if x != grain]
        if cookable:
            steps.append(f"Meanwhile, roast or pan-fry the {prep_join(cookable)} until tender and lightly browned, about 10-15 min.")
        toss_in = dairy + sauces + herbs + extras
        steps.append(f"Toss everything together{(' with the ' + join_names(toss_in)) if toss_in else ''}, season with salt and pepper, and serve warm or at room temperature.")
        equip=['pot']
    elif archetype == 'salad':
        mains = [x for x in b if x not in {'oliveoil','lemon','honey','vinegar'}]
        steps.append(f"Toss the {prep_join(mains)} together in a large bowl.")
        dressing = [x for x in ('oliveoil','lemon','honey','vinegar') if x in b]
        if dressing:
            steps.append(f"Drizzle with the {join_names(dressing)} and toss gently to coat. Season with salt and pepper to taste.")
        else:
            steps.append("Season with salt and pepper to taste.")
    elif archetype == 'soup':
        if aromatics:
            steps.append(f"Sauté the {prep_join(aromatics)} in a pot over medium heat for 3 min until softened and fragrant.")
        body = [x for x in vegs+proteins+carbs if x not in aromatics]
        liquid = "the stock cube and enough water to cover" if 'stockcube' in b else "a splash of water"
        steps.append(f"Add the {prep_join(body)} and {liquid}, bring to a boil, then reduce the heat and simmer 15-20 min until tender.")
        finish_in = dairy + [x for x in sauces if x != 'stockcube'] + herbs + extras
        if finish_in:
            steps.append(f"Stir in the {join_names(finish_in)}. Blend with an immersion blender if you'd like a smooth soup, then season with salt and pepper to taste.")
        else:
            steps.append("Blend with an immersion blender if you'd like a smooth soup, then season with salt and pepper to taste.")
        equip=['pot']
    elif archetype == 'roast':
        steps.append("Preheat the oven to 200°C.")
        oven_veg = [x for x in vegs if x in ROASTABLE_VEG]
        quick_veg = [x for x in vegs if x not in ROASTABLE_VEG]
        main = (proteins+carbs) if (proteins or carbs) else oven_veg[:1]
        rest_veg = [x for x in oven_veg if x not in main]
        oil = ['oliveoil'] if 'oliveoil' in extras else []
        post = [x for x in extras+sauces if x not in oil]
        steps.append(f"Toss the {prep_join(main+rest_veg)} with the {join_names(aromatics+oil) or 'a little oil'}{(' and ' + join_names(herbs)) if herbs else ''}, season generously with salt and pepper, and spread out in a single layer on a baking tray.")
        tail = "Roast for 30-40 min, turning the pieces once halfway through, until golden and cooked through."
        if quick_veg:
            tail += f" Stir in the {prep_join(quick_veg)} for the last 5 min of roasting."
        steps.append(tail)
        if post or dairy:
            steps.append(f"Finish with the {join_names(post+dairy)} and serve hot.")
        equip=['oven']
    else:  # skillet (default)
        if aromatics:
            steps.append(f"Sauté the {prep_join(aromatics)} in a pan over medium heat for 2 min until fragrant.")
        main = proteins+vegs+carbs
        if not main:
            main = [x for x in b if x not in aromatics]
        steps.append(f"Add the {prep_join(main)} and cook over medium heat for 8-12 min, stirring occasionally, until cooked through.")
        finishing = [x for x in sauces+herbs+dairy+extras if x not in main]
        if finishing:
            steps.append(f"Stir in the {join_names(finishing)}, season with salt and pepper, and serve hot.")
        else:
            steps.append("Season with salt and pepper to taste and serve hot.")
        equip=['pan']

    # safety net: never silently drop an ingredient the shopping list charges for
    full_text = ' '.join(steps).lower()
    leftover = [r for r in b if not any(w in full_text for w in T(r).lower().split())]
    if leftover:
        steps.append(f"Stir in the {join_names(leftover)} as well.")
    return steps, equip

ARCHETYPE_TYPE = {
 'porridge':['breakfast'],'pancake':['breakfast'],'smoothie':['breakfast','snack'],'bites':['snack'],
 'eggbreakfast':['breakfast'],'breaded':['dinner'],'toast':['lunch','snack'],
 'wrap':['lunch','snack'],'pasta':['lunch','dinner'],
 'curry':['dinner'],'grainbowl':['lunch'],'salad':['lunch','snack'],'soup':['lunch','dinner'],
 'roast':['dinner'],'skillet':['dinner','lunch'],
}
ARCHETYPE_ICON_DEFAULT = {
 'porridge':'ti-coffee','pancake':'ti-coffee','smoothie':'ti-glass','bites':'ti-coffee','eggbreakfast':'ti-egg',
 'breaded':'ti-meat','toast':'ti-bread','wrap':'ti-bread','pasta':'ti-bowl','curry':'ti-bowl',
 'grainbowl':'ti-bowl','salad':'ti-leaf','soup':'ti-bowl','roast':'ti-meat','skillet':'ti-meat',
}
ARCHETYPE_SERVINGS = {
 'porridge':1,'pancake':2,'smoothie':1,'bites':4,'eggbreakfast':1,'breaded':2,'toast':1,
 'wrap':1,'pasta':2,'curry':3,'grainbowl':2,'salad':2,'soup':3,'roast':3,'skillet':2,
}
ARCHETYPE_TIME_RANGE = {
 'porridge':(5,15),'pancake':(15,25),'smoothie':(5,10),'bites':(10,15),'eggbreakfast':(10,20),
 'breaded':(15,25),'toast':(5,15),'wrap':(5,15),'pasta':(15,30),'curry':(20,35),
 'grainbowl':(20,40),'salad':(5,20),'soup':(20,40),'roast':(30,50),'skillet':(10,30),
}

def icon_for(buckets, archetype):
    proteins = [x for x in buckets if x in PROTEIN_SET]
    if proteins:
        return protein_icon(proteins[0])
    return ARCHETYPE_ICON_DEFAULT[archetype]

def build_recipe(buckets, minutes, used_ids):
    archetype = classify(buckets)
    steps, equip = gen_steps(archetype, buckets, minutes)
    name = dish_title(buckets, archetype)
    icon = icon_for(buckets, archetype)
    mtype = ARCHETYPE_TYPE[archetype]
    servings = ARCHETYPE_SERVINGS[archetype]
    lo, hi = ARCHETYPE_TIME_RANGE[archetype]
    raw_time = minutes if minutes else (lo+hi)//2
    time = max(lo, min(hi, round(raw_time/5)*5))
    ing = [{'ref':r,'frac':FRAC.get(r,1)} for r in buckets]
    refs = [i['ref'] for i in ing]
    protein, carbs, fat, kcal = macro(refs, servings)
    filters = []
    tags = []
    if is_vegan(refs):
        filters.append('vegan'); tags.append('Vegan')
    elif is_veg(refs):
        filters.append('veg'); tags.append('Vegetarian')
    if protein>=18:
        filters.append('protein'); tags.append('Protein')
    if is_lowcarb(refs):
        filters.append('lowcarb'); tags.append('Low-carb')
    if time<=15:
        filters.append('quick'); tags.append('Quick')
    if is_lowfat(fat):
        filters.append('lowfat')
    if is_lowcal(kcal):
        filters.append('lowcal')
    pps = price_per_serving([(r['ref'],r['frac']) for r in ing], servings)
    if pps < BUDGET_MAX_EUR:
        filters.append('budget')
    if pps < VERYBUDGET_MAX_EUR:
        filters.append('verybudget')
    if not tags:
        tags = ['Hearty']
    tags = tags[:2]
    cid = make_id([archetype]+sorted(buckets), used_ids)
    return {'id':cid,'name':name,'icon':icon,'type':mtype,'filters':filters,'tags':tags,
            'time':time,'protein':protein,'carbs':carbs,'fat':fat,'kcal':kcal,'servings':servings,
            'equip':equip,'steps':steps,'ing':ing}

if __name__ == '__main__':
    import pandas as pd
    cands = pd.read_json(r"C:\Users\swath\tuore-app\data\final_candidates.json")
    cands = cands.sort_values('score', ascending=False)

    html = open(r"C:\Users\swath\tuore-app\index.html", encoding='utf-8').read()
    existing_ids = set(re.findall(r"\{id:'(\w+)'", html))
    used_ids = set(existing_ids)

    TARGET_NEW = 800
    recipes = []
    seen_idsets = set()
    skipped_no_body = 0
    for _, row in cands.iterrows():
        if len(recipes) >= TARGET_NEW: break
        if not has_body(row['buckets']):
            skipped_no_body += 1
            continue
        buckets = tuple(sorted(row['buckets']))
        if buckets in seen_idsets: continue
        seen_idsets.add(buckets)
        r = build_recipe(list(row['buckets']), row['minutes'], used_ids)
        recipes.append(r)
    print(f"Skipped {skipped_no_body} bodyless (sauce/condiment-only) combos")
    print(f"Built {len(recipes)} recipes")

    from collections import Counter
    arch_count = Counter(classify([i['ref'] for i in r['ing']]) for r in recipes)
    print('by archetype:', dict(arch_count))
    type_count = Counter()
    for r in recipes:
        for t in r['type']: type_count[t]+=1
    print('by type:', dict(type_count))

    json.dump(recipes, open(r"C:\Users\swath\tuore-app\data\foodcom_recipes.json", 'w', encoding='utf-8'), ensure_ascii=False)
    print("Saved foodcom_recipes.json")

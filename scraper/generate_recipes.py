# -*- coding: utf-8 -*-
"""Generates many new recipe combinations from the already-scraped P ingredient
dict in index.html. No new scraping -- purely recombines real, in-stock products
the app already knows about into new recipes (stir-fry, roast, soup, pasta,
salad, curry, egg breakfast, grain bowl, smoothie, energy bites, wrap, skillet)."""
import json
from recipe_lib import (P, existing_ids, TITLE, T, Cap, MID, M, FISH, protein_icon,
    FRAC, MEAT_FISH, ANIMAL_NONVEGAN, CARBY, RICHFAT, PROTEIN_G, macro,
    is_vegan, is_veg, is_lowcarb, price_per_serving, make_id)

used_ids = set(existing_ids)
recipes = []

def add_recipe(parts_for_id, name, icon, mtype, time, servings, equip, steps, ing, tags_extra=None):
    refs = [i['ref'] for i in ing]
    fracs = [(i['ref'], i['frac']) for i in ing]
    protein, kcal = macro(refs, servings)
    filters = []
    tags = []
    if is_vegan(refs):
        filters.append('vegan'); tags.append('Vegan')
    elif is_veg(refs):
        filters.append('veg'); tags.append('Vegetarian')
    if any(r in MEAT_FISH or r in {'tofu','chickpeas','lentils','blackbeans','eggs'} for r in refs) and protein>=18:
        if 'protein' not in filters: filters.append('protein')
        if 'Protein' not in tags: tags.append('Protein')
    if is_lowcarb(refs):
        filters.append('lowcarb')
        if not tags or tags[-1] not in ('Vegan','Vegetarian'): pass
        tags.append('Low-carb')
    if time <= 15:
        filters.append('quick'); tags.append('Quick')
    pps = price_per_serving(fracs, servings)
    if pps < 2.0:
        filters.append('budget')
    if tags_extra:
        tags.extend(tags_extra)
    if not tags:
        tags = ['Quick'] if time<=15 else ['Hearty']
    tags = tags[:2] if len(tags)>2 else tags
    cid = make_id(parts_for_id, used_ids)
    recipes.append({
        'id': cid, 'name': name, 'icon': icon, 'type': mtype, 'filters': filters, 'tags': tags,
        'time': time, 'protein': protein, 'kcal': kcal, 'servings': servings, 'equip': equip,
        'steps': steps, 'ing': ing,
    })

# ================= STIR-FRY =================
STIRFRY = [
 ('turkey','cauliflower'),('turkey','zucchini'),('turkey','kale'),
 ('beef','cabbage'),('beef','asparagus'),('beef','cauliflower'),
 ('pork','leek'),('pork','cabbage'),
 ('chicken','cauliflower'),('chicken','zucchini'),('chicken','kale'),('chicken','asparagus'),
 ('chicken','leek'),('chicken','pepper'),
 ('prawns','zucchini'),('prawns','broccoli'),('prawns','asparagus'),
 ('tofu','cauliflower'),('tofu','peas'),('tofu','kale'),('tofu','zucchini'),
 ('salmon','asparagus'),('salmon','broccoli'),
 ('whitefish','broccoli'),('whitefish','kale'),
]
SAUCE_VARIANTS = ['soy', 'chili-honey', 'lemon-garlic']
for i,(prot,veg) in enumerate(STIRFRY):
    sauce = SAUCE_VARIANTS[i % 3]
    base_ing=[{'ref':prot,'frac':FRAC[prot]},{'ref':veg,'frac':FRAC[veg]},
              {'ref':'garlic','frac':FRAC['garlic']},{'ref':'rice','frac':FRAC['rice']}]
    s1="Cook the rice in a pot."
    s2=(f"Stir-fry the {M(prot)} in a pan until cooked through." if prot!='tofu'
        else "Cube the tofu, pat dry, and fry in a pan until golden on all sides.")
    s3=f"Add the {T(veg)} and garlic, cook 4-5 min."
    if sauce == 'soy':
        ing = base_ing+[{'ref':'soysauce','frac':FRAC['soysauce']}]
        s4 = "Stir in the soy sauce, season with black pepper, and serve over the rice."
        suffix = ''
    elif sauce == 'chili-honey':
        ing = base_ing+[{'ref':'chiliflakes','frac':FRAC['chiliflakes']},{'ref':'honey','frac':FRAC['honey']}]
        s4 = "Stir in the chili flakes and honey, season with salt, and serve over the rice."
        suffix = ', sweet & spicy'
    else:
        ing = base_ing+[{'ref':'lemon','frac':FRAC['lemon']}]
        s4 = "Squeeze over the lemon, season with salt and black pepper, and serve over the rice."
        suffix = ''
    name=f"{Cap(T(prot))} & {T(veg)} stir-fry{suffix}"
    add_recipe([prot,veg,'sf'], name, protein_icon(prot),
        ['dinner'], 20, 2, ['pot','pan'], [s1,s2,s3,s4], ing)

# ================= ROAST/BAKE TRAY =================
ROAST = [
 ('chicken','sweetpotato','kale'),('chicken','pumpkin','onion'),('chicken','zucchini','pepper'),
 ('chicken','beetroot','onion'),
 ('turkey','zucchini','pepper'),('turkey','asparagus',None),('turkey','rutabaga','carrot'),
 ('turkey','cauliflower','onion'),
 ('pork','apple','fennel'),('pork','leek','potato'),('pork','pumpkin','onion'),
 ('lamb','eggplant','freshtomato'),('lamb','cauliflower',None),
 ('salmon','asparagus',None),('salmon','fennel',None),('salmon','zucchini',None),
 ('whitefish','leek',None),
 ('sausage','pepper','onion'),
 ('beef','potato','carrot'),
]
SPICE_FOR = {'pork':'paprika','sausage':'paprika','beef':'paprika','lamb':'cumin',
             'salmon':'dill','whitefish':'dill'}
for prot,veg1,veg2 in ROAST:
    vegs=[veg1]+([veg2] if veg2 else [])
    ing=[{'ref':prot,'frac':FRAC[prot]}]+[{'ref':v,'frac':FRAC[v]} for v in vegs]
    ing+=[{'ref':'garlic','frac':FRAC['garlic']},{'ref':'oliveoil','frac':FRAC['oliveoil']}]
    citrus = prot in ('salmon','whitefish','turkey') and 'lemon' not in vegs
    if citrus:
        ing.append({'ref':'lemon','frac':FRAC['lemon']})
    spice = SPICE_FOR.get(prot)
    if spice and spice not in vegs:
        ing.append({'ref':spice,'frac':FRAC[spice]})
    vegname = f"{T(veg1)} & {T(veg2)}" if veg2 else T(veg1)
    name=f"{Cap(T(prot))} with roasted {vegname}"
    season_extra = f", black pepper and {T(spice)}" if spice else " and black pepper"
    steps=["Preheat the oven to 200°C.", f"Season the {T(prot)} with salt{season_extra}."]
    steps.append(f"Toss the {vegname} with olive oil and garlic.")
    tail = f"Roast the {T(prot)} and vegetables together for 30-40 min, turning once."
    if citrus:
        tail += " Squeeze over lemon to serve."
    steps.append(tail)
    add_recipe([prot,veg1,(veg2 or ''),'rst'], name, protein_icon(prot),
        ['dinner'], 40, 3, ['oven'], steps, ing)

# ================= SOUP =================
def soup_ing(*items):
    return [{'ref':r,'frac':FRAC[r]} for r in items]

SOUPS = [
 ('carrotlentilsoup','Curried carrot & lentil soup','ti-bowl',
  ['carrot','lentils','onion','currypaste','coconutmilk'],
  ["Saúté the onion and carrot in a pot for 3 min.",
   "Stir in the curry paste, then add the lentils, coconut milk and enough water to cover.",
   "Simmer 20 min until the lentils are soft. Season with salt and pepper."]),
 ('cauliflowerleeksoup','Cauliflower & leek soup','ti-leaf',
  ['cauliflower','leek','onion','cream','stockcube'],
  ["Saúté the leek and onion in a pot for 5 min.",
   "Add the cauliflower, stock cube and enough water to cover, simmer 15 min until soft.",
   "Blend until smooth and stir in the cream. Season with salt and pepper."]),
 ('fennelpotatosoup','Fennel & potato soup','ti-leaf',
  ['fennel','potato','leek','cream'],
  ["Saúté the fennel and leek in a pot for 5 min.",
   "Add diced potato and enough water to cover, simmer 20 min until soft.",
   "Blend until smooth and stir in the cream. Season with salt and pepper."]),
 ('spinachpotatosoup','Spinach & potato soup','ti-leaf',
  ['spinach','potato','onion','stockcube'],
  ["Saúté the onion in a pot for 3 min.",
   "Add diced potato, stock cube and enough water to cover, simmer 15 min until soft.",
   "Stir in the spinach, blend until smooth, and season with salt and pepper."]),
 ('chickenleeksoup','Chicken & leek soup','ti-meat',
  ['chicken','leek','carrot','stockcube'],
  ["Saúté the leek and carrot in a pot for 5 min.",
   "Add the chicken, stock cube and enough water to cover.",
   "Simmer 20 min until the chicken is cooked through. Season with salt and pepper."]),
 ('beefbarleysoup','Beef & barley soup','ti-meat',
  ['beef','barley','carrot','onion','stockcube'],
  ["Brown the beef in a pot for 3-4 min.",
   "Add the onion and carrot, cook 3 min.",
   "Stir in the barley, stock cube and enough water to cover, simmer 30 min until the barley is tender."]),
 ('tomatobasilsoup','Tomato & basil soup','ti-bowl',
  ['tomato','basil','onion','cream'],
  ["Saúté the onion in a pot for 3 min.",
   "Add the canned tomatoes and a splash of water, simmer 10 min.",
   "Stir in the basil and cream, blend until smooth, and season with salt and pepper."]),
 ('veganbroccolisoup','Vegan broccoli & potato soup','ti-leaf',
  ['broccoli','potato','onion','coconutmilk'],
  ["Saúté the onion in a pot for 3 min.",
   "Add the broccoli, diced potato and enough water to cover, simmer 15 min until soft.",
   "Stir in the coconut milk, blend until smooth, and season with salt and pepper."]),
 ('kalepotatosoup','Kale & potato soup','ti-leaf',
  ['kale','potato','onion','garlic'],
  ["Saúté the onion and garlic in a pot for 3 min.",
   "Add diced potato and enough water to cover, simmer 15 min until soft.",
   "Stir in the kale, cook 5 min more until wilted, and season with salt and pepper."]),
 ('musselleekchowder','Mussel & leek chowder','ti-fish',
  ['mussels','leek','potato','cream'],
  ["Saúté the leek in a pot for 3 min.",
   "Add diced potato and enough water to cover, simmer 10 min until soft.",
   "Add the mussels and cream, cover and cook 5-6 min until the mussels open."]),
 ('chickpeaspinachsoup','Spiced chickpea & spinach soup','ti-bowl',
  ['chickpeas','spinach','onion','cumin','tomato'],
  ["Saúté the onion and cumin in a pot for 2 min.",
   "Add the chickpeas, canned tomatoes and enough water to cover, simmer 15 min.",
   "Stir in the spinach and cook 5 min more. Season with salt and pepper."]),
 ('turkeyleeksoup','Turkey & leek soup','ti-meat',
  ['turkey','leek','carrot','stockcube'],
  ["Saúté the leek and carrot in a pot for 5 min.",
   "Add the turkey, stock cube and enough water to cover.",
   "Simmer 15 min until the turkey is cooked through. Season with salt and pepper."]),
 ('cauliflowerchickpeasoup','Cauliflower & chickpea soup','ti-bowl',
  ['cauliflower','chickpeas','onion','cumin'],
  ["Saúté the onion and cumin in a pot for 3 min.",
   "Add the cauliflower, chickpeas and enough water to cover, simmer 15 min until soft.",
   "Blend until smooth and season with salt and pepper."]),
]
for cid, name, icon, items, steps in SOUPS:
    ing = soup_ing(*items)
    equip = ['pot','blender'] if 'blend' in ' '.join(steps).lower() else ['pot']
    tt = ['lunch','dinner']
    servings = 3 if any(r in ('beef','barley','chicken','turkey','mussels') for r in items) else 3
    add_recipe([cid], name, icon, tt, 30, servings, equip, steps, ing)

# ================= PASTA =================
PASTAS = [
 ('tunapeapasta','Creamy tuna & pea pasta','ti-fish',['tuna','peas','cream','parmesan','pasta'],
  ["Boil the pasta in a pot.","Warm the tuna, peas and cream in a pan for 3-4 min.",
   "Drain the pasta, toss through the sauce and stir in the parmesan."]),
 ('sausagepepperpasta','Sausage & pepper pasta','ti-meat',['sausage','pepper','tomato','basil','pasta'],
  ["Boil the pasta in a pot.","Slice and fry the sausage in a pan for 3 min.",
   "Add the pepper and canned tomatoes, simmer 10 min.",
   "Drain the pasta, toss through the sauce and stir in the basil."]),
 ('mushroomspinachpasta','Mushroom & spinach pasta','ti-leaf',['mushroom','spinach','cream','parmesan','pasta'],
  ["Boil the pasta in a pot.","Fry the mushrooms in a pan for 5 min until golden.",
   "Add the spinach and cream, simmer 3 min.",
   "Drain the pasta, toss through the sauce and stir in the parmesan."]),
 ('chickpeagarlicpasta','Chickpea & garlic pasta','ti-bowl',['chickpeas','spinach','garlic','oliveoil','pasta'],
  ["Boil the pasta in a pot.","Saúté the garlic in olive oil in a pan for 1 min.",
   "Add the chickpeas and spinach, cook 4-5 min until wilted.",
   "Drain the pasta and toss through the sauce. Season with salt and pepper."]),
 ('prawnchilipasta','Garlic chili prawn pasta','ti-fish',['prawns','garlic','chiliflakes','oliveoil','pasta'],
  ["Boil the pasta in a pot.","Saúté the garlic and chili flakes in olive oil in a pan for 1 min.",
   "Add the prawns, cook 2-3 min until pink.",
   "Drain the pasta and toss through the sauce."]),
 ('salmondillpasta','Salmon & dill pasta','ti-fish',['salmon','dill','cream','lemon','pasta'],
  ["Boil the pasta in a pot.","Cook the salmon in a pan 3-4 min per side, then flake it.",
   "Stir the cream and dill into the pan and warm through.",
   "Drain the pasta, toss through the sauce, and finish with a squeeze of lemon."]),
 ('baconmushroompasta','Bacon & mushroom pasta','ti-meat',['bacon','mushroom','cream','parmesan','pasta'],
  ["Boil the pasta in a pot.","Fry the bacon in a pan until crisp.",
   "Add the mushrooms, cook 5 min, then stir in the cream.",
   "Drain the pasta, toss through the sauce and stir in the parmesan."]),
 ('zucchinibasilpasta','Zucchini & basil pasta','ti-leaf',['zucchini','basil','parmesan','oliveoil','pasta'],
  ["Boil the pasta in a pot.","Fry the zucchini in olive oil in a pan for 5 min until golden.",
   "Drain the pasta, toss through the zucchini, basil and parmesan."]),
 ('beefmushroompasta','Beef & mushroom pasta','ti-meat',['beef','mushroom','cream','parsley','pasta'],
  ["Boil the pasta in a pot.","Sear the beef in a hot pan 2-3 min, then set aside to rest.",
   "Fry the mushrooms in the same pan for 4 min, then stir in the cream.",
   "Slice the beef, drain the pasta, and toss everything together with the parsley."]),
 ('choriopepperpasta','Chorizo & pepper pasta','ti-meat',['chorizo','pepper','tomato','pasta'],
  ["Boil the pasta in a pot.","Fry the chorizo in a pan for 2 min until it releases its oil.",
   "Add the pepper and canned tomatoes, simmer 10 min.",
   "Drain the pasta and toss through the sauce."]),
 ('turkeyzucchinipasta','Turkey & zucchini pasta','ti-meat',['turkey','zucchini','basil','oliveoil','pasta'],
  ["Boil the pasta in a pot.","Fry the turkey in a pan 3-4 min until cooked through.",
   "Add the zucchini, cook 4 min more.",
   "Drain the pasta, toss through the olive oil, basil and turkey."]),
 ('lemonherbpasta','White fish & lemon pasta','ti-fish',['whitefish','lemon','parsley','butter','pasta'],
  ["Boil the pasta in a pot.","Melt the butter in a pan and cook the fish 3-4 min per side, then flake it.",
   "Drain the pasta, toss through the fish, lemon and parsley."]),
 ('eggplanttomatopasta','Eggplant & tomato pasta','ti-leaf',['eggplant','tomato','basil','garlic','pasta'],
  ["Boil the pasta in a pot.","Fry the eggplant and garlic in a pan for 6-8 min until soft.",
   "Add the canned tomatoes, simmer 8 min.",
   "Drain the pasta, toss through the sauce and stir in the basil."]),
 ('blackbeanpasta','Smoky bean & sweetcorn pasta','ti-bowl',['blackbeans','sweetcorn','pepper','chiliflakes','pasta'],
  ["Boil the pasta in a pot.","Warm the beans, sweetcorn, pepper and chili flakes in a pan for 5 min.",
   "Drain the pasta and toss through the sauce. Season with salt and pepper."]),
]
for cid, name, icon, items, steps in PASTAS:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['lunch','dinner'], 20, 2, ['pot','pan'], steps, ing)

# ================= SALAD =================
SALADS = [
 ('tunasweetcornsalad','Tuna & sweetcorn salad','ti-fish',['tuna','sweetcorn','pepper','mayo'],
  ["Drain the tuna and sweetcorn.","Toss with the diced pepper and a spoonful of mayo."],[]),
 ('chickpeacucumberferta','Chickpea, cucumber & feta salad','ti-bowl',['chickpeas','cucumber','feta','oliveoil','lemon'],
  ["Toss the chickpeas and cucumber together.","Crumble over the feta and dress with olive oil and lemon."],[]),
 ('turkeyavocadosalad','Turkey & avocado salad','ti-meat',['turkey','avocado','spinach','lemon'],
  ["Slice the turkey and avocado.","Toss with the spinach and a squeeze of lemon."],[]),
 ('prawnorangefennel','Prawn, orange & fennel salad','ti-fish',['prawns','orange','fennel','oliveoil'],
  ["Thinly slice the fennel and orange.","Toss with the prawns and dress with olive oil."],[]),
 ('halloumipeppersalad','Grilled halloumi & pepper salad','ti-cheese',['halloumi','pepper','zucchini','oliveoil'],
  ["Slice the halloumi, pepper and zucchini.","Fry in a pan until golden, 2-3 min per side.","Drizzle with olive oil to serve."],['pan']),
 ('beetrootapplewalnut','Beetroot, apple & walnut salad','ti-leaf',['beetroot','apple','walnuts','oliveoil','honey'],
  ["Slice the beetroot and apple.","Toss together, scatter with walnuts, and drizzle with olive oil and honey."],[]),
 ('radishchickpeasalad','Radish & chickpea salad','ti-carrot',['radish','chickpeas','dill','oliveoil','vinegar'],
  ["Thinly slice the radish.","Toss with the chickpeas and dill, dress with olive oil and vinegar."],[]),
 ('eggspinachsalad','Egg & spinach salad','ti-egg',['eggs','spinach','feta','oliveoil'],
  ["Boil the eggs in a pot for 8-9 min, then peel and quarter.","Toss the spinach with olive oil and crumbled feta, top with the eggs."],['pot']),
 ('tunaavocadosalad','Tuna & avocado salad','ti-fish',['tuna','avocado','cucumber','lemon'],
  ["Drain the tuna.","Toss with the avocado and cucumber, finish with a squeeze of lemon."],[]),
 ('herringbeetrootsalad','Herring & beetroot salad','ti-fish',['herring','beetroot','dill','onion'],
  ["Bake the herring casserole following the pack instructions.","Serve with sliced beetroot, onion and a sprinkle of dill."],['oven']),
 ('pumpkinfetawalnutsalad','Roasted pumpkin, feta & walnut salad','ti-leaf',['pumpkin','feta','walnuts','honey','oliveoil'],
  ["Preheat the oven to 200°C and roast the diced pumpkin with olive oil for 25 min.",
   "Crumble over the feta, scatter with walnuts, and drizzle with honey."],['oven']),
 ('cabbagecarrotslaw','Cabbage & carrot slaw','ti-carrot',['cabbage','carrot','vinegar','oliveoil'],
  ["Finely shred the cabbage and carrot.","Toss with olive oil and vinegar. Season with salt and pepper."],[]),
]
for cid, name, icon, items, steps, extra_equip in SALADS:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['lunch','snack'], 12, 2, extra_equip, steps, ing)

# ================= CURRY =================
CURRIES = [
 ('prawncurry','Coconut prawn curry','ti-fish',['prawns','currypaste','coconutmilk','rice','lemon'],
  ["Saúté the curry paste in a pot for 1 min.",
   "Add the coconut milk and a splash of water, simmer 5 min.",
   "Add the prawns, cook 3-4 min until pink. Squeeze over lemon and serve with rice."]),
 ('chickenpumpkincurry','Chicken & pumpkin curry','ti-meat',['chicken','pumpkin','currypaste','coconutmilk','rice'],
  ["Cut the chicken and pumpkin into chunks.",
   "Saúté the curry paste in a pot for 1 min, then add the chicken and pumpkin.",
   "Add the coconut milk and a splash of water, simmer 20 min. Serve with rice."]),
 ('chickpeacauliflowercurry','Chickpea & cauliflower curry','ti-bowl',['chickpeas','cauliflower','currypaste','coconutmilk','rice'],
  ["Saúté the curry paste in a pot for 1 min.",
   "Add the cauliflower, chickpeas, coconut milk and a splash of water.",
   "Simmer 15 min until the cauliflower is tender. Serve with rice."]),
 ('fishspinachcurry','Fish & spinach curry','ti-fish',['whitefish','spinach','currypaste','coconutmilk','rice'],
  ["Saúté the curry paste in a pot for 1 min.",
   "Add the coconut milk and a splash of water, simmer 5 min.",
   "Add the fish, cook 6-8 min until just cooked through, then stir in the spinach. Serve with rice."]),
 ('beefsweetpotatocurry','Beef & sweet potato curry','ti-meat',['beef','sweetpotato','currypaste','coconutmilk','rice'],
  ["Brown the beef in a pot for 3-4 min.",
   "Stir in the curry paste, then add the sweet potato, coconut milk and a splash of water.",
   "Simmer 25 min until the sweet potato is tender. Serve with rice."]),
 ('lentilpumpkincurry','Lentil & pumpkin curry','ti-bowl',['lentils','pumpkin','currypaste','coconutmilk','rice'],
  ["Saúté the curry paste in a pot for 1 min.",
   "Add the lentils, pumpkin, coconut milk and a splash of water.",
   "Simmer 20 min until soft. Serve with rice."]),
 ('porkbroccolicurry','Pork & broccoli curry','ti-meat',['pork','broccoli','currypaste','coconutmilk','rice'],
  ["Slice the pork thinly.",
   "Saúté the curry paste in a pot for 1 min, then add the pork.",
   "Add the coconut milk and broccoli, simmer 12-15 min. Serve with rice."]),
 ('turkeyspinachcurry','Turkey & spinach curry','ti-meat',['turkey','spinach','currypaste','coconutmilk','rice'],
  ["Saúté the curry paste in a pot for 1 min.",
   "Add the turkey and coconut milk, simmer 12 min until cooked through.",
   "Stir in the spinach and cook 3 min more. Serve with rice."]),
 ('musselcoconutcurry','Thai coconut mussels','ti-fish',['mussels','currypaste','coconutmilk','lemon'],
  ["Saúté the curry paste in a pot for 1 min.",
   "Add the coconut milk and bring to a simmer.",
   "Add the mussels, cover and cook 5-6 min until they open. Squeeze over lemon."]),
]
for cid, name, icon, items, steps in CURRIES:
    ing = soup_ing(*items)
    servings = 2 if items[0] in ('prawns','mussels') else 3
    add_recipe([cid], name, icon, ['dinner'], 28, servings, ['pot'], steps, ing)

# ================= EGG BREAKFAST =================
EGGS = [
 ('spinachfetascramble','Spinach & feta scrambled eggs','ti-egg',['eggs','spinach','feta'],
  ["Whisk the eggs with a pinch of salt and pepper.","Wilt the spinach in a pan for 1 min.",
   "Pour in the eggs and scramble gently, folding through the feta at the end."]),
 ('mushroomcheeseomelette','Mushroom & cheese omelette','ti-egg',['eggs','mushroom','cheese'],
  ["Fry the mushrooms in a pan for 4 min until golden.",
   "Whisk the eggs with salt and pepper, pour over the mushrooms.",
   "Cook 2-3 min, fold in the cheese, then fold the omelette in half."]),
 ('sweetcornpepperfrittata','Sweetcorn & pepper frittata','ti-egg',['eggs','sweetcorn','pepper','cheese'],
  ["Whisk the eggs with the sweetcorn, pepper and cheese.",
   "Pour into a hot pan and cook 5-6 min over low heat until set, then flip or finish under a grill if you have one."]),
 ('shakshuka','Tomato & pepper shakshuka','ti-egg',['eggs','freshtomato','pepper','paprika'],
  ["Saúté the pepper and paprika in a pan for 3 min.",
   "Add the chopped tomato, simmer 8 min until thickened.",
   "Make small wells and crack in the eggs, cover and cook 5-6 min until set."]),
 ('leekeggscramble','Leek & cheese scrambled eggs','ti-egg',['eggs','leek','cheese'],
  ["Saúté the leek in a pan for 4 min until soft.",
   "Whisk the eggs with salt and pepper, pour over the leek.",
   "Scramble gently and fold in the cheese."]),
 ('asparagusparmeggs','Asparagus & parmesan eggs','ti-egg',['eggs','asparagus','parmesan','butter'],
  ["Fry the asparagus in butter in a pan for 4 min.",
   "Whisk the eggs with salt and pepper, pour over the asparagus.",
   "Cook 2-3 min, fold in the parmesan, then fold in half."]),
 ('avocadobeaneggbowl','Avocado & black bean breakfast bowl','ti-egg',['eggs','avocado','blackbeans','chiliflakes'],
  ["Warm the beans in a pan with a pinch of chili flakes.",
   "Fry the eggs in the same pan to your liking.",
   "Serve over the beans with sliced avocado."]),
]
for cid, name, icon, items, steps in EGGS:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['breakfast'], 15, 1, ['pan'], steps, ing)

# ================= GRAIN BOWL =================
GRAINBOWLS = [
 ('quinoapumpkinfeta','Quinoa, roasted pumpkin & feta bowl','ti-bowl',['quinoa','pumpkin','feta','walnuts','oliveoil'],
  ["Preheat the oven to 200°C and roast the diced pumpkin with olive oil for 25 min.",
   "Cook the quinoa in a pot following the pack instructions.",
   "Toss together with the feta and walnuts."],['pot','oven']),
 ('barleykalelemon','Barley, kale & lemon bowl','ti-bowl',['barley','kale','lemon','parmesan','oliveoil'],
  ["Cook the barley in a pot following the pack instructions.",
   "Wilt the kale briefly with a little olive oil.",
   "Toss everything together with parmesan and a squeeze of lemon."],['pot']),
 ('buckwheatmushroomparsley','Buckwheat & mushroom bowl','ti-bowl',['buckwheat','mushroom','parsley','garlic','butter'],
  ["Cook the buckwheat flakes in a pot with water following the pack instructions.",
   "Saúté the mushrooms and garlic in butter in a pan for 5 min.",
   "Toss together and scatter with parsley."],['pot','pan']),
 ('couscouschickpeapepper','Couscous, chickpea & pepper bowl','ti-bowl',['couscous','chickpeas','pepper','parsley','lemon'],
  ["Soak the couscous in boiling water for 5 min, then fluff with a fork.",
   "Toss with the chickpeas, diced pepper, parsley and a squeeze of lemon."],[]),
 ('ricebeancornbowl','Rice, black bean & corn bowl','ti-bowl',['rice','blackbeans','sweetcorn','freshtomato','avocado'],
  ["Cook the rice in a pot.",
   "Warm the beans and sweetcorn in a pan for 3-4 min.",
   "Serve over the rice with diced tomato and avocado."],['pot','pan']),
 ('quinoabeetwalnut','Quinoa, beetroot & walnut bowl','ti-bowl',['quinoa','beetroot','walnuts','feta','honey'],
  ["Cook the quinoa in a pot following the pack instructions, then cool slightly.",
   "Toss with the sliced beetroot, crumbled feta and walnuts, finished with a drizzle of honey."],['pot']),
 ('sweetpotatobeanquinoa','Sweet potato, black bean & quinoa bowl','ti-bowl',['sweetpotato','blackbeans','quinoa','avocado','lemon'],
  ["Preheat the oven to 200°C and roast the sweet potato wedges with olive oil for 25 min.",
   "Cook the quinoa in a pot following the pack instructions.",
   "Toss together with the beans, avocado and a squeeze of lemon."],['pot','oven']),
 ('turkeyquinoavegbowl','Turkey & roasted vegetable quinoa bowl','ti-bowl',['turkey','quinoa','zucchini','pepper','oliveoil'],
  ["Preheat the oven to 200°C and roast the zucchini and pepper with olive oil for 20 min.",
   "Cook the quinoa in a pot following the pack instructions.",
   "Fry the turkey in a pan 3-4 min until cooked through, then toss everything together."],['pot','oven','pan']),
]
for cid, name, icon, items, steps, equip in GRAINBOWLS:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['lunch'], 30, 2, equip, steps, ing)

# ================= SMOOTHIE / BREAKFAST BOWL =================
SMOOTHIES = [
 ('mangoraspberrysmoothie','Mango & raspberry smoothie','ti-glass',['mango','raspberries','plantmilk'],
  ["Add the mango, raspberries and plant milk to a blender.","Blend until smooth."],['blender'],1),
 ('blueberrybananasmoothie','Blueberry & banana smoothie','ti-glass',['blueberries','banana','milk'],
  ["Add the blueberry compote, banana and milk to a blender.","Blend until smooth."],['blender'],1),
 ('strawberrypineapplesmoothie','Strawberry & pineapple smoothie','ti-glass',['strawberries','pineapple','plantmilk'],
  ["Add the strawberries, pineapple and plant milk to a blender.","Blend until smooth."],['blender'],1),
 ('orangecarrotsmoothie','Orange & carrot smoothie','ti-glass',['orange','carrot','banana'],
  ["Peel and chop the orange and carrot.","Blend with the banana and a splash of water until smooth."],['blender'],1),
 ('applecinnamonovernightoats','Apple & cinnamon overnight oats','ti-coffee',['oats','apple','cinnamon','milk'],
  ["Mix the oats, milk and cinnamon in a bowl or jar.","Stir through the diced apple and leave to soften (overnight in the fridge, or 10 min at room temperature)."],[],1),
 ('pumpkinspiceporridge','Pumpkin spice porridge','ti-coffee',['oats','pumpkin','cinnamon','milk'],
  ["Cook the pumpkin in a pot with a little water until soft, then mash.",
   "Stir in the milk, oats and cinnamon, cook 3-4 min."],['pot'],1),
 ('raspberryalmondbowl','Raspberry & almond yogurt bowl','ti-bowl',['yogurt','raspberries','almonds','honey'],
  ["Spoon the yogurt into a bowl.","Top with raspberries, a few almonds and a drizzle of honey."],[],1),
 ('walnutbananaoats','Walnut & banana oats','ti-coffee',['oats','banana','walnuts','honey','milk'],
  ["Bring the milk to a simmer in a pot.","Stir in the oats, cook 3-4 min.",
   "Top with sliced banana, walnuts and a drizzle of honey."],['pot'],1),
 ('avocadobananasmoothie','Avocado & banana smoothie','ti-glass',['avocado','banana','plantmilk','honey'],
  ["Add the avocado, banana, plant milk and honey to a blender.","Blend until smooth and creamy."],['blender'],1),
 ('beetrootapplesmoothie','Beetroot, apple & orange smoothie','ti-glass',['beetroot','apple','orange'],
  ["Chop the beetroot, apple and orange.","Blend with a splash of water until smooth."],['blender'],1),
]
for cid, name, icon, items, steps, equip, servings in SMOOTHIES:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['breakfast','snack'], 5, servings, equip, steps, ing)

# ================= ENERGY BITES =================
BITES = [
 ('walnuthoneybites','Walnut & honey energy bites','ti-coffee',['oats','walnuts','honey','peanutbutter']),
 ('almondvanillabites','Almond & vanilla energy bites','ti-coffee',['oats','almonds','vanilla','honey']),
 ('sesamehalvabites','Sesame tahini energy bites','ti-coffee',['tahini','sesameseeds','honey','oats']),
 ('raspberrypeanutbites','Raspberry & peanut butter energy bites','ti-coffee',['oats','peanutbutter','raspberries','honey']),
]
for cid, name, icon, items in BITES:
    ing = soup_ing(*items)
    steps = ["Mash or mix the ingredients together in a bowl until well combined.",
             "Roll into small bites and chill in the fridge for at least 20 min."]
    add_recipe([cid], name, icon, ['snack'], 10, 4, [], steps, ing)

# ================= WRAP / SANDWICH =================
WRAPS = [
 ('turkeyavocadowrap','Turkey & avocado wrap','ti-bread',['tortilla','turkey','avocado','salad'],
  ["Lay the turkey slices and avocado over the tortilla.","Add the salad leaves, roll up tightly and slice in half."],[]),
 ('eggspinachwrap','Egg & spinach wrap','ti-egg',['tortilla','eggs','spinach','mayo'],
  ["Scramble the eggs in a pan.","Spread the tortilla with mayo, add the spinach and scrambled egg, then roll up."],['pan']),
 ('hummuscucumberpita','Hummus, cucumber & pepper pita','ti-bread',['pita','hummus','cucumber','pepper'],
  ["Warm the pita if you like.","Spread with hummus and fill with sliced cucumber and pepper."],[]),
 ('tunaavocadosandwich','Tuna & avocado sandwich','ti-fish',['bread','tuna','avocado','lemon'],
  ["Mash the avocado with a squeeze of lemon.","Layer onto the bread with the tuna."],[]),
 ('chickpeatahiniwrap','Chickpea & tahini wrap','ti-bread',['tortilla','chickpeas','tahini','salad','lemon'],
  ["Lightly mash the chickpeas with the tahini and a squeeze of lemon.","Spread over the tortilla, add the salad leaves and roll up."],[]),
 ('fetacucumberdillwrap','Feta, cucumber & dill wrap','ti-bread',['pita','feta','cucumber','dill','oliveoil'],
  ["Crumble the feta into the pita.","Add sliced cucumber and dill, drizzle with olive oil."],[]),
 ('halloumipestowrap','Halloumi & pesto wrap','ti-cheese',['tortilla','halloumi','pesto','zucchini'],
  ["Fry the halloumi and sliced zucchini in a pan until golden, 2-3 min per side.",
   "Spread the tortilla with pesto, add the halloumi and zucchini, then roll up."],['pan']),
 ('baconeggcheesewrap','Bacon, egg & cheese wrap','ti-egg',['tortilla','bacon','eggs','cheese'],
  ["Fry the bacon in a pan until crisp, then scramble in the eggs.",
   "Spread the tortilla with the cheese, add the bacon and egg, then roll up."],['pan']),
]
for cid, name, icon, items, steps, equip in WRAPS:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['lunch','snack'], 10, 1, equip, steps, ing)

# ================= SKILLET / HASH =================
SKILLETS = [
 ('turkeypepperhash','Turkey & pepper hash','ti-meat',['turkey','pepper','potato','paprika'],
  ["Fry the diced potato in a pan for 8-10 min until starting to soften.",
   "Add the turkey and pepper, season with paprika, and cook 8 min more until cooked through."]),
 ('salmonasparagusskillet','Salmon & asparagus skillet','ti-fish',['salmon','asparagus','lemon','butter'],
  ["Melt the butter in a pan.","Cook the salmon 3-4 min per side.",
   "Add the asparagus for the last 4-5 min. Squeeze over lemon to serve."]),
 ('prawnzucchinigarlicskillet','Garlic prawn & zucchini skillet','ti-fish',['prawns','zucchini','garlic','chiliflakes'],
  ["Saúté the garlic and chili flakes in a pan for 1 min.",
   "Add the zucchini, cook 4 min.","Add the prawns, cook 2-3 min until pink."]),
 ('beefmushroomonionskillet','Beef, mushroom & onion skillet','ti-meat',['beef','mushroom','onion','parsley'],
  ["Saúté the onion in a pan for 3 min.",
   "Add the mushrooms, cook 5 min.","Add the beef, cook 3-4 min, then scatter with parsley."]),
 ('porkappleskillet','Pork & apple skillet','ti-meat',['pork','apple','onion'],
  ["Slice the pork, apple and onion.",
   "Fry the onion in a pan for 3 min, then add the pork and cook 5-6 min.",
   "Add the apple for the last 3-4 min until just softened."]),
 ('whitefishleekbutterskillet','White fish & leek skillet','ti-fish',['whitefish','leek','butter','lemon'],
  ["Saúté the leek in butter in a pan for 4 min until soft.",
   "Add the fish, cook 3-4 min per side. Squeeze over lemon to serve."]),
 ('chickpeaspinachpaprikaskillet','Spiced chickpea & spinach skillet','ti-bowl',['chickpeas','spinach','paprika','garlic'],
  ["Saúté the garlic and paprika in a pan for 1 min.",
   "Add the chickpeas, cook 3-4 min.","Stir in the spinach and cook 3 min more until wilted."]),
]
for cid, name, icon, items, steps in SKILLETS:
    ing = soup_ing(*items)
    add_recipe([cid], name, icon, ['dinner','lunch'], 22, 2, ['pan'], steps, ing)

# ================= validate & emit =================
all_ids = [r['id'] for r in recipes]
assert len(all_ids) == len(set(all_ids)), "duplicate generated ids!"
for r in recipes:
    for i in r['ing']:
        assert i['ref'] in P, f"unknown ingredient ref {i['ref']} in {r['id']}"

def js_str(r):
    def arr(lst): return '['+','.join(f"'{x}'" for x in lst)+']'
    def ingarr(ing):
        return '['+','.join(f"{{ref:'{i['ref']}',frac:{i['frac']}}}" for i in ing)+']'
    def steparr(steps):
        return '['+','.join(json.dumps(s, ensure_ascii=False) for s in steps)+']'
    name_js = json.dumps(r['name'], ensure_ascii=False)
    return (f"{{id:'{r['id']}',name:{name_js},icon:'{r['icon']}',type:{arr(r['type'])},"
            f"filters:{arr(r['filters'])},tags:{arr(r['tags'])},time:{r['time']},"
            f"protein:{r['protein']},kcal:{r['kcal']},servings:{r['servings']},"
            f"equip:{arr(r['equip'])},steps:{steparr(r['steps'])},ing:{ingarr(r['ing'])}}}")

snippet = ',\n'.join(js_str(r) for r in recipes)
out_path = r"C:\Users\swath\tuore-app\new_meals_snippet.js"
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(snippet)

print(f"Generated {len(recipes)} new recipes -> {out_path}")
print(f"Existing: {len(existing_ids)}, New total would be: {len(existing_ids)+len(recipes)}")

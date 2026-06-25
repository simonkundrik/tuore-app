# -*- coding: utf-8 -*-
"""Shared, side-effect-free helpers for recipe generation: P dict extraction,
ingredient display names, nutrition/price heuristics, and id allocation.
Reads index.html (pure) but writes nothing -- safe to import from any script."""
import re

HTML_PATH = r"C:\Users\swath\tuore-app\index.html"
html = open(HTML_PATH, encoding="utf-8").read()

P = {}
for m in re.finditer(
    r'(\w+):\{"nm":\s*"([^"]+)".*?"price":\s*([\d.]+).*?"unit":\s*"(kpl|kg)".*?"inStock":\s*(true|false)',
    html):
    key, nm, price, unit, instock = m.groups()
    P[key] = {"nm": nm, "price": float(price), "unit": unit, "inStock": instock == "true"}

assert len(P) > 100, f"only parsed {len(P)} P entries, regex likely broken"

existing_ids = set(re.findall(r"\{id:'(\w+)'", html))

TITLE = {
 'chicken':'chicken','cookedchicken':'chicken','beef':'beef','pork':'pork','turkey':'turkey',
 'lamb':'lamb','sausage':'sausage','bacon':'bacon','chorizo':'chorizo','mince':'beef mince',
 'salmon':'salmon','tuna':'tuna','whitefish':'white fish','prawns':'prawn','mussels':'mussel',
 'herring':'herring','tofu':'tofu','chickpeas':'chickpea','lentils':'lentil','blackbeans':'bean',
 'eggs':'egg','broccoli':'broccoli','cauliflower':'cauliflower','zucchini':'zucchini',
 'eggplant':'eggplant','cabbage':'cabbage','kale':'kale','leek':'leek','mushroom':'mushroom',
 'pepper':'pepper','cucumber':'cucumber','pumpkin':'pumpkin','rutabaga':'rutabaga',
 'fennel':'fennel','asparagus':'asparagus','radish':'radish','sweetcorn':'sweetcorn',
 'peas':'pea','beetroot':'beetroot','spinach':'spinach','carrot':'carrot',
 'sweetpotato':'sweet potato','potato':'potato','onion':'onion','avocado':'avocado',
 'rice':'rice','pasta':'pasta','quinoa':'quinoa','couscous':'couscous','barley':'barley',
 'buckwheat':'buckwheat','bread':'bread','pita':'pita','tortilla':'tortilla',
 'feta':'feta','halloumi':'halloumi','mozzarella':'mozzarella','parmesan':'parmesan',
 'ricotta':'ricotta','cheese':'cheese','yogurt':'yogurt','skyr':'skyr','rahka':'rahka',
 'basil':'basil','parsley':'parsley','dill':'dill','orange':'orange','mango':'mango',
 'pineapple':'pineapple','banana':'banana','apple':'apple','blueberries':'blueberry',
 'strawberries':'strawberry','raspberries':'raspberry','almonds':'almond','walnuts':'walnut',
 'garlic':'garlic','lemon':'lemon','oliveoil':'olive oil','butter':'butter','cream':'cream',
 'coconutmilk':'coconut milk','currypaste':'curry paste','soysauce':'soy sauce',
 'chiliflakes':'chili flakes','cumin':'cumin','paprika':'paprika','cinnamon':'cinnamon',
 'honey':'honey','vinegar':'vinegar','tahini':'tahini','sesameseeds':'sesame seeds',
 'pesto':'pesto','mayo':'mayo','peanutbutter':'peanut butter','vanilla':'vanilla',
 'oats':'oats','milk':'milk','plantmilk':'plant milk','stockcube':'stock cube',
 'freshtomato':'tomato','tomato':'canned tomato','hummus':'hummus','salad':'salad leaves',
}
def T(key): return TITLE.get(key, P[key]['nm'].lower())
def Cap(s): return s[0].upper()+s[1:]
MID = {'prawns':'prawns','mussels':'mussels','blackbeans':'beans'}
def M(key): return MID.get(key, T(key))
FISH = {'salmon','tuna','whitefish','prawns','mussels','herring'}
def protein_icon(key):
    if key in FISH: return 'ti-fish'
    if key in {'tofu','chickpeas','lentils','blackbeans'}: return 'ti-bowl'
    return 'ti-meat'

FRAC = {
 'chicken':1,'cookedchicken':.5,'beef':.4,'pork':1,'turkey':1,'lamb':.4,'sausage':1,'bacon':.5,
 'chorizo':.5,'mince':1,'salmon':.4,'tuna':1,'whitefish':1,'prawns':1,'mussels':1,'herring':1,
 'tofu':1,'chickpeas':1,'lentils':1,'blackbeans':1,'eggs':.3,
 'rice':.4,'pasta':.4,'quinoa':.4,'couscous':.4,'barley':.4,'buckwheat':.15,
 'broccoli':.5,'carrot':.5,'onion':1,'cauliflower':.5,'zucchini':1,'eggplant':1,'cabbage':.3,
 'sweetpotato':2,'potato':1,'spinach':.5,'kale':1,'leek':1,'mushroom':4,'pepper':.5,
 'cucumber':.5,'pumpkin':1,'rutabaga':1,'fennel':1,'asparagus':1,'radish':1,'sweetcorn':1,
 'peas':1,'beetroot':.5,'garlic':.33,'oliveoil':.1,'lemon':.5,'parsley':.3,'basil':.3,
 'dill':.5,'cumin':.05,'paprika':.15,'chiliflakes':.05,'cinnamon':.03,'soysauce':.2,
 'currypaste':.5,'coconutmilk':1,'cream':1,'cheese':.15,'feta':.5,'parmesan':.2,
 'mozzarella':.5,'butter':.1,'honey':.05,'vinegar':.05,'tahini':.15,'pesto':.5,'mayo':.2,
 'breadcrumbs':.3,'avocado':.5,'yogurt':1,'skyr':1,'rahka':1,'almonds':.1,'walnuts':.1,
 'sesameseeds':.1,'apple':.5,'orange':1,'mango':.5,'pineapple':.5,'banana':1,
 'blueberries':.25,'strawberries':.5,'raspberries':.5,'oats':.08,'milk':.2,'plantmilk':.2,
 'tomato':1,'freshtomato':1,'stockcube':.13,'hummus':.5,'salad':.33,'tortilla':.125,
 'pita':.4,'bread':.14,'peanutbutter':.1,'vanilla':.05,'halloumi':.4,'ricotta':1,
}

MEAT_FISH = {'chicken','cookedchicken','beef','pork','turkey','lamb','sausage','bacon','chorizo',
             'mince','salmon','tuna','whitefish','prawns','mussels','herring'}
ANIMAL_NONVEGAN = MEAT_FISH | {'eggs','cheese','feta','halloumi','mozzarella','parmesan','ricotta',
             'butter','cream','oatcream','yogurt','skyr','rahka','milk','honey'}
CARBY = {'rice','pasta','quinoa','couscous','barley','buckwheat','bread','pita','tortilla',
         'potato','sweetpotato'}
RICHFAT = {'cream','cheese','feta','halloumi','mozzarella','parmesan','coconutmilk','oliveoil',
           'butter','tahini','ricotta'}
PROTEIN_G = {'chicken':30,'cookedchicken':22,'beef':28,'pork':30,'turkey':26,'lamb':26,'sausage':18,
 'bacon':14,'chorizo':16,'mince':24,'salmon':26,'tuna':22,'whitefish':24,'prawns':18,'mussels':18,
 'herring':20,'tofu':16,'chickpeas':13,'lentils':15,'blackbeans':11,'eggs':13,'feta':9,'halloumi':17,
 'mozzarella':11,'parmesan':8,'ricotta':10,'cheese':7,'cream':2,'yogurt':9,'skyr':15,'rahka':11,
 'quinoa':6,'barley':4,'buckwheat':5,'almonds':5,'walnuts':4,'peanutbutter':6,'tahini':5}

def macro(ing_refs, servings):
    protein = sum(PROTEIN_G.get(r, 0) for r in ing_refs)
    has_carb = any(r in CARBY for r in ing_refs)
    has_fat = any(r in RICHFAT for r in ing_refs)
    kcal = 200 + protein*4 + (130 if has_carb else 0) + (80 if has_fat else 20)
    kcal = max(150, min(580, round(kcal/10)*10))
    protein = max(3, min(45, protein))
    return protein, kcal

def is_vegan(ing_refs):
    return not any(r in ANIMAL_NONVEGAN for r in ing_refs)
def is_veg(ing_refs):
    return not any(r in MEAT_FISH for r in ing_refs)
def is_lowcarb(ing_refs):
    return not any(r in CARBY for r in ing_refs)

def price_per_serving(ing_refs_fracs, servings):
    total = sum(P[r]['price']*f for r, f in ing_refs_fracs)
    return total/servings

def make_id(parts, used):
    base = ''.join(parts)
    cid = base
    n = 2
    while cid in used:
        cid = base+str(n); n += 1
    used.add(cid)
    return cid

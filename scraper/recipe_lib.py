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

# grams of carbohydrate contributed by a typical recipe-serving usage of each ingredient
CARB_G = {
 'oats':10,'berries':8,'milk':5,'eggs':1,'bread':12,'cheese':1,'salmon':0,'spinach':1,'carrot':6,
 'onion':5,'oatcream':2,'dill':0,'lentils':30,'tomato':5,'stockcube':1,'chicken':0,'potato':20,
 'paprika':1,'yogurt':5,'cookedchicken':0,'cucumber':2,'tortilla':15,'hummus':4,'salad':1,'pepper':4,
 'banana':23,'plantmilk':4,'rice':45,'mince':0,'tuna':0,'pasta':40,'broccoli':4,'feta':2,'garlic':1,
 'lemon':2,'beetroot':8,'oliveoil':0,'mushroom':2,'sweetpotato':18,'halloumi':2,'prawns':1,
 'coconutmilk':2,'currypaste':2,'leek':5,'soysauce':1,'peanutbutter':3,'quinoa':20,'chorizo':1,
 'pita':20,'avocado':4,'rahka':4,'apple':14,'beef':0,'pork':0,'whitefish':0,'sausage':2,'bacon':0,
 'tofu':2,'cream':3,'butter':0,'mozzarella':2,'freshtomato':4,'cabbage':3,'cauliflower':3,
 'eggplant':4,'zucchini':3,'sweetcorn':10,'peas':7,'orange':12,'blueberries':14,'strawberries':6,
 'chickpeas':27,'couscous':25,'blackbeans':22,'basil':0,'parsley':0,'cumin':0,'cinnamon':1,
 'chiliflakes':0,'honey':8,'vinegar':0,'turkey':0,'lamb':0,'herring':8,'mussels':4,'parmesan':1,
 'ricotta':4,'skyr':5,'radish':2,'fennel':4,'asparagus':3,'kale':3,'rutabaga':6,'pumpkin':6,
 'barley':22,'buckwheat':15,'breadcrumbs':8,'pineapple':11,'mango':13,'raspberries':5,'almonds':2,
 'walnuts':1,'sesameseeds':1,'pesto':1,'mayo':0,'tahini':1,'flour':20,'vanilla':1,'darkchocolate':8,
}
# grams of fat contributed by a typical recipe-serving usage of each ingredient
FAT_G = {
 'oats':2,'berries':0,'milk':2,'eggs':10,'bread':1,'cheese':5,'salmon':14,'spinach':0,'carrot':0,
 'onion':0,'oatcream':4,'dill':0,'lentils':1,'tomato':0,'stockcube':0,'chicken':12,'potato':0,
 'paprika':0,'yogurt':5,'cookedchicken':3,'cucumber':0,'tortilla':3,'hummus':4,'salad':0,'pepper':0,
 'banana':0,'plantmilk':2,'rice':0,'mince':10,'tuna':6,'pasta':1,'broccoli':0,'feta':13,'garlic':0,
 'lemon':0,'beetroot':0,'oliveoil':13,'mushroom':0,'sweetpotato':0,'halloumi':18,'prawns':1,
 'coconutmilk':9,'currypaste':1,'leek':0,'soysauce':0,'peanutbutter':8,'quinoa':2,'chorizo':18,
 'pita':1,'avocado':15,'rahka':1,'apple':0,'beef':15,'pork':6,'whitefish':2,'sausage':20,'bacon':12,
 'tofu':9,'cream':15,'butter':12,'mozzarella':8,'freshtomato':0,'cabbage':0,'cauliflower':0,
 'eggplant':0,'zucchini':0,'sweetcorn':1,'peas':0,'orange':0,'blueberries':0,'strawberries':0,
 'chickpeas':3,'couscous':0,'blackbeans':1,'basil':0,'parsley':0,'cumin':0,'cinnamon':0,
 'chiliflakes':0,'honey':0,'vinegar':0,'turkey':3,'lamb':18,'herring':14,'mussels':3,'parmesan':6,
 'ricotta':11,'skyr':0,'radish':0,'fennel':0,'asparagus':0,'kale':0,'rutabaga':0,'pumpkin':0,
 'barley':0,'buckwheat':1,'breadcrumbs':0,'pineapple':0,'mango':0,'raspberries':0,'almonds':7,
 'walnuts':8,'sesameseeds':5,'pesto':8,'mayo':10,'tahini':8,'flour':1,'vanilla':0,'darkchocolate':6,
}

def macro(ing_refs, servings):
    protein = sum(PROTEIN_G.get(r, 0) for r in ing_refs)
    carbs = sum(CARB_G.get(r, 0) for r in ing_refs)
    fat = sum(FAT_G.get(r, 0) for r in ing_refs)
    protein = max(3, min(45, protein))
    kcal = round((protein*4 + carbs*4 + fat*9)/10)*10
    return protein, carbs, fat, kcal

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

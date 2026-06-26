# -*- coding: utf-8 -*-
"""Maps K-Ruoka recipe ingredient phrases (Finnish, inflected) onto our
existing P-dict ingredient keys via stem substring matching -- the same
technique scraper.py already uses for include/exclude keyword matching,
which handles Finnish's many noun cases (porkkana/porkkanaa/porkkanan...)
without needing a real morphological analyzer.

Order matters: more specific stems must come before generic ones, since
we return the first match (e.g. 'valkosipulin' before 'sipuli', so garlic
doesn't get caught by the generic onion stem)."""

# Stems that are genuine pantry/seasoning staples not worth tracking as a
# priced shopping-list item (mirrors how salt/pepper are already implicit,
# untracked ingredients elsewhere in the app). Recipes that use only these
# beyond their mapped ingredients still count as fully covered.
IGNORE_STEMS = [
    'suola', 'mustapippur', 'valkopippur', 'maustepippur', 'cayennepippur',
    'kokonaista pippuria', 'pippuria', 'vesi', 'vettä', 'jäitä', 'jäät',
    'sokeri', 'siirappia', 'hillosokeri', 'raesokeri',
    'leivinjauhe', 'ruokasooda', 'soodaa', 'hiiva',
    'liivateleht', 'laakerinleht', 'maissitärkkely', 'perunajauho',
    'kaakaojauhe', 'kardemumma', 'neilikka', 'muskottipähkin', 'tähtianis',
    'cayenne', 'currya', 'currytahna', 'wasabia',
    'ruohosipul', 'minttua', 'minttu', 'korianter', 'tilli', 'rosmariini',
    'timjami', 'oregano', 'salvia', 'fenkolinsiemen',
    'sitruunankuor', 'sitruunan raastettu kuori', 'appelsiininkuor',
    'limetinkuor', 'inkivääri', 'vaniljatank', 'vaniljapalko',
    'ketsuppia', 'sinappia', 'majoneesia', 'mayoa', 'aiolia',
    'kalakastik', 'srirach', 'harissa', 'sambal', 'tabasco',
    'punaviini', 'valkoviini', 'samppanja', 'olutta',
    'taikina', 'piirakkataikin', 'lasagnelev', 'pizzapohj', 'digestivekeksej',
    'pastan keitinvet', 'gluteenitonta jauhoseo', 'mantelijauhe', 'mantelirouhe',
    'mantelilastu', 'kookoshiutale', 'rusinoita', 'granaattiomena',
    'tomaattiketsuppi', 'pizzakastik', 'pizzamauste', 'tacomauste',
    'garam masala', 'curryjauhe', 'currytahnaa',
    'syötäviä kukk', 'kapri', 'pekaanipähkin', 'cashewpähkin', 'hasselpähkin',
    'vihreitä papuja', 'kurkumaa', 'kasvirasvasekoite', 'chiansiemen',
    'salaattisiemensekoitus', 'gochujang', 'raakalakritsijauhe', 'kaurakeksej',
    'hoisinkastik', 'pinjansiemen', 'nonparell', 'vaahtoutuvaa vaniljakastik',
    'cosmopolitan-salaatti', 'auringonkukansiemen', 'soijapap', 'jalapeno',
    'maissilastu', 'pähkinäsekoitus', 'lehtisellerin vart', 'herneenvers',
    'passionhedelm', 'nektariin', 'päärynä', 'sushi nori', 'sämpyl',
    'naughty', 'pankojauho',
]

# (finnish_stem, P-dict key). productSpelling.fi is lowercased before
# matching, so stems here should already be lowercase.
FI_STEM_TO_KEY = [
    # --- proteins ---
    ('kananmunan valkuais', 'eggs'), ('kananmunan keltuais', 'eggs'),
    ('kananmuna', 'eggs'),
    ('katkarapu', 'prawns'),
    ('kirjolohi', 'salmon'), ('lohifile', 'salmon'), ('lohta', 'salmon'),
    ('kylmäsavu', 'salmon'), ('savulohi', 'salmon'), ('graavilohi', 'salmon'),
    ('fusilli', 'pasta'),
    ('silakk', 'herring'), ('silli', 'herring'),
    ('tonnikala', 'tuna'),
    ('kirjolohifile', 'salmon'),
    ('valkoinen kalafile', 'whitefish'), ('kalafile', 'whitefish'),
    ('naudan jauheliha', 'mince'), ('jauheliha', 'mince'),
    ('naudan ulkofile', 'beef'), ('naudanlihaa', 'beef'),
    ('porsaan sisäfile', 'pork'), ('porsaa', 'pork'),
    ('kalkkuna', 'turkey'),
    ('karitsa', 'lamb'), ('lampaan', 'lamb'),
    ('kanan fileesuikale', 'cookedchicken'), ('kanan fileepihv', 'chicken'),
    ('kanan ohutleik', 'chicken'), ('kanan rintafile', 'chicken'),
    ('kanan koipireis', 'chicken'), ('broilerin', 'chicken'),
    ('prosciutto', 'bacon'), ('kinkku', 'bacon'), ('pekoni', 'bacon'),
    ('chorizo', 'chorizo'), ('makkara', 'sausage'), ('nakki', 'sausage'),
    ('tofu', 'tofu'),
    ('kikherne', 'chickpeas'),
    ('punainen linssi', 'lentils'), ('linssej', 'lentils'), ('linssi', 'lentils'),
    ('mustapap', 'blackbeans'), ('kidneypap', 'blackbeans'), ('papuja suolaliem', 'blackbeans'),

    # --- dairy / eggs / fats ---
    ('voitaikina', None),  # explicit no-map (pastry dough, not plain butter)
    ('voita tai leivontamargariini', 'butter'), ('voita tai margariini', 'butter'),
    ('leivontamargariini', 'butter'), ('margariinia', 'butter'),
    ('voita sulatettuna', 'butter'), ('huoneenlämpöistä voi', 'butter'),
    ('pehmeää voi', 'butter'), ('voita', 'butter'),
    ('voisula', 'butter'), ('voinokare', 'butter'),
    ('kevytmaito', 'milk'), ('täysmaito', 'milk'), ('kevyt- tai täysmaito', 'milk'),
    ('kaurajuoma', 'plantmilk'), ('kauramaito', 'plantmilk'),
    ('soijamaito', 'plantmilk'), ('kookosmaito', 'coconutmilk'),
    ('kondensoitua maitoa', 'milk'), ('maitoa', 'milk'),
    ('kuohukerma', 'cream'), ('vispikerma', 'cream'), ('ruokakerma', 'cream'),
    ('ranskankerma', 'cream'), ('crème fraîche', 'cream'), ('kermaviili', 'cream'),
    ('smetana', 'cream'),
    ('vehnäjauho', 'flour'), ('ruisjauho', 'flour'), ('hiivaleipävehnäjauho', 'flour'),
    ('kaurajauho', 'flour'),
    ('korppujauho', 'breadcrumbs'),
    ('maustamaton tuorejuusto', 'rahka'), ('vaniljatuorejuusto', 'rahka'),
    ('tuorejuusto', 'rahka'), ('maitorahka', 'rahka'), ('rahka', 'rahka'),
    ('kreikkalainen jogurtti', 'yogurt'), ('turkkilaista', 'yogurt'), ('jogurtti', 'yogurt'),
    ('emmental-mozzarella', 'mozzarella'), ('mozzarella di bufala', 'mozzarella'),
    ('mozzarellajuusto', 'mozzarella'), ('mozzarella', 'mozzarella'),
    ('parmesaani', 'parmesan'), ('vuohenjuusto', 'feta'), ('fetajuusto', 'feta'),
    ('salaattijuusto', 'feta'), ('sinihomejuusto', 'feta'),
    ('mascarpone', 'ricotta'),
    ('cheddar', 'cheese'), ('juustoraaste', 'cheese'), ('juustoviipale', 'cheese'),
    ('sulatejuusto', 'cheese'),
    ('halloumi', 'halloumi'),

    # --- oils / vinegars ---
    ('seesamiöljy', 'oliveoil'), ('rypsiöljy', 'oliveoil'),
    ('ekstra-neitsytoliiviöljy', 'oliveoil'), ('oliiviöljy', 'oliveoil'),
    ('öljyä paistamiseen', 'oliveoil'), ('öljyä', 'oliveoil'),
    ('balsamiviinietikk', 'vinegar'), ('balsamietikk', 'vinegar'),
    ('omenaviinietikk', 'vinegar'), ('riisiviinietikk', 'vinegar'),
    ('punaviinietikk', 'vinegar'), ('valkoviinietikk', 'vinegar'),
    ('retikk', 'radish'),
    ('väkiviinaetikk', 'vinegar'), ('etikk', 'vinegar'),

    # --- veg ---
    ('valkosipulinkynsi', 'garlic'), ('valkosipulinkynt', 'garlic'),
    ('valkosipulijauhe', 'garlic'), ('valkosipuli', 'garlic'),
    ('punasipuli', 'onion'), ('salottisipuli', 'onion'), ('kevätsipuli', 'onion'),
    ('iso sipuli', 'onion'), ('pieni sipuli', 'onion'), ('sipulikuutio', 'onion'),
    ('sipul', 'onion'),
    ('kirsikkatomaat', 'freshtomato'), ('miniluumutomaat', 'freshtomato'),
    ('paseerattua tomaatti', 'tomato'), ('tomaattimurska', 'tomato'),
    ('tomaattisose', 'tomato'), ('kuorittuja tomaatteja', 'tomato'),
    ('yrttitomaattimurska', 'tomato'),
    ('tomaatti', 'freshtomato'),
    ('porkkan', 'carrot'),
    ('kurkku', 'cucumber'),
    ('keltainen paprika', 'pepper'), ('punainen paprika', 'pepper'),
    ('paprikajauhe', 'paprika'), ('savupaprikajauhe', 'paprika'),
    ('paprika', 'pepper'),
    ('kukkakaali', 'cauliflower'),
    ('parsakaali', 'broccoli'), ('brokkoli', 'broccoli'),
    ('punakaali', 'cabbage'), ('varhaiskaali', 'cabbage'), ('keräkaali', 'cabbage'),
    ('lehtikaali', 'kale'),
    ('kaali', 'cabbage'),
    ('fenkoli', 'fennel'),
    ('purjo', 'leek'),
    ('herkkusieni', 'mushroom'), ('sieni', 'mushroom'),
    ('kesäkurpitsa', 'zucchini'),
    ('munakoiso', 'eggplant'),
    ('palsternakka', 'rutabaga'), ('lanttu', 'rutabaga'), ('juuriselleri', 'rutabaga'),
    ('vihreä parsa', 'asparagus'), ('parsaa', 'asparagus'),
    ('retiis', 'radish'),
    ('myskikurpitsa', 'pumpkin'), ('kurpitsa', 'pumpkin'),
    ('bataat', 'sweetpotato'),
    ('peruna', 'potato'),
    ('herneitä', 'peas'), ('herneit', 'peas'),
    ('rucola', 'spinach'), ('lehtipinaatti', 'spinach'), ('babypinaatti', 'spinach'),
    ('pinaatti', 'spinach'),
    ('jääsalaatti', 'salad'), ('provence salaattisekoitus', 'salad'),
    ('provencale yrttiseos', 'salad'), ('salaattisekoitus', 'salad'),
    ('avokado', 'avocado'),
    ('punajuur', 'beetroot'),

    # --- carbs / pantry ---
    ('jasmiiniriisi', 'rice'), ('puuroriisi', 'rice'), ('risottoriisi', 'rice'),
    ('riisi', 'rice'),
    ('spagetti', 'pasta'), ('pastaa', 'pasta'),
    ('kvinoa', 'quinoa'),
    ('couscous', 'couscous'), ('kuskus', 'couscous'),
    ('ohrasuurimo', 'barley'), ('helmiohra', 'barley'),
    ('tattarihiutale', 'buckwheat'),
    ('kaurahiutale', 'oats'),
    ('tortillaleip', 'tortilla'),
    ('pitaleip', 'pita'),
    ('leipäjuusto', 'cheese'),
    ('hiivaleipä', 'bread'), ('ruisleip', 'bread'), ('leip', 'bread'),
    ('munanuudel', 'pasta'),
    ('aurinkokuivattuja tomaat', 'tomato'),
    ('luomu kauralese', 'oats'), ('kaurales', 'oats'),
    ('nautafondi', 'stockcube'),
    ('rasvatonta piimää', 'milk'), ('piimää', 'milk'),

    # --- fruit ---
    ('omena', 'apple'),
    ('appelsiinia', 'orange'), ('appelsiinin', 'orange'), ('appelsiini', 'orange'),
    ('banaani', 'banana'),
    ('sitruunanmehu', 'lemon'), ('sitruunan mehu', 'lemon'), ('sitruunamehu', 'lemon'),
    ('limetinmehu', 'lemon'), ('limetin mehu', 'lemon'), ('limetti', 'lemon'),
    ('sitruuna', 'lemon'),
    ('mansikoita', 'strawberries'), ('mansikka', 'strawberries'),
    ('vadelmia', 'raspberries'), ('vadelma', 'raspberries'),
    ('mustikoita', 'blueberries'), ('pensasmustikk', 'blueberries'), ('mustikka', 'blueberries'),
    ('puolukoita', 'berries'), ('karpaloita', 'berries'), ('marjasekoitus', 'berries'),
    ('mango', 'mango'),
    ('ananas', 'pineapple'),

    # --- nuts / seeds / spreads ---
    ('seesaminsiemen', 'sesameseeds'),
    ('mantelijauhe', None), ('mantelirouhe', None), ('mantelilastu', None),
    ('mantel', 'almonds'),
    ('saksanpähkin', 'walnuts'),
    ('maapähkinävoi', 'peanutbutter'), ('peanut butter', 'peanutbutter'),
    ('tahini', 'tahini'),
    ('hummus', 'hummus'),
    ('vihreä pesto', 'pesto'), ('arrabbiatapesto', 'pesto'), ('pesto', 'pesto'),

    # --- spices / flavorings that DO map ---
    ('juustokumina', 'cumin'), ('jeera', 'cumin'), ('kumina', 'cumin'),
    ('kaneli', 'cinnamon'),
    ('vaniljasokeri', 'vanilla'), ('vanilliinisokeri', None),
    ('chilirouhe', 'chiliflakes'), ('chilihiutale', 'chiliflakes'),
    ('mieto punainen chili', 'chiliflakes'), ('mietoa punaista chiliä', 'chiliflakes'),
    ('chilijauhe', 'chiliflakes'),
    ('juokseva hunaja', 'honey'), ('hunaja', 'honey'),
    ('punainen currytahna', 'currypaste'), ('currytahna', 'currypaste'),
    ('japanilaista soijakastik', 'soysauce'), ('kiinalaista soijakastik', 'soysauce'),
    ('soijakastik', 'soysauce'),
    ('dijon-sinappi', None),
    ('kasvisfondi', 'stockcube'), ('kanafondi', 'stockcube'), ('kasvisliemikuutio', 'stockcube'),
    ('basilikaa', 'basil'), ('basilika', 'basil'),
    ('persiljaa', 'parsley'), ('lehtipersilja', 'parsley'), ('persilja', 'parsley'),
    ('tummaa leivontasuklaa', 'darkchocolate'), ('valkoista leivontasuklaa', 'darkchocolate'),
    ('leivontamaitosuklaa', 'darkchocolate'), ('kaakaojauhetta (tummaa)', 'darkchocolate'),
    ('suklaa', 'darkchocolate'),

    # generic 'kana' (chicken) stem MUST stay last -- it's a substring of
    # 'porkkana' (carrot) and would otherwise misclassify any carrot
    # ingredient as chicken. Keeping it last lets every more-specific stem
    # (porkkan/kananmuna/kanafondi/kaali etc.) match first.
    ('kana', 'chicken'),
]


def classify(phrase_fi):
    """Returns ('mapped', key) | ('ignored', None) | ('unknown', phrase)."""
    p = phrase_fi.strip().lower()
    for stem, key in FI_STEM_TO_KEY:
        if stem in p:
            return ('mapped', key) if key else ('ignored', None)
    for stem in IGNORE_STEMS:
        if stem in p:
            return ('ignored', None)
    return ('unknown', p)

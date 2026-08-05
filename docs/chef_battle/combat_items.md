# COMBAT ITEMS — Kitchen Battle Arsenal

## Author note
Designed by project creator. Items are kitchen-themed artifacts used in the
Chef's Battle combat system. Combat is entertainment while chefs prepare real
dishes — the actual winner is always decided by audience vote on the best recipe.

---

## Item structure

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Display name (English) |
| `slug` | str | URL-safe identifier |
| `item_type` | str | `attack` or `defense` |
| `base_power` | int | Inherent power of the item |
| `max_bonus` | int | Always 3 — max moves a chef can invest on top |
| `rarity` | str | `common` / `uncommon` / `rare` / `epic` / `legendary` |
| `combat_log_text` | str | Short phrase shown in Combat Log |
| `emoji` | str | Display emoji |

**Total max damage/defense per move = base_power + max_bonus (3)**

## Rarity → base_power scale

| Rarity | base_power | Count (attack) | Count (defense) |
|--------|-----------|----------------|-----------------|
| Common | 1–2 | 35 | 35 |
| Uncommon | 3–4 | 25 | 25 |
| Rare | 5–6 | 20 | 20 |
| Epic | 7–8 | 13 | 13 |
| Legendary | 9–10 | 7 | 7 |
| **Total** | | **100** | **100** |

---

## ATTACK ITEMS (100)

### Common (base 1–2)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 1 | Rotten Tomato | rotten-tomato | 2 | 🍅 | hurled a rotten tomato |
| 2 | Stale Bread Crumb | stale-bread-crumb | 1 | 🍞 | flicked a stale bread crumb |
| 3 | Raw Onion Tears | raw-onion-tears | 2 | 🧅 | waved a raw onion menacingly |
| 4 | Wet Dishcloth Flick | wet-dishcloth-flick | 1 | 🧻 | snapped a wet dishcloth |
| 5 | Soggy Lettuce Slap | soggy-lettuce-slap | 1 | 🥬 | slapped with soggy lettuce |
| 6 | Overripe Banana Peel | overripe-banana-peel | 2 | 🍌 | flung an overripe banana |
| 7 | Flour Dust Puff | flour-dust-puff | 1 | ⚪ | blasted a flour dust cloud |
| 8 | Lemon Juice Squirt | lemon-juice-squirt | 2 | 🍋 | squirted lemon juice at the eyes |
| 9 | Cold Soup Splash | cold-soup-splash | 1 | 🍲 | splashed cold soup |
| 10 | Wilted Herb Whip | wilted-herb-whip | 1 | 🌿 | whipped with wilted herbs |
| 11 | Eggshell Flick | eggshell-flick | 1 | 🥚 | flicked an eggshell |
| 12 | Olive Pit Spit | olive-pit-spit | 2 | 🫒 | spat an olive pit |
| 13 | Garlic Breath Cloud | garlic-breath-cloud | 2 | 🧄 | unleashed a garlic breath cloud |
| 14 | Mustard Blob | mustard-blob | 2 | 🟡 | launched a mustard blob |
| 15 | Pickle Brine Splash | pickle-brine-splash | 1 | 🥒 | splashed pickle brine |
| 16 | Burnt Toast Throw | burnt-toast-throw | 2 | 🍞 | threw burnt toast |
| 17 | Soggy Noodle Whip | soggy-noodle-whip | 1 | 🍜 | whipped with a soggy noodle |
| 18 | Chili Flakes Flick | chili-flakes-flick | 2 | 🌶️ | flicked chili flakes |
| 19 | Vinegar Splash | vinegar-splash | 2 | 💧 | splashed vinegar |
| 20 | Overcooked Pea | overcooked-pea | 1 | 🫛 | pelted with an overcooked pea |
| 21 | Sardine Smell | sardine-smell | 2 | 🐟 | opened a tin of sardines nearby |
| 22 | Coffee Grounds Throw | coffee-grounds-throw | 1 | ☕ | threw wet coffee grounds |
| 23 | Parsley Sprig Whip | parsley-sprig-whip | 1 | 🌿 | whipped with a parsley sprig |
| 24 | Ketchup Squirt | ketchup-squirt | 2 | 🍅 | squirted ketchup |
| 25 | Stinky Cheese Chunk | stinky-cheese-chunk | 2 | 🧀 | lobbed a stinky cheese chunk |
| 26 | Beet Juice Splash | beet-juice-splash | 2 | 🫐 | splashed beet juice |
| 27 | Cold Porridge Glob | cold-porridge-glob | 1 | 🥣 | lobbed cold porridge |
| 28 | Rubbery Calamari | rubbery-calamari | 2 | 🦑 | threw rubbery calamari |
| 29 | Frozen Pea Blizzard | frozen-pea-blizzard | 1 | 🫛 | unleashed a frozen pea blizzard |
| 30 | Limp Asparagus | limp-asparagus | 1 | 🥦 | waved limp asparagus |
| 31 | Anchovy Throw | anchovy-throw | 2 | 🐟 | threw a slimy anchovy |
| 32 | Overboiled Egg | overboiled-egg | 2 | 🥚 | bounced an overboiled egg |
| 33 | Soggy Rice Ball | soggy-rice-ball | 1 | 🍚 | lobbed a soggy rice ball |
| 34 | Stale Cracker Crumble | stale-cracker-crumble | 1 | 🫙 | crumbled a stale cracker |
| 35 | Tomato Paste Glob | tomato-paste-glob | 2 | 🍅 | flung a tomato paste glob |

### Uncommon (base 3–4)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 36 | Cucumber Javelin | cucumber-javelin | 3 | 🥒 | threw a cucumber javelin |
| 37 | Potato Grenade | potato-grenade | 3 | 🥔 | lobbed a potato grenade |
| 38 | Ladle Swing | ladle-swing | 4 | 🥄 | swung a ladle |
| 39 | Wooden Spoon Slap | wooden-spoon-slap | 3 | 🥄 | delivered a wooden spoon slap |
| 40 | Rolling Pin Whack | rolling-pin-whack | 4 | ⚪ | whacked with a rolling pin |
| 41 | Carrot Javelin | carrot-javelin | 3 | 🥕 | hurled a carrot javelin |
| 42 | Apple Throw | apple-throw | 3 | 🍎 | threw a solid apple |
| 43 | Pasta Lasso | pasta-lasso | 3 | 🍝 | lassoed with spaghetti |
| 44 | Hot Sauce Tsunami | hot-sauce-tsunami | 4 | 🌶️ | unleashed a hot sauce tsunami |
| 45 | Butter Slide Trap | butter-slide-trap | 3 | 🧈 | laid a butter slide trap |
| 46 | Baguette Joust | baguette-joust | 4 | 🥖 | jousted with a baguette |
| 47 | Spatula Slap | spatula-slap | 3 | ⚪ | delivered a spatula slap |
| 48 | Pepper Mill Grind | pepper-mill-grind | 4 | ⚫ | ground pepper in the eyes |
| 49 | Whisk Tornado | whisk-tornado | 3 | ⚪ | spun a whisk tornado |
| 50 | Tongs Snap | tongs-snap | 4 | ⚪ | snapped tongs aggressively |
| 51 | Sauce Pistol | sauce-pistol | 3 | ⚪ | fired the sauce pistol |
| 52 | Frozen Fish Club | frozen-fish-club | 4 | 🐟 | clubbed with a frozen fish |
| 53 | Pineapple Cannonball | pineapple-cannonball | 4 | 🍍 | launched a pineapple cannonball |
| 54 | Coconut Skull Crusher | coconut-skull-crusher | 4 | 🥥 | dropped a coconut |
| 55 | Cabbage Head Bowler | cabbage-head-bowler | 3 | 🥬 | bowled a cabbage head |
| 56 | Leek Whip | leek-whip | 3 | 🌿 | whipped with a leek |
| 57 | Corn Cob Bat | corn-cob-bat | 4 | 🌽 | batted with a corn cob |
| 58 | Zucchini Club | zucchini-club | 3 | 🥒 | clubbed with a zucchini |
| 59 | Onion Avalanche | onion-avalanche | 3 | 🧅 | triggered an onion avalanche |
| 60 | Turnip Hammer | turnip-hammer | 4 | ⚪ | hammered with a turnip |

### Rare (base 5–6)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 61 | Wok Smash | wok-smash | 5 | 🍳 | smashed with a wok |
| 62 | Cast Iron Pan | cast-iron-pan | 6 | 🍳 | swung a cast iron pan |
| 63 | Kitchen Knife Throw | kitchen-knife-throw | 5 | 🔪 | threw a kitchen knife |
| 64 | Cleaver Toss | cleaver-toss | 6 | 🔪 | tossed a cleaver |
| 65 | Boiling Water Splash | boiling-water-splash | 5 | 💧 | splashed boiling water |
| 66 | Pressure Cooker Burst | pressure-cooker-burst | 6 | ⚪ | burst a pressure cooker |
| 67 | Heavy Cauldron Drop | heavy-cauldron-drop | 5 | 🫕 | dropped a heavy cauldron |
| 68 | Mixer Cyclone | mixer-cyclone | 5 | ⚪ | unleashed a mixer cyclone |
| 69 | Grater Rash | grater-rash | 5 | ⚪ | scraped with a box grater |
| 70 | Blender Lid-Off Explosion | blender-lid-off | 6 | ⚪ | blended with the lid off |
| 71 | Flambé Torch Blast | flambe-torch-blast | 5 | 🔥 | fired a flambé torch |
| 72 | Deep Fryer Splash | deep-fryer-splash | 6 | ⚪ | splashed hot fryer oil |
| 73 | Meat Tenderizer Rain | meat-tenderizer-rain | 6 | ⚪ | rained with a meat tenderizer |
| 74 | Espresso Machine Burst | espresso-machine-burst | 5 | ☕ | burst the espresso machine |
| 75 | Mandoline Blade Rush | mandoline-blade-rush | 6 | ⚪ | rushed with a mandoline |
| 76 | Stone Mortar Crush | stone-mortar-crush | 5 | ⚪ | crushed with a stone mortar |
| 77 | Smoking Hot Pan | smoking-hot-pan | 5 | 🍳 | attacked with a smoking pan |
| 78 | Stand Mixer Arm Swipe | stand-mixer-arm-swipe | 5 | ⚪ | swiped with a stand mixer arm |
| 79 | Boiling Syrup Spill | boiling-syrup-spill | 6 | 🍯 | spilled boiling syrup |
| 80 | Food Processor Spray | food-processor-spray | 6 | ⚪ | sprayed the food processor |

### Epic (base 7–8)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 81 | Salamander Grill Sauce | salamander-grill-sauce | 7 | 🔥 | unleashed the salamander grill sauce |
| 82 | Molten Chocolate Cannon | molten-chocolate-cannon | 7 | 🍫 | fired the molten chocolate cannon |
| 83 | Truffle Grenade | truffle-grenade | 8 | ⚫ | detonated a truffle grenade |
| 84 | Nitrogen Freeze Blast | nitrogen-freeze-blast | 7 | ⚪ | fired a liquid nitrogen blast |
| 85 | Chili Oil Tsunami | chili-oil-tsunami | 8 | 🌶️ | triggered a chili oil tsunami |
| 86 | Volcanic Lava Cake | volcanic-lava-cake | 7 | 🎂 | launched a volcanic lava cake |
| 87 | Giant Wok Slam | giant-wok-slam | 8 | 🍳 | slammed with a giant wok |
| 88 | Pressure Cooker Missile | pressure-cooker-missile | 7 | ⚪ | launched a pressure cooker missile |
| 89 | Industrial Blender Tornado | industrial-blender-tornado | 8 | ⚪ | spun an industrial blender tornado |
| 90 | Ghost Pepper Bomb | ghost-pepper-bomb | 7 | 🌶️ | detonated a ghost pepper bomb |
| 91 | Superheated Steam Jet | superheated-steam-jet | 8 | ⚪ | blasted with superheated steam |
| 92 | Flaming Cheese Wheel | flaming-cheese-wheel | 7 | 🧀 | rolled a flaming cheese wheel |
| 93 | Caramel Napalm | caramel-napalm | 8 | 🍯 | poured caramel napalm |

### Legendary (base 9–10)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 94 | The Gordon Scream | the-gordon-scream | 9 | 👨‍🍳 | unleashed the Gordon Scream |
| 95 | Nuclear Soufflé | nuclear-souffle | 9 | 🎂 | detonated a nuclear soufflé |
| 96 | The Kitchen Sink | the-kitchen-sink | 10 | 🚿 | threw the actual kitchen sink |
| 97 | Michelin Throwing Star | michelin-throwing-star | 10 | ⭐ | launched a Michelin throwing star |
| 98 | Apocalypse Curry | apocalypse-curry | 9 | 🍛 | unleashed the Apocalypse Curry |
| 99 | The Forbidden Habanero | the-forbidden-habanero | 10 | 🌶️ | used the Forbidden Habanero |
| 100 | The Dagda's Ladle | the-dagdas-ladle | 10 | 🥄 | struck with the Dagda's Ladle |

---

## DEFENSE ITEMS (100)

### Common (base 1–2)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 1 | Pot Lid Shield | pot-lid-shield | 2 | 🪣 | blocked with a pot lid |
| 2 | Kitchen Towel Block | kitchen-towel-block | 1 | 🧻 | deflected with a kitchen towel |
| 3 | Oven Mitt Parry | oven-mitt-parry | 2 | 🧤 | parried with an oven mitt |
| 4 | Paper Plate Shield | paper-plate-shield | 1 | ⚪ | hid behind a paper plate |
| 5 | Colander Helmet | colander-helmet | 2 | ⚪ | wore a colander as helmet |
| 6 | Dish Sponge Block | dish-sponge-block | 1 | ⚪ | blocked with a dish sponge |
| 7 | Bread Loaf Wall | bread-loaf-wall | 2 | 🍞 | hid behind a bread loaf |
| 8 | Salad Bowl Duck | salad-bowl-duck | 1 | 🥗 | ducked inside a salad bowl |
| 9 | Apron Flap | apron-flap | 1 | ⚪ | flapped the apron defensively |
| 10 | Pizza Box Shield | pizza-box-shield | 2 | 🍕 | raised a pizza box shield |
| 11 | Tin Foil Armor | tin-foil-armor | 2 | ⚪ | wrapped in tin foil armor |
| 12 | Plastic Wrap Cocoon | plastic-wrap-cocoon | 1 | ⚪ | cocooned in plastic wrap |
| 13 | Takeaway Container Stack | takeaway-container-stack | 1 | ⚪ | stacked takeaway containers |
| 14 | Egg Carton Cushion | egg-carton-cushion | 1 | 🥚 | cushioned with an egg carton |
| 15 | Pot Holder Parry | pot-holder-parry | 2 | ⚪ | parried with a pot holder |
| 16 | Mixing Bowl Helmet | mixing-bowl-helmet | 2 | ⚪ | wore a mixing bowl as helmet |
| 17 | Cereal Box Wall | cereal-box-wall | 1 | ⚪ | hid behind a cereal box |
| 18 | Baguette Block | baguette-block | 2 | 🥖 | blocked with a baguette |
| 19 | Cabbage Leaf Cloak | cabbage-leaf-cloak | 1 | 🥬 | cloaked in cabbage leaves |
| 20 | Pasta Colander | pasta-colander | 1 | ⚪ | used a colander as shield |
| 21 | Stack of Pancakes | stack-of-pancakes | 2 | 🥞 | hid behind a pancake stack |
| 22 | Bread Basket | bread-basket | 1 | 🧺 | blocked with a bread basket |
| 23 | Kitchen Roll Tower | kitchen-roll-tower | 1 | 🧻 | built a kitchen roll tower |
| 24 | Sieve Deflect | sieve-deflect | 2 | ⚪ | deflected through a sieve |
| 25 | Silicone Spatula Block | silicone-spatula-block | 1 | ⚪ | blocked with a silicone spatula |
| 26 | Butter Paper Shield | butter-paper-shield | 1 | ⚪ | hid behind butter paper |
| 27 | Cupcake Tray Wall | cupcake-tray-wall | 2 | ⚪ | raised a cupcake tray wall |
| 28 | Rubber Glove Block | rubber-glove-block | 1 | ⚪ | blocked with rubber gloves |
| 29 | Dish Rack Barrier | dish-rack-barrier | 2 | ⚪ | hid behind a dish rack |
| 30 | Wet Cloth Wrap | wet-cloth-wrap | 1 | 🧻 | wrapped in a wet cloth |
| 31 | Lunch Box Shield | lunch-box-shield | 2 | ⚪ | raised a lunch box shield |
| 32 | Bamboo Steamer Lid | bamboo-steamer-lid | 2 | ⚪ | blocked with a bamboo steamer lid |
| 33 | Cork Trivets | cork-trivets | 1 | ⚪ | stacked cork trivets |
| 34 | Tea Cozy Helmet | tea-cozy-helmet | 1 | ☕ | wore a tea cozy as helmet |
| 35 | Salad Spinner Spin | salad-spinner-spin | 2 | ⚪ | deflected with a salad spinner |

### Uncommon (base 3–4)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 36 | Cutting Board Parry | cutting-board-parry | 3 | ⚪ | parried with a cutting board |
| 37 | Heavy Pot Lid | heavy-pot-lid | 4 | 🪣 | blocked with a heavy pot lid |
| 38 | Cast Iron Lid | cast-iron-lid | 4 | 🍳 | raised a cast iron lid |
| 39 | Wok Shield | wok-shield | 3 | 🍳 | held up a wok shield |
| 40 | Baking Sheet Wall | baking-sheet-wall | 3 | ⚪ | raised a baking sheet wall |
| 41 | Steel Bowl Helmet | steel-bowl-helmet | 4 | ⚪ | wore a steel bowl helmet |
| 42 | Dutch Oven Lid | dutch-oven-lid | 4 | 🫕 | blocked with a dutch oven lid |
| 43 | Marble Rolling Pin Block | marble-rolling-pin-block | 3 | ⚪ | blocked with a marble rolling pin |
| 44 | Wooden Chopping Board | wooden-chopping-board | 3 | ⚪ | raised a wooden chopping board |
| 45 | Catering Tray Shield | catering-tray-shield | 4 | ⚪ | raised a catering tray |
| 46 | Stockpot Lid Smash Back | stockpot-lid-smash-back | 4 | ⚪ | smashed back with a stockpot lid |
| 47 | Roasting Pan Wall | roasting-pan-wall | 3 | ⚪ | raised a roasting pan wall |
| 48 | Pizza Peel Deflect | pizza-peel-deflect | 4 | 🍕 | deflected with a pizza peel |
| 49 | Knife Block Bunker | knife-block-bunker | 3 | 🔪 | hid behind a knife block |
| 50 | Serving Dome Cover | serving-dome-cover | 3 | ⚪ | covered with a serving dome |
| 51 | Pressure Cooker Lid Seal | pressure-cooker-lid-seal | 4 | ⚪ | sealed with a pressure cooker lid |
| 52 | Deep Dish Pan | deep-dish-pan | 3 | ⚪ | blocked with a deep dish pan |
| 53 | Tagine Lid | tagine-lid | 4 | ⚪ | deflected with a tagine lid |
| 54 | Paella Pan Shield | paella-pan-shield | 3 | ⚪ | raised a paella pan shield |
| 55 | Restaurant Cloche | restaurant-cloche | 4 | ⚪ | hid under a restaurant cloche |
| 56 | Enamel Pot Lid | enamel-pot-lid | 3 | ⚪ | blocked with an enamel pot lid |
| 57 | Griddle Block | griddle-block | 4 | ⚪ | blocked with a griddle |
| 58 | Cast Iron Skillet | cast-iron-skillet | 4 | 🍳 | raised a cast iron skillet |
| 59 | Bread Proofing Basket | bread-proofing-basket | 3 | 🧺 | hid inside a proofing basket |
| 60 | Pasta Pot Fortress | pasta-pot-fortress | 3 | ⚪ | hid behind a pasta pot |

### Rare (base 5–6)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 61 | Chef's Steel Apron | chefs-steel-apron | 5 | ⚪ | wore a steel apron |
| 62 | Triple-Layer Pot Stack | triple-layer-pot-stack | 6 | ⚪ | stacked three pots as shield |
| 63 | Industrial Mixing Bowl | industrial-mixing-bowl | 5 | ⚪ | hid inside an industrial mixing bowl |
| 64 | Walk-in Fridge Door | walk-in-fridge-door | 6 | ⚪ | slammed a walk-in fridge door |
| 65 | Full Body Oven Mitt | full-body-oven-mitt | 5 | ⚪ | wore a full-body oven mitt |
| 66 | Steel Cauldron Fortress | steel-cauldron-fortress | 6 | ⚪ | hid inside a steel cauldron |
| 67 | Marble Countertop Slab | marble-countertop-slab | 6 | ⚪ | raised a marble countertop slab |
| 68 | Thick Cutting Board Tower | thick-cutting-board-tower | 5 | ⚪ | stacked a thick cutting board tower |
| 69 | Salamander Grill Shield | salamander-grill-shield | 5 | ⚪ | blocked with a salamander grill |
| 70 | Commercial Baking Rack | commercial-baking-rack | 6 | ⚪ | hid behind a commercial baking rack |
| 71 | Giant Stockpot Dome | giant-stockpot-dome | 6 | ⚪ | hid under a giant stockpot dome |
| 72 | Cast Iron Dutch Oven Suit | cast-iron-dutch-oven-suit | 5 | ⚪ | wore a dutch oven suit |
| 73 | Smoking Cloche Cloud | smoking-cloche-cloud | 6 | ⚪ | hid in a smoking cloche cloud |
| 74 | Restaurant Tray Tower | restaurant-tray-tower | 5 | ⚪ | stacked a restaurant tray tower |
| 75 | Industrial Pot Lid Dome | industrial-pot-lid-dome | 5 | ⚪ | blocked with an industrial pot lid |
| 76 | Whetstone Wall | whetstone-wall | 6 | ⚪ | raised a whetstone wall |
| 77 | Teflon Force Field | teflon-force-field | 5 | ⚪ | activated a teflon force field |
| 78 | Heavy Granite Pestle Block | heavy-granite-pestle-block | 6 | ⚪ | blocked with a granite pestle |
| 79 | Enchanted Chef Hat | enchanted-chef-hat | 5 | 👨‍🍳 | deflected with an enchanted chef hat |
| 80 | The Inverted Wok Dome | inverted-wok-dome | 6 | 🍳 | hid under an inverted wok dome |

### Epic (base 7–8)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 81 | Titanium Wok Shield | titanium-wok-shield | 7 | ⚪ | raised a titanium wok shield |
| 82 | Grandma's Cast Iron Fortress | grandmas-cast-iron-fortress | 8 | 🍳 | hid in grandma's cast iron fortress |
| 83 | Molecular Gastronomy Gel Shield | molecular-gel-shield | 7 | ⚪ | activated a molecular gel shield |
| 84 | Liquid Nitrogen Ice Wall | liquid-nitrogen-ice-wall | 8 | ⚪ | built a liquid nitrogen ice wall |
| 85 | The Unbreakable Tagine | unbreakable-tagine | 7 | ⚪ | hid under the unbreakable tagine |
| 86 | Diamond-Hard Mortar | diamond-hard-mortar | 8 | ⚪ | blocked with a diamond-hard mortar |
| 87 | Chef's Sacred Chopping Board | chefs-sacred-chopping-board | 7 | ⚪ | raised the sacred chopping board |
| 88 | The Indestructible Colander | indestructible-colander | 8 | ⚪ | blocked with the indestructible colander |
| 89 | Ancient Copper Cloche | ancient-copper-cloche | 7 | ⚪ | hid under an ancient copper cloche |
| 90 | The Eternal Pot Lid | eternal-pot-lid | 8 | ⚪ | raised the eternal pot lid |
| 91 | Skellig Stone Stockpot | skellig-stone-stockpot | 7 | ⚪ | hid inside the Skellig stone stockpot |
| 92 | Blessed Baking Stone | blessed-baking-stone | 8 | ⚪ | blocked with a blessed baking stone |
| 93 | Enchanted Restaurant Dome | enchanted-restaurant-dome | 7 | ⚪ | activated an enchanted restaurant dome |

### Legendary (base 9–10)

| # | Name | Slug | Power | Emoji | Combat log text |
|---|------|------|-------|-------|-----------------|
| 94 | The Ogham Cutting Board | the-ogham-cutting-board | 9 | ⚪ | raised the Ogham Cutting Board |
| 95 | The Tír na nÓg Wok | the-tir-na-nog-wok | 10 | 🍳 | blocked with the Tír na nÓg Wok |
| 96 | Michelin Shield of Honor | michelin-shield-of-honor | 9 | ⭐ | raised the Michelin Shield of Honor |
| 97 | Grandma's Indestructible Apron | grandmas-indestructible-apron | 10 | ⚪ | activated Grandma's Indestructible Apron |
| 98 | Giant's Causeway Dome | giants-causeway-dome | 10 | ⚪ | hid under the Giant's Causeway Dome |
| 99 | The Last Line of Pots | the-last-line-of-pots | 9 | ⚪ | raised the Last Line of Pots |
| 100 | Nuada's Silver Pot Lid | nuadas-silver-pot-lid | 10 | ⚪ | raised Nuada's Silver Pot Lid |

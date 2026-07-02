"""
Generate all static image assets for Chef Battles.

Usage:
  python manage.py generate_battle_assets               # everything
  python manage.py generate_battle_assets --type levels
  python manage.py generate_battle_assets --type rarity
  python manage.py generate_battle_assets --type icons
  python manage.py generate_battle_assets --type artifacts
  python manage.py generate_battle_assets --type artifacts --rarity common
  python manage.py generate_battle_assets --skip-existing
"""

import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from recipes.management.commands.generate_recipe import fetch_image_bytes  # noqa: E402

STYLE = (
    "flat digital illustration, game item icon style, square format, "
    "rich saturated colours, dark navy background, centered composition, "
    "no text, no watermarks, no people, clean edges"
)

RARITY_COLOURS = {
    "common":    "grey-white palette, plain border",
    "uncommon":  "green palette, glowing green border",
    "rare":      "blue palette, glowing blue border",
    "epic":      "purple palette, glowing purple border",
    "legendary": "gold-orange palette, radiant golden border, dramatic glow",
}

# ── Level badge prompts ────────────────────────────────────────────────────────

LEVEL_PROMPTS = {
    "level-1": (
        "Chef's apron badge, level 1, white apron icon on dark navy, "
        "simple clean design, " + STYLE
    ),
    "level-2": (
        "Chef's hat badge, level 2, classic toque blanche on dark navy, "
        "clean design, " + STYLE
    ),
    "level-3": (
        "Kitchen knife badge, level 3, gleaming chef's knife on dark navy, "
        "confident design, " + STYLE
    ),
    "level-4": (
        "Cast iron pan badge, level 4, glowing cast iron skillet on dark navy, "
        "powerful design, " + STYLE
    ),
    "level-5": (
        "Flaming wok badge, level 5, wok with dramatic flames on dark navy, "
        "fierce design, " + STYLE
    ),
    "culinary-hero": (
        "CulinEire Hero badge, legendary chef crown made of kitchen utensils — "
        "knives, ladles, spatulas forming a crown, gold and fire, radiant glow, "
        "dark navy background, epic game badge style, " + STYLE
    ),
}

# ── Rarity frame prompts ───────────────────────────────────────────────────────

RARITY_PROMPTS = {
    rarity: (
        f"Artifact item frame for a cooking battle game, {rarity} rarity tier, "
        f"{colour}, ornate border frame with empty centre for an icon, "
        f"dark navy background, " + STYLE
    )
    for rarity, colour in RARITY_COLOURS.items()
}

# ── UI icon prompts ────────────────────────────────────────────────────────────

ICON_PROMPTS = {
    "icon-attack":   "Sword and fork crossed, attack action icon, red-orange glow, dark navy, " + STYLE,
    "icon-defense":  "Shield made of a pot lid, defense action icon, blue glow, dark navy, " + STYLE,
    "icon-lock":     "Golden padlock with a chef's hat engraved, ingredient lock icon, gold glow, dark navy, " + STYLE,
    "icon-energy":   "Lightning bolt made from a kitchen knife silhouette, energy icon, electric yellow, dark navy, " + STYLE,
    "icon-ready":    "Green checkmark inside a chef's hat, ready signal icon, bright green, dark navy, " + STYLE,
    "icon-slot":     "Hourglass filled with spices, battle slot timer icon, warm amber, dark navy, " + STYLE,
    "icon-victory":  "Trophy made of stacked pots and pans, victory icon, gold, dark navy, " + STYLE,
    "icon-chat":     "Speech bubble with a fork and knife inside, audience chat icon, teal, dark navy, " + STYLE,
}

# ── Artifact items ─────────────────────────────────────────────────────────────

ATTACK_ITEMS = [
    ("rotten-tomato", "common", "rotten tomato dripping"),
    ("stale-bread-crumb", "common", "stale bread crumb"),
    ("raw-onion-tears", "common", "raw onion with teardrops"),
    ("wet-dishcloth-flick", "common", "wet dishcloth mid-flick"),
    ("soggy-lettuce-slap", "common", "soggy limp lettuce leaf"),
    ("overripe-banana-peel", "common", "overripe brown banana"),
    ("flour-dust-puff", "common", "cloud of flour dust"),
    ("lemon-juice-squirt", "common", "lemon squirting juice"),
    ("cold-soup-splash", "common", "bowl of cold soup splashing"),
    ("wilted-herb-whip", "common", "wilted herbs drooping"),
    ("eggshell-flick", "common", "cracked eggshell"),
    ("olive-pit-spit", "common", "olive pit mid-air"),
    ("garlic-breath-cloud", "common", "garlic clove with green cloud"),
    ("mustard-blob", "common", "yellow mustard blob splat"),
    ("pickle-brine-splash", "common", "pickle jar splashing brine"),
    ("burnt-toast-throw", "common", "black burnt toast"),
    ("soggy-noodle-whip", "common", "limp soggy noodle"),
    ("chili-flakes-flick", "common", "chili flakes mid-scatter"),
    ("vinegar-splash", "common", "vinegar bottle splashing"),
    ("overcooked-pea", "common", "wrinkled overcooked pea"),
    ("sardine-smell", "common", "open sardine tin with stink lines"),
    ("coffee-grounds-throw", "common", "wet coffee grounds clump"),
    ("parsley-sprig-whip", "common", "parsley sprig mid-whip"),
    ("ketchup-squirt", "common", "ketchup bottle squirting"),
    ("stinky-cheese-chunk", "common", "stinky cheese chunk with odour waves"),
    ("beet-juice-splash", "common", "beet root splashing purple juice"),
    ("cold-porridge-glob", "common", "grey porridge glob mid-air"),
    ("rubbery-calamari", "common", "rubbery calamari ring"),
    ("frozen-pea-blizzard", "common", "frozen peas flying like projectiles"),
    ("limp-asparagus", "common", "limp drooping asparagus spear"),
    ("anchovy-throw", "common", "slimy anchovy mid-throw"),
    ("overboiled-egg", "common", "overboiled egg with cracked shell"),
    ("soggy-rice-ball", "common", "wet falling apart rice ball"),
    ("stale-cracker-crumble", "common", "crumbling stale cracker"),
    ("tomato-paste-glob", "common", "tomato paste glob splat"),
    ("cucumber-javelin", "uncommon", "cucumber used as a javelin"),
    ("potato-grenade", "uncommon", "potato shaped like a grenade with pin"),
    ("ladle-swing", "uncommon", "metal ladle mid-swing with motion blur"),
    ("wooden-spoon-slap", "uncommon", "wooden spoon impact motion"),
    ("rolling-pin-whack", "uncommon", "rolling pin swinging"),
    ("carrot-javelin", "uncommon", "carrot thrown like a javelin"),
    ("apple-throw", "uncommon", "red apple mid-throw"),
    ("pasta-lasso", "uncommon", "spaghetti strand as lasso"),
    ("hot-sauce-tsunami", "uncommon", "hot sauce bottle erupting in tsunami"),
    ("butter-slide-trap", "uncommon", "stick of butter as a slide trap"),
    ("baguette-joust", "uncommon", "baguette used as jousting lance"),
    ("spatula-slap", "uncommon", "metal spatula mid-slap"),
    ("pepper-mill-grind", "uncommon", "pepper mill grinding aggressively"),
    ("whisk-tornado", "uncommon", "whisk spinning tornado vortex"),
    ("tongs-snap", "uncommon", "tongs snapping dramatically"),
    ("sauce-pistol", "uncommon", "sauce squeeze bottle shaped like pistol"),
    ("frozen-fish-club", "uncommon", "frozen whole fish as a club"),
    ("pineapple-cannonball", "uncommon", "pineapple as cannonball"),
    ("coconut-skull-crusher", "uncommon", "coconut falling with crack lines"),
    ("cabbage-head-bowler", "uncommon", "cabbage head rolling like bowling ball"),
    ("leek-whip", "uncommon", "leek used as a whip"),
    ("corn-cob-bat", "uncommon", "corn cob as baseball bat"),
    ("zucchini-club", "uncommon", "large zucchini as a club"),
    ("onion-avalanche", "uncommon", "avalanche of onions rolling"),
    ("turnip-hammer", "uncommon", "turnip shaped like a hammer"),
    ("wok-smash", "rare", "iron wok smashing with sparks"),
    ("cast-iron-pan", "rare", "cast iron pan swinging with force"),
    ("kitchen-knife-throw", "rare", "kitchen knife spinning mid-throw"),
    ("cleaver-toss", "rare", "heavy cleaver spinning mid-air"),
    ("boiling-water-splash", "rare", "pot of boiling water splashing with steam"),
    ("pressure-cooker-burst", "rare", "pressure cooker exploding steam"),
    ("heavy-cauldron-drop", "rare", "heavy cauldron dropping from above"),
    ("mixer-cyclone", "rare", "stand mixer spinning cyclone"),
    ("grater-rash", "rare", "box grater mid-scrape with sparks"),
    ("blender-lid-off", "rare", "blender with lid flying off explosion"),
    ("flambe-torch-blast", "rare", "kitchen blowtorch fire blast"),
    ("deep-fryer-splash", "rare", "deep fryer splashing hot oil sparks"),
    ("meat-tenderizer-rain", "rare", "meat tenderizer raining blows"),
    ("espresso-machine-burst", "rare", "espresso machine bursting steam"),
    ("mandoline-blade-rush", "rare", "mandoline slicer blade rushing"),
    ("stone-mortar-crush", "rare", "stone mortar and pestle crushing"),
    ("smoking-hot-pan", "rare", "smoking pan on fire"),
    ("stand-mixer-arm-swipe", "rare", "stand mixer arm swiping"),
    ("boiling-syrup-spill", "rare", "caramel syrup spilling boiling"),
    ("food-processor-spray", "rare", "food processor spraying contents"),
    ("salamander-grill-sauce", "epic", "hot sauce erupting in flames from a salamander grill, purple glow"),
    ("molten-chocolate-cannon", "epic", "chocolate cannon firing molten streams, purple glow"),
    ("truffle-grenade", "epic", "black truffle as grenade with fuse, dark dramatic"),
    ("nitrogen-freeze-blast", "epic", "liquid nitrogen freeze ray blast, icy blue epic glow"),
    ("chili-oil-tsunami", "epic", "tsunami wave of red chili oil, epic scale"),
    ("volcanic-lava-cake", "epic", "lava cake erupting like volcano, molten core"),
    ("giant-wok-slam", "epic", "enormous wok slamming ground with shockwave, purple glow"),
    ("pressure-cooker-missile", "epic", "pressure cooker as guided missile with trail"),
    ("industrial-blender-tornado", "epic", "industrial blender creating tornado vortex"),
    ("ghost-pepper-bomb", "epic", "ghost pepper exploding like bomb, purple fire"),
    ("superheated-steam-jet", "epic", "superheated steam jet like rocket engine"),
    ("flaming-cheese-wheel", "epic", "giant cheese wheel rolling on fire"),
    ("caramel-napalm", "epic", "caramel dripping like napalm, dark epic"),
    ("the-gordon-scream", "legendary", "chef's mouth open in a powerful scream, golden radiant energy waves, legendary glow, no face details"),
    ("nuclear-souffle", "legendary", "soufflé rising like a nuclear mushroom cloud, gold legendary"),
    ("the-kitchen-sink", "legendary", "actual kitchen sink as thrown weapon, gold legendary glow"),
    ("michelin-throwing-star", "legendary", "Michelin star shaped as throwing star, gold radiant"),
    ("apocalypse-curry", "legendary", "curry pot erupting apocalyptic fire and spice clouds, legendary"),
    ("the-forbidden-habanero", "legendary", "single habanero pepper radiating forbidden dark power, gold legendary"),
    ("the-dagdas-ladle", "legendary", "the Dagda's giant golden ladle radiating heavenly light, legendary artifact"),
]

DEFENSE_ITEMS = [
    ("pot-lid-shield", "common", "pot lid held as shield"),
    ("kitchen-towel-block", "common", "kitchen towel used as deflection"),
    ("oven-mitt-parry", "common", "oven mitt raised in parry"),
    ("paper-plate-shield", "common", "paper plate as tiny shield"),
    ("colander-helmet", "common", "colander worn as helmet"),
    ("dish-sponge-block", "common", "dish sponge as shield block"),
    ("bread-loaf-wall", "common", "bread loaf as wall"),
    ("salad-bowl-duck", "common", "salad bowl as duck-and-cover"),
    ("apron-flap", "common", "apron flapping defensively"),
    ("pizza-box-shield", "common", "pizza box as shield"),
    ("tin-foil-armor", "common", "tin foil wrapped as armor"),
    ("plastic-wrap-cocoon", "common", "plastic wrap cocoon"),
    ("takeaway-container-stack", "common", "takeaway containers stacked as wall"),
    ("egg-carton-cushion", "common", "egg carton as cushion"),
    ("pot-holder-parry", "common", "pot holder raised in parry"),
    ("mixing-bowl-helmet", "common", "mixing bowl worn as helmet"),
    ("cereal-box-wall", "common", "cereal box as wall"),
    ("baguette-block", "common", "baguette as blocking rod"),
    ("cabbage-leaf-cloak", "common", "cabbage leaves as cloak"),
    ("pasta-colander", "common", "pasta colander as shield"),
    ("stack-of-pancakes", "common", "stack of pancakes as cushion wall"),
    ("bread-basket", "common", "bread basket raised as shield"),
    ("kitchen-roll-tower", "common", "kitchen roll tower barrier"),
    ("sieve-deflect", "common", "sieve used to deflect"),
    ("silicone-spatula-block", "common", "silicone spatula as block"),
    ("butter-paper-shield", "common", "butter paper as shield"),
    ("cupcake-tray-wall", "common", "cupcake tray raised as wall"),
    ("rubber-glove-block", "common", "rubber gloves as block"),
    ("dish-rack-barrier", "common", "dish rack as barrier"),
    ("wet-cloth-wrap", "common", "wet cloth wrapped around as shield"),
    ("lunch-box-shield", "common", "lunch box raised as shield"),
    ("bamboo-steamer-lid", "common", "bamboo steamer lid as shield"),
    ("cork-trivets", "common", "cork trivets stacked as barrier"),
    ("tea-cozy-helmet", "common", "tea cozy worn as helmet"),
    ("salad-spinner-spin", "common", "salad spinner spinning as deflection"),
    ("cutting-board-parry", "uncommon", "wooden cutting board as parry shield"),
    ("heavy-pot-lid", "uncommon", "heavy pot lid raised as shield"),
    ("cast-iron-lid", "uncommon", "cast iron lid raised as shield"),
    ("wok-shield", "uncommon", "wok held as round shield"),
    ("baking-sheet-wall", "uncommon", "baking sheet as wall"),
    ("steel-bowl-helmet", "uncommon", "steel mixing bowl as helmet"),
    ("dutch-oven-lid", "uncommon", "dutch oven lid as shield"),
    ("marble-rolling-pin-block", "uncommon", "marble rolling pin as block"),
    ("wooden-chopping-board", "uncommon", "wooden chopping board raised"),
    ("catering-tray-shield", "uncommon", "catering tray as shield"),
    ("stockpot-lid-smash-back", "uncommon", "stockpot lid used to smash back"),
    ("roasting-pan-wall", "uncommon", "roasting pan raised as wall"),
    ("pizza-peel-deflect", "uncommon", "pizza peel deflecting attacks"),
    ("knife-block-bunker", "uncommon", "knife block as bunker"),
    ("serving-dome-cover", "uncommon", "serving dome as cover"),
    ("pressure-cooker-lid-seal", "uncommon", "pressure cooker lid sealed"),
    ("deep-dish-pan", "uncommon", "deep dish pan as shield"),
    ("tagine-lid", "uncommon", "tagine lid as deflector"),
    ("paella-pan-shield", "uncommon", "paella pan as large shield"),
    ("restaurant-cloche", "uncommon", "restaurant cloche as dome shield"),
    ("enamel-pot-lid", "uncommon", "enamel pot lid as shield"),
    ("griddle-block", "uncommon", "flat griddle as block"),
    ("cast-iron-skillet", "uncommon", "cast iron skillet raised"),
    ("bread-proofing-basket", "uncommon", "bread proofing basket as shield"),
    ("pasta-pot-fortress", "uncommon", "pasta pot as mini fortress"),
    ("chefs-steel-apron", "rare", "steel chainmail apron as armor"),
    ("triple-layer-pot-stack", "rare", "three stacked pots as tower shield"),
    ("industrial-mixing-bowl", "rare", "industrial size mixing bowl as bunker"),
    ("walk-in-fridge-door", "rare", "walk-in fridge door slammed as wall"),
    ("full-body-oven-mitt", "rare", "full body oven mitt suit"),
    ("steel-cauldron-fortress", "rare", "steel cauldron as fortress"),
    ("marble-countertop-slab", "rare", "marble slab raised as shield"),
    ("thick-cutting-board-tower", "rare", "tower of thick cutting boards"),
    ("salamander-grill-shield", "rare", "salamander grill as shield"),
    ("commercial-baking-rack", "rare", "commercial baking rack as barrier"),
    ("giant-stockpot-dome", "rare", "giant stockpot dome shelter"),
    ("cast-iron-dutch-oven-suit", "rare", "dutch oven pieces as full suit armor"),
    ("smoking-cloche-cloud", "rare", "smoking cloche creating cover cloud"),
    ("restaurant-tray-tower", "rare", "stacked restaurant trays as tower"),
    ("industrial-pot-lid-dome", "rare", "industrial pot lid dome"),
    ("whetstone-wall", "rare", "whetstone wall barrier"),
    ("teflon-force-field", "rare", "teflon pan creating force field shimmer"),
    ("heavy-granite-pestle-block", "rare", "granite pestle as heavy block"),
    ("enchanted-chef-hat", "rare", "glowing enchanted chef hat deflecting"),
    ("inverted-wok-dome", "rare", "inverted wok as dome shelter"),
    ("titanium-wok-shield", "epic", "titanium wok shield radiating power, purple glow"),
    ("grandmas-cast-iron-fortress", "epic", "grandmother's cast iron fortress, warm epic glow"),
    ("molecular-gel-shield", "epic", "molecular gastronomy gel shield, scientific purple"),
    ("liquid-nitrogen-ice-wall", "epic", "liquid nitrogen ice wall, icy blue epic"),
    ("unbreakable-tagine", "epic", "unbreakable tagine dome, epic purple aura"),
    ("diamond-hard-mortar", "epic", "diamond mortar, crystalline epic glow"),
    ("chefs-sacred-chopping-board", "epic", "sacred chopping board carved with glowing ogham script, epic"),
    ("indestructible-colander", "epic", "indestructible colander, epic purple energy"),
    ("ancient-copper-cloche", "epic", "ancient copper cloche with engravings, epic"),
    ("eternal-pot-lid", "epic", "eternal pot lid with divine markings, purple"),
    ("skellig-stone-stockpot", "epic", "Skellig stone stockpot fortress, dark epic glow"),
    ("blessed-baking-stone", "epic", "blessed baking stone with holy light, epic"),
    ("enchanted-restaurant-dome", "epic", "enchanted restaurant dome with purple energy field"),
    ("the-ogham-cutting-board", "legendary", "ancient cutting board carved with radiant ogham script, legendary artifact, gold"),
    ("the-tir-na-nog-wok", "legendary", "ageless shining wok of Tír na nÓg, ultimate power, gold"),
    ("michelin-shield-of-honor", "legendary", "Michelin star shield of honor, legendary gold radiant"),
    ("grandmas-indestructible-apron", "legendary", "grandmother's indestructible apron legendary relic, gold"),
    ("giants-causeway-dome", "legendary", "stockpot dome of basalt columns like the Giant's Causeway, legendary gold"),
    ("the-last-line-of-pots", "legendary", "last line of pots legendary wall, gold dramatic"),
    ("nuadas-silver-pot-lid", "legendary", "Nuada's gleaming silver pot lid raised as a shield, legendary ultimate gold glow"),
]


def _build_artifact_prompt(name: str, item_type: str, rarity: str, description: str) -> str:
    colour = RARITY_COLOURS[rarity]
    action = "attack" if item_type == "attack" else "defense"
    return (
        f"Kitchen battle game {action} artifact: {description}, "
        f"{rarity} rarity, {colour}, "
        f"square icon, centered, dramatic game art style, "
        f"dark navy background, no text, no watermarks, "
        f"flat digital illustration, bold outlines, vivid colours"
    )


class Command(BaseCommand):
    help = "Generate static image assets for Chef Battles via OpenAI"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["levels", "rarity", "icons", "artifacts", "all"],
            default="all",
        )
        parser.add_argument(
            "--rarity",
            choices=["common", "uncommon", "rare", "epic", "legendary"],
            default=None,
            help="Only generate artifacts of this rarity (only with --type artifacts)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Skip files that already exist (default: True)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Re-generate even if file already exists",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "OPENAI_API_KEY", ""):
            raise CommandError("OPENAI_API_KEY is not set.")

        base = Path(settings.BASE_DIR) / "static" / "images" / "battle"
        force = options["force"]
        asset_type = options["type"]
        rarity_filter = options.get("rarity")

        if asset_type in ("levels", "all"):
            self._generate_set(base / "levels", LEVEL_PROMPTS, force)

        if asset_type in ("rarity", "all"):
            self._generate_set(base / "rarity", RARITY_PROMPTS, force)

        if asset_type in ("icons", "all"):
            self._generate_set(base / "icons", ICON_PROMPTS, force)

        if asset_type in ("artifacts", "all"):
            self._generate_artifacts(base / "artifacts", force, rarity_filter)

        self.stdout.write(self.style.SUCCESS("Done."))

    def _generate_set(self, directory: Path, prompts: dict, force: bool):
        directory.mkdir(parents=True, exist_ok=True)
        for slug, prompt in prompts.items():
            dest = directory / f"{slug}.png"
            if dest.exists() and not force:
                self.stdout.write(f"  skip  {dest.relative_to(dest.parents[3])}")
                continue
            self.stdout.write(f"  gen   {slug} ...", ending="")
            self.stdout.flush()
            try:
                data = fetch_image_bytes(prompt)
                dest.write_bytes(data)
                self.stdout.write(f" ok ({len(data)//1024}kb)")
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f" FAIL: {exc}"))

    def _generate_artifacts(self, directory: Path, force: bool, rarity_filter):
        for item_type, items in (("attack", ATTACK_ITEMS), ("defense", DEFENSE_ITEMS)):
            for slug, rarity, description in items:
                if rarity_filter and rarity != rarity_filter:
                    continue
                dest = directory / item_type / f"{slug}.png"
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and not force:
                    self.stdout.write(f"  skip  {item_type}/{slug}")
                    continue
                prompt = _build_artifact_prompt(slug.replace("-", " "), item_type, rarity, description)
                self.stdout.write(f"  gen   {item_type}/{slug} [{rarity}] ...", ending="")
                self.stdout.flush()
                try:
                    data = fetch_image_bytes(prompt)
                    dest.write_bytes(data)
                    self.stdout.write(f" ok ({len(data)//1024}kb)")
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f" FAIL: {exc}"))

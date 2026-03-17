"""Item definitions, data dictionaries, and helper functions."""

from game.settings import *


class Item:
    """An item that can be held in inventory."""
    def __init__(self, name: str, kind: str, value: int = 1,
                 damage: int = 0, defense: int = 0, heal: int = 0,
                 description: str = "", stackable: bool = False):
        self.name = name
        self.kind = kind
        self.value = value
        self.damage = damage
        self.defense = defense
        self.heal = heal
        self.description = description
        self.stackable = stackable
        self.count = 1
        # Durability (weapons and armor degrade with use)
        if kind in (ITEM_WEAPON, ITEM_ARMOR):
            self.durability = 100
            self.max_durability = 100
        else:
            self.durability = None
            self.max_durability = None


# Pre-defined items
ITEMS = {
    "Wooden Sword":    Item("Wooden Sword", ITEM_WEAPON, 10, damage=8, description="A basic wooden sword."),
    "Iron Sword":      Item("Iron Sword", ITEM_WEAPON, 50, damage=18, description="A sturdy iron blade."),
    "Steel Sword":     Item("Steel Sword", ITEM_WEAPON, 150, damage=28, description="A finely crafted steel sword."),
    "Hunting Bow":     Item("Hunting Bow", ITEM_WEAPON, 40, damage=14, description="A simple hunting bow."),
    "Staff":           Item("Staff", ITEM_WEAPON, 30, damage=10, description="A wooden staff."),
    "Leather Armor":   Item("Leather Armor", ITEM_ARMOR, 30, defense=5, description="Basic leather protection."),
    "Iron Armor":      Item("Iron Armor", ITEM_ARMOR, 100, defense=12, description="Heavy iron armor."),
    "Health Potion":   Item("Health Potion", ITEM_CONSUMABLE, 15, heal=30, description="Restores 30 HP.", stackable=True),
    "Greater Health Potion": Item("Greater Health Potion", ITEM_CONSUMABLE, 40, heal=60, description="Restores 60 HP.", stackable=True),
    "Bread":           Item("Bread", ITEM_FOOD, 3, heal=8, description="Simple bread.", stackable=True),
    "Cooked Meat":     Item("Cooked Meat", ITEM_FOOD, 8, heal=20, description="Hearty cooked meat.", stackable=True),
    "Apple":           Item("Apple", ITEM_FOOD, 2, heal=5, description="A fresh apple.", stackable=True),
    "Fish":            Item("Fish", ITEM_FOOD, 5, heal=12, description="Freshly caught fish.", stackable=True),
    "Water Flask":     Item("Water Flask", ITEM_DRINK, 2, heal=0, description="Fresh water.", stackable=True),
    "Ale":             Item("Ale", ITEM_DRINK, 4, heal=0, description="A pint of ale.", stackable=True),
    "Axe":             Item("Axe", ITEM_TOOL, 15, description="For chopping trees."),
    "Pickaxe":         Item("Pickaxe", ITEM_TOOL, 20, description="For mining stone and ore."),
    "Hoe":             Item("Hoe", ITEM_TOOL, 10, description="For tilling soil."),
    "Fishing Rod":     Item("Fishing Rod", ITEM_TOOL, 12, description="For catching fish."),
    "Hammer":          Item("Hammer", ITEM_TOOL, 15, description="For building structures."),
    "Lockpick":        Item("Lockpick", ITEM_TOOL, 8, description="For picking locks. Consumed on use.", stackable=True),
    "Seeds":           Item("Seeds", ITEM_RESOURCE, 1, description="Crop seeds for planting.", stackable=True),
    "Wood":            Item("Wood", ITEM_RESOURCE, 2, description="A bundle of wood.", stackable=True),
    "Stone":           Item("Stone", ITEM_RESOURCE, 3, description="Rough stone.", stackable=True),
    "Iron Ore":        Item("Iron Ore", ITEM_RESOURCE, 8, description="Raw iron ore.", stackable=True),
    "Herbs":           Item("Herbs", ITEM_RESOURCE, 5, description="Medicinal herbs.", stackable=True),
    "Wolf Pelt":       Item("Wolf Pelt", ITEM_RESOURCE, 12, description="A thick wolf pelt.", stackable=True),
    "Gold Nugget":     Item("Gold Nugget", ITEM_RESOURCE, 25, description="A small gold nugget.", stackable=True),
    "Ancient Relic":   Item("Ancient Relic", ITEM_QUEST, 100, description="A mysterious artifact from a forgotten age."),
    # Raw materials
    "Berries":         Item("Berries", ITEM_FOOD, 1, heal=3, description="Wild berries.", stackable=True),
    "Mushrooms":       Item("Mushrooms", ITEM_FOOD, 2, heal=5, description="Forest mushrooms.", stackable=True),
    "Wheat":           Item("Wheat", ITEM_RESOURCE, 1, description="Harvested wheat grain.", stackable=True),
    "Vegetables":      Item("Vegetables", ITEM_FOOD, 2, heal=8, description="Fresh vegetables.", stackable=True),
    "Flowers":         Item("Flowers", ITEM_RESOURCE, 2, description="Colorful flowers for alchemy.", stackable=True),
    "Clay":            Item("Clay", ITEM_RESOURCE, 1, description="Wet clay for pottery.", stackable=True),
    "Raw Meat":        Item("Raw Meat", ITEM_RESOURCE, 3, description="Uncooked meat.", stackable=True),
    # Processed materials
    "Iron Ingot":      Item("Iron Ingot", ITEM_RESOURCE, 12, description="Smelted iron bar.", stackable=True),
    "Leather":         Item("Leather", ITEM_RESOURCE, 8, description="Tanned leather.", stackable=True),
    "Planks":          Item("Planks", ITEM_RESOURCE, 3, description="Sawn wooden planks.", stackable=True),
    "Nails":           Item("Nails", ITEM_RESOURCE, 1, description="Iron nails.", stackable=True),
    "Arrowheads":      Item("Arrowheads", ITEM_RESOURCE, 1, description="Iron arrowheads.", stackable=True),
    # Crafted food
    "Vegetable Stew":  Item("Vegetable Stew", ITEM_FOOD, 5, heal=15, description="Hearty vegetable stew.", stackable=True),
    "Berry Pie":       Item("Berry Pie", ITEM_FOOD, 4, heal=12, description="Sweet berry pie.", stackable=True),
    "Mushroom Soup":   Item("Mushroom Soup", ITEM_FOOD, 4, heal=12, description="Savory mushroom soup.", stackable=True),
    # Drinks
    "Mead":            Item("Mead", ITEM_DRINK, 5, description="Honeyed mead.", stackable=True),
    "Healing Tonic":   Item("Healing Tonic", ITEM_CONSUMABLE, 10, heal=20, description="A mild healing tonic.", stackable=True),
    "Antidote":        Item("Antidote", ITEM_CONSUMABLE, 8, heal=5, description="Cures poison.", stackable=True),
    "Fire Oil":        Item("Fire Oil", ITEM_RESOURCE, 10, description="Flammable oil.", stackable=True),
    # Crafted equipment
    "Arrows":          Item("Arrows", ITEM_WEAPON, 2, damage=6, description="A bundle of arrows.", stackable=True),
    "Boots":           Item("Boots", ITEM_ARMOR, 15, defense=1, description="Leather boots."),
    "Quiver":          Item("Quiver", ITEM_RESOURCE, 8, description="Holds arrows."),
    "Wooden Shield":   Item("Wooden Shield", ITEM_ARMOR, 10, defense=2, description="A sturdy wooden shield."),
    "Pot":             Item("Pot", ITEM_TOOL, 5, description="A clay cooking pot."),
    "Smith's Tools":   Item("Smith's Tools", ITEM_TOOL, 25, description="Blacksmithing tools."),
    "Herbalism Kit":   Item("Herbalism Kit", ITEM_TOOL, 15, description="Kit for preparing herbal remedies."),
    # Gems (raw)
    "Raw Ruby":        Item("Raw Ruby", ITEM_RESOURCE, 30, description="An uncut ruby.", stackable=True),
    "Raw Sapphire":    Item("Raw Sapphire", ITEM_RESOURCE, 35, description="An uncut sapphire.", stackable=True),
    "Raw Emerald":     Item("Raw Emerald", ITEM_RESOURCE, 40, description="An uncut emerald.", stackable=True),
    "Raw Diamond":     Item("Raw Diamond", ITEM_RESOURCE, 80, description="An uncut diamond.", stackable=True),
    # Gems (cut)
    "Ruby":            Item("Ruby", ITEM_RESOURCE, 75, description="A brilliant cut ruby."),
    "Sapphire":        Item("Sapphire", ITEM_RESOURCE, 85, description="A polished blue sapphire."),
    "Emerald":         Item("Emerald", ITEM_RESOURCE, 100, description="A flawless green emerald."),
    "Diamond":         Item("Diamond", ITEM_RESOURCE, 200, description="A dazzling cut diamond."),
    # Jewelry
    "Gold Ring":       Item("Gold Ring", ITEM_ARMOR, 50, defense=0, description="A simple gold ring."),
    "Ruby Ring":       Item("Ruby Ring", ITEM_ARMOR, 120, defense=1, description="A gold ring set with a ruby. +1 STR."),
    "Sapphire Amulet": Item("Sapphire Amulet", ITEM_ARMOR, 150, defense=1, description="A sapphire pendant. +1 INT."),
    "Emerald Pendant": Item("Emerald Pendant", ITEM_ARMOR, 160, defense=1, description="An emerald necklace. +1 WIS."),
    "Diamond Crown":   Item("Diamond Crown", ITEM_ARMOR, 500, defense=2, description="A crown set with diamonds. +2 CHA."),
    "Enchanted Ring":  Item("Enchanted Ring", ITEM_ARMOR, 300, defense=2, description="A ring of magical protection."),
    # New raw materials
    "Copper Ore":      Item("Copper Ore", ITEM_RESOURCE, 4, description="Raw copper ore.", stackable=True),
    "Copper Ingot":    Item("Copper Ingot", ITEM_RESOURCE, 8, description="Smelted copper.", stackable=True),
    "Bronze Ingot":    Item("Bronze Ingot", ITEM_RESOURCE, 15, description="Bronze alloy.", stackable=True),
    "Steel Ingot":     Item("Steel Ingot", ITEM_RESOURCE, 20, description="High-quality steel.", stackable=True),
    "Gold Bar":        Item("Gold Bar", ITEM_RESOURCE, 50, description="A bar of pure gold.", stackable=True),
    "Resin":           Item("Resin", ITEM_RESOURCE, 2, description="Sticky tree resin.", stackable=True),
    "Flax":            Item("Flax", ITEM_RESOURCE, 1, description="Raw flax fiber.", stackable=True),
    "Honey":           Item("Honey", ITEM_FOOD, 3, heal=5, description="Golden honey.", stackable=True),
    "Beeswax":         Item("Beeswax", ITEM_RESOURCE, 2, description="Natural beeswax.", stackable=True),
    "Salt":            Item("Salt", ITEM_RESOURCE, 2, description="Mineral salt.", stackable=True),
    "Sand":            Item("Sand", ITEM_RESOURCE, 1, description="Fine sand for glassmaking.", stackable=True),
    "Flour":           Item("Flour", ITEM_RESOURCE, 2, description="Ground wheat flour.", stackable=True),
    "Compost":         Item("Compost", ITEM_RESOURCE, 1, description="Rich compost for farming.", stackable=True),
    # Crafted equipment
    "Bronze Shield":   Item("Bronze Shield", ITEM_ARMOR, 25, defense=3, description="A bronze shield."),
    "Chain Mail":      Item("Chain Mail", ITEM_ARMOR, 75, defense=8, description="Interlocking iron chains."),
    "Plate Armor":     Item("Plate Armor", ITEM_ARMOR, 200, defense=10, description="Full plate armor."),
    # Crafted food/drink
    "Meat Pie":        Item("Meat Pie", ITEM_FOOD, 6, heal=18, description="A hearty meat pie.", stackable=True),
    "Honey Cake":      Item("Honey Cake", ITEM_FOOD, 5, heal=10, description="Sweet honey cake.", stackable=True),
    "Salted Fish":     Item("Salted Fish", ITEM_FOOD, 4, heal=10, description="Preserved salted fish.", stackable=True),
    "Trail Rations":   Item("Trail Rations", ITEM_FOOD, 8, heal=20, description="Packed travel food.", stackable=True),
    "Feast Platter":   Item("Feast Platter", ITEM_FOOD, 25, heal=50, description="A grand feast platter!", stackable=True),
    "Wine":            Item("Wine", ITEM_DRINK, 8, description="Fine wine.", stackable=True),
    "Dwarven Stout":   Item("Dwarven Stout", ITEM_DRINK, 10, description="Strong dwarven ale.", stackable=True),
    "Elven Cordial":   Item("Elven Cordial", ITEM_DRINK, 15, heal=15, description="Refreshing elven drink.", stackable=True),
    # Alchemy
    "Poison Vial":     Item("Poison Vial", ITEM_RESOURCE, 15, description="A vial of potent poison.", stackable=True),
    "Strength Elixir": Item("Strength Elixir", ITEM_CONSUMABLE, 40, heal=10, description="Temporarily boosts strength.", stackable=True),
    "Speed Elixir":    Item("Speed Elixir", ITEM_CONSUMABLE, 40, heal=10, description="Temporarily boosts speed.", stackable=True),
    "Invisibility Oil":Item("Invisibility Oil", ITEM_CONSUMABLE, 80, description="Grants brief invisibility.", stackable=True),
    "Healing Salve":   Item("Healing Salve", ITEM_CONSUMABLE, 8, heal=12, description="A soothing healing salve.", stackable=True),
    "Smelling Salts":  Item("Smelling Salts", ITEM_CONSUMABLE, 5, heal=5, description="Revives the unconscious.", stackable=True),
    "Ink":             Item("Ink", ITEM_RESOURCE, 5, description="Ink for writing.", stackable=True),
    # Magic potions
    "Mana Potion":     Item("Mana Potion", ITEM_CONSUMABLE, 20, description="Restores 25 mana.", stackable=True),
    "Strength Potion": Item("Strength Potion", ITEM_CONSUMABLE, 35, description="Temporarily boosts strength by 4.", stackable=True),
    "Invisibility Potion": Item("Invisibility Potion", ITEM_CONSUMABLE, 70, description="Grants 15s of invisibility.", stackable=True),
    # Textiles
    "Linen":           Item("Linen", ITEM_RESOURCE, 3, description="Woven linen cloth.", stackable=True),
    "Rope":            Item("Rope", ITEM_RESOURCE, 3, description="Strong rope.", stackable=True),
    "Bandage":         Item("Bandage", ITEM_CONSUMABLE, 2, heal=8, description="Cloth bandage.", stackable=True),
    "Cloak":           Item("Cloak", ITEM_ARMOR, 10, defense=1, description="A warm traveling cloak."),
    "Robe":            Item("Robe", ITEM_ARMOR, 15, defense=1, description="A mage's robe."),
    "Tent":            Item("Tent", ITEM_TOOL, 20, description="A portable tent for camping."),
    # Woodcraft
    "Torch":           Item("Torch", ITEM_TOOL, 1, description="A lit torch.", stackable=True),
    "Barrel":          Item("Barrel", ITEM_RESOURCE, 8, description="A wooden barrel."),
    "Crate":           Item("Crate", ITEM_RESOURCE, 5, description="A wooden crate."),
    "Cart":            Item("Cart", ITEM_TOOL, 50, description="A wheeled cart for hauling goods."),
    # Pottery & glass
    "Vase":            Item("Vase", ITEM_RESOURCE, 6, description="A decorated clay vase."),
    "Glass Pane":      Item("Glass Pane", ITEM_RESOURCE, 5, description="A pane of clear glass.", stackable=True),
    "Bottle":          Item("Bottle", ITEM_RESOURCE, 3, description="A glass bottle.", stackable=True),
    # Chandlery
    "Candle":          Item("Candle", ITEM_TOOL, 1, description="A beeswax candle.", stackable=True),
    "Sealing Wax":     Item("Sealing Wax", ITEM_RESOURCE, 3, description="Red sealing wax.", stackable=True),
    # Misc equipment
    "Lantern":         Item("Lantern", ITEM_TOOL, 10, description="An iron lantern."),
    "Iron Chain":      Item("Iron Chain", ITEM_RESOURCE, 5, description="A length of iron chain.", stackable=True),
    "Iron Horseshoes": Item("Iron Horseshoes", ITEM_RESOURCE, 4, description="Horseshoes.", stackable=True),
    "Belt":            Item("Belt", ITEM_ARMOR, 3, defense=0, description="A leather belt."),
    "Leather Gloves":  Item("Leather Gloves", ITEM_ARMOR, 5, defense=1, description="Tough leather gloves."),
    "Satchel":         Item("Satchel", ITEM_TOOL, 8, description="A leather satchel for carrying goods."),
    "Saddle":          Item("Saddle", ITEM_TOOL, 25, description="A riding saddle."),
    "Waterskin":       Item("Waterskin", ITEM_DRINK, 3, description="A leather waterskin.", stackable=True),
    # Enchanting
    "Scroll of Healing": Item("Scroll of Healing", ITEM_CONSUMABLE, 20, heal=25, description="A magical healing scroll."),
    "Scroll of Fire":    Item("Scroll of Fire", ITEM_CONSUMABLE, 25, damage=20, description="Unleashes a burst of flame."),
    "Wand of Sparks":    Item("Wand of Sparks", ITEM_WEAPON, 100, damage=15, description="A wand crackling with energy."),
    "Jeweler's Tools":   Item("Jeweler's Tools", ITEM_TOOL, 30, description="Precision tools for gem cutting."),
    # Animal products
    "Milk":            Item("Milk", ITEM_DRINK, 2, description="Fresh cow's milk.", stackable=True),
    "Cheese":          Item("Cheese", ITEM_FOOD, 4, heal=8, description="Aged cheese.", stackable=True),
    "Butter":          Item("Butter", ITEM_FOOD, 3, heal=3, description="Creamy butter.", stackable=True),
    "Eggs":            Item("Eggs", ITEM_FOOD, 2, heal=4, description="Fresh eggs.", stackable=True),
    "Bacon":           Item("Bacon", ITEM_FOOD, 5, heal=12, description="Smoked bacon.", stackable=True),
    "Wool":            Item("Wool", ITEM_RESOURCE, 3, description="Sheep's wool.", stackable=True),
    "Feathers":        Item("Feathers", ITEM_RESOURCE, 1, description="Bird feathers.", stackable=True),
    # Books and knowledge
    "Book":            Item("Book", ITEM_RESOURCE, 10, description="A book of knowledge."),
    "Spellbook":       Item("Spellbook", ITEM_RESOURCE, 50, description="A tome of arcane secrets."),
    "Skill Manual":    Item("Skill Manual", ITEM_RESOURCE, 25, description="A training manual. Read to learn."),
    "Map":             Item("Map", ITEM_RESOURCE, 8, description="A map of the region."),
    "Letter":          Item("Letter", ITEM_QUEST, 1, description="A sealed letter."),
    "Journal":         Item("Journal", ITEM_RESOURCE, 5, description="A personal journal."),
    # Trapping
    "Snare Trap":      Item("Snare Trap", ITEM_TOOL, 5, description="A simple animal snare.", stackable=True),
    "Cage":            Item("Cage", ITEM_TOOL, 15, description="A cage for capturing live animals."),
    "Net":             Item("Net", ITEM_TOOL, 8, description="A net for catching animals or fish."),
    # Farming tools
    "Bucket":          Item("Bucket", ITEM_TOOL, 3, description="A wooden bucket for milking."),
    "Churn":           Item("Churn", ITEM_TOOL, 8, description="A butter churn."),
    "Trough":          Item("Trough", ITEM_TOOL, 5, description="An animal feeding trough."),
    # Cooked specialties
    "Omelette":        Item("Omelette", ITEM_FOOD, 4, heal=10, description="A fluffy omelette.", stackable=True),
    "Cheese Wheel":    Item("Cheese Wheel", ITEM_FOOD, 12, heal=20, description="A whole wheel of cheese."),
    "Smoked Fish":     Item("Smoked Fish", ITEM_FOOD, 6, heal=14, description="Smoked and preserved fish.", stackable=True),
    "Sausage":         Item("Sausage", ITEM_FOOD, 5, heal=12, description="A hearty sausage.", stackable=True),
    # === NEW SKILL TOOLS ===
    "Thieves' Tools":  Item("Thieves' Tools", ITEM_TOOL, 20, description="Lockpicks and trap-disarming tools."),
    "Disguise Kit":    Item("Disguise Kit", ITEM_TOOL, 15, description="Wigs, makeup, and costumes for disguise."),
    "Cartographer's Kit": Item("Cartographer's Kit", ITEM_TOOL, 20, description="Compass, ruler, and parchment for map-making."),
    "Navigator's Tools": Item("Navigator's Tools", ITEM_TOOL, 18, description="Compass and sextant for navigation."),
    "Climbing Kit":    Item("Climbing Kit", ITEM_TOOL, 15, description="Pitons, rope, and harness for climbing."),
    "Glassblower's Tools": Item("Glassblower's Tools", ITEM_TOOL, 25, description="Blowpipe and shaping tools."),
    "Dye Kit":         Item("Dye Kit", ITEM_TOOL, 10, description="Mordants and pigments for dyeing cloth."),
    "Siege Tools":     Item("Siege Tools", ITEM_TOOL, 40, description="Heavy tools for siege engineering."),
    "Shipwright's Tools": Item("Shipwright's Tools", ITEM_TOOL, 35, description="Caulking, saws, and rigging tools."),
    "Enchanter's Focus": Item("Enchanter's Focus", ITEM_TOOL, 50, description="A crystal orb for channeling enchantments."),
    "Musical Instrument": Item("Musical Instrument", ITEM_TOOL, 15, description="A lute for performing."),
    "Healer's Kit":    Item("Healer's Kit", ITEM_TOOL, 15, description="Bandages, splints, and salves for treating wounds."),
    "Divination Crystal": Item("Divination Crystal", ITEM_TOOL, 30, description="A crystal sphere for scrying the future."),
    "Ward Stones":     Item("Ward Stones", ITEM_TOOL, 25, description="Inscribed stones for warding magic.", stackable=True),
    "Training Dummy":  Item("Training Dummy", ITEM_TOOL, 10, description="A wooden dummy for combat practice."),
    "Grappling Hook":  Item("Grappling Hook", ITEM_TOOL, 12, description="A hook and rope for scaling walls."),
    "Iron Shield":     Item("Iron Shield", ITEM_ARMOR, 35, defense=4, description="A heavy iron shield."),
    # === NEW CRAFTED PRODUCTS ===
    "Pottery Jar":     Item("Pottery Jar", ITEM_RESOURCE, 4, description="A sturdy clay jar.", stackable=True),
    "Stained Glass":   Item("Stained Glass", ITEM_RESOURCE, 15, description="Beautiful stained glass panel."),
    "Dyed Cloth":      Item("Dyed Cloth", ITEM_RESOURCE, 8, description="Colorfully dyed fabric.", stackable=True),
    "Enchanted Sword": Item("Enchanted Sword", ITEM_WEAPON, 250, damage=35, description="A blade humming with arcane power."),
    "Enchanted Staff": Item("Enchanted Staff", ITEM_WEAPON, 200, damage=25, description="A staff crackling with energy."),
    "Regional Map":    Item("Regional Map", ITEM_RESOURCE, 12, description="A detailed map of the surrounding region."),
    "Battering Ram":   Item("Battering Ram", ITEM_TOOL, 60, description="A heavy log for breaching gates."),
    "Boat Hull":       Item("Boat Hull", ITEM_RESOURCE, 80, description="The hull of a small boat."),
    "Trap":            Item("Trap", ITEM_TOOL, 8, description="A spring-loaded trap.", stackable=True),
    "Caltrops":        Item("Caltrops", ITEM_TOOL, 5, description="Scattered metal spikes to slow enemies.", stackable=True),
    "Holy Water":      Item("Holy Water", ITEM_CONSUMABLE, 15, damage=10, description="Blessed water. Burns undead.", stackable=True),
    "Scroll of Ward":  Item("Scroll of Ward", ITEM_CONSUMABLE, 20, description="Creates a protective barrier.", stackable=True),
    "Herbal Poultice": Item("Herbal Poultice", ITEM_CONSUMABLE, 6, heal=15, description="A medicinal herb compress.", stackable=True),
    "Tanned Hide":     Item("Tanned Hide", ITEM_RESOURCE, 10, description="Properly tanned animal hide.", stackable=True),
    # === FINANCIAL ITEMS ===
    "Ledger":          Item("Ledger", ITEM_TOOL, 12, description="An accounting ledger for tracking finances."),
    "Abacus":          Item("Abacus", ITEM_TOOL, 8, description="A counting tool for calculations."),
    "Strongbox":       Item("Strongbox", ITEM_TOOL, 20, description="A locked iron box for storing valuables."),
    "Debt Contract":   Item("Debt Contract", ITEM_QUEST, 1, description="A signed loan agreement.", stackable=True),
    "Bond Certificate":Item("Bond Certificate", ITEM_QUEST, 5, description="An investment bond certificate."),
    "Insurance Writ":  Item("Insurance Writ", ITEM_QUEST, 3, description="An insurance policy document."),
    "Gold Coins":      Item("Gold Coins", ITEM_RESOURCE, 1, description="A stack of gold coins.", stackable=True),
    "Silver Coins":    Item("Silver Coins", ITEM_RESOURCE, 1, description="A stack of silver coins.", stackable=True),
    "Wax Seal":        Item("Wax Seal", ITEM_RESOURCE, 2, description="Official wax seal for documents.", stackable=True),
    # === WOOL TEXTILES ===
    "Wool Cloth":      Item("Wool Cloth", ITEM_RESOURCE, 4, description="Woven wool fabric.", stackable=True),
    # === FOREIGN TRADE GOODS ===
    "Silk":            Item("Silk", ITEM_RESOURCE, 15, description="Fine silk from the Zarath Empire.", stackable=True),
    "Spices":          Item("Spices", ITEM_RESOURCE, 10, description="Exotic spices from the east.", stackable=True),
    "Exotic Fruits":   Item("Exotic Fruits", ITEM_FOOD, 8, heal=10, description="Tropical fruits from the Southern Isles.", stackable=True),
    "Pearls":          Item("Pearls", ITEM_RESOURCE, 20, description="Ocean pearls of great beauty.", stackable=True),
    "Rum":             Item("Rum", ITEM_DRINK, 6, description="Strong sugarcane spirit.", stackable=True),
    "Arcane Tomes":    Item("Arcane Tomes", ITEM_RESOURCE, 25, description="Books of foreign magical theory."),
    "Navigation Charts": Item("Navigation Charts", ITEM_RESOURCE, 12, description="Sea charts for distant waters."),
    "Jade":            Item("Jade", ITEM_RESOURCE, 18, description="Green jade stone from the north.", stackable=True),
    "Ivory":           Item("Ivory", ITEM_RESOURCE, 22, description="Carved ivory tusks.", stackable=True),
    "Incense":         Item("Incense", ITEM_RESOURCE, 5, description="Fragrant temple incense.", stackable=True),
    # === ELVEN SPECIALTY GOODS ===
    "Elven Wine":      Item("Elven Wine", ITEM_DRINK, 15, heal=5, description="A vintage of exquisite elven wine.", stackable=True),
    "Mooncloth":       Item("Mooncloth", ITEM_RESOURCE, 20, description="Silvery fabric woven under moonlight.", stackable=True),
    "Lembas Bread":    Item("Lembas Bread", ITEM_FOOD, 12, heal=25, description="Elven waybread that sustains for days.", stackable=True),
    "Enchanted Arrows":Item("Enchanted Arrows", ITEM_WEAPON, 18, damage=10, description="Arrows imbued with elven magic.", stackable=True),
    # === DWARVEN SPECIALTY GOODS ===
    "Dwarven Steel":   Item("Dwarven Steel", ITEM_RESOURCE, 25, description="Steel of legendary dwarven quality.", stackable=True),
    "Masterwork Weapon": Item("Masterwork Weapon", ITEM_WEAPON, 30, damage=22, description="A weapon of dwarven mastercraft."),
    "Masterwork Armor": Item("Masterwork Armor", ITEM_ARMOR, 35, defense=12, description="Armor forged by a dwarven master."),
    "Gem Jewelry":     Item("Gem Jewelry", ITEM_RESOURCE, 40, description="Exquisite gem-studded jewelry.", stackable=True),
    # === ORCISH SPECIALTY GOODS ===
    "War Paint":       Item("War Paint", ITEM_CONSUMABLE, 5, description="Tribal war paint that inspires ferocity.", stackable=True),
    "Beast Hide":      Item("Beast Hide", ITEM_RESOURCE, 8, description="A thick hide from a great beast.", stackable=True),
    "Bone Weapon":     Item("Bone Weapon", ITEM_WEAPON, 6, damage=7, description="A crude weapon carved from bone."),
    "Bone Tools":      Item("Bone Tools", ITEM_TOOL, 4, description="Simple tools fashioned from bone."),
    "War Drums":       Item("War Drums", ITEM_TOOL, 10, description="Drums that thunder with orcish fury."),
    "Trophy Skulls":   Item("Trophy Skulls", ITEM_RESOURCE, 3, description="Grim trophies of battle.", stackable=True),
    # === GOBLIN SPECIALTY GOODS ===
    "Goblin Fire":     Item("Goblin Fire", ITEM_CONSUMABLE, 10, damage=15, description="A volatile goblin incendiary.", stackable=True),
    "Crude Trap":      Item("Crude Trap", ITEM_TOOL, 4, description="A crude but effective mechanical trap.", stackable=True),
    "Mushroom Brew":   Item("Mushroom Brew", ITEM_DRINK, 3, heal=2, description="A dubious fungal concoction.", stackable=True),
    "Sneaky Lockpicks":Item("Sneaky Lockpicks", ITEM_TOOL, 12, description="Goblin-crafted picks that find every tumbler."),
    "Scrap Metal":     Item("Scrap Metal", ITEM_RESOURCE, 2, description="Salvaged bits of metal.", stackable=True),
    # === UNDEAD SPECIALTY GOODS ===
    "Cursed Artifact":  Item("Cursed Artifact", ITEM_RESOURCE, 30, description="An artifact radiating dark energy."),
    "Soul Gem":        Item("Soul Gem", ITEM_RESOURCE, 35, description="A gem pulsing with trapped souls.", stackable=True),
    "Dark Tome":       Item("Dark Tome", ITEM_RESOURCE, 20, description="A tome of forbidden necromantic lore."),
    "Phylactery Shard":Item("Phylactery Shard", ITEM_RESOURCE, 50, description="A fragment of a lich's phylactery."),
    "Death Shroud":    Item("Death Shroud", ITEM_ARMOR, 25, defense=3, description="A shroud that chills the living."),
    # === HUMAN SPECIALTY GOODS ===
    "Fine Ale":        Item("Fine Ale", ITEM_DRINK, 8, heal=2, description="A premium brew of exceptional quality.", stackable=True),
    "Embroidered Cloth": Item("Embroidered Cloth", ITEM_RESOURCE, 12, description="Beautifully embroidered fabric.", stackable=True),
}

# Food items that satisfy hunger
FOOD_ITEMS = {"Bread", "Cooked Meat", "Apple", "Fish", "Berries", "Mushrooms",
              "Vegetables", "Vegetable Stew", "Berry Pie", "Mushroom Soup",
              "Meat Pie", "Honey Cake", "Salted Fish", "Trail Rations", "Feast Platter", "Honey",
              "Cheese", "Butter", "Eggs", "Bacon", "Omelette", "Cheese Wheel",
              "Smoked Fish", "Sausage", "Exotic Fruits", "Lembas Bread"}
DRINK_ITEMS = {"Water Flask", "Ale", "Mead", "Wine", "Dwarven Stout", "Elven Cordial", "Waterskin", "Milk", "Rum",
               "Elven Wine", "Fine Ale", "Mushroom Brew"}

# Profession starter inventories
PROFESSION_STARTER = {
    "Farmer":     [("Hoe", 1), ("Seeds", 5), ("Bread", 8), ("Water Flask", 6), ("Apple", 4)],
    "Blacksmith": [("Hammer", 1), ("Smith's Tools", 1), ("Iron Ore", 3), ("Bread", 6), ("Water Flask", 6)],
    "Merchant":   [("Bread", 8), ("Water Flask", 6), ("Health Potion", 2), ("Apple", 5), ("Cooked Meat", 3)],
    "Guard":      [("Iron Sword", 1), ("Bread", 6), ("Water Flask", 6), ("Cooked Meat", 3)],
    "Ranger":     [("Hunting Bow", 1), ("Axe", 1), ("Cooked Meat", 5), ("Water Flask", 6), ("Bread", 4)],
    "Miner":      [("Pickaxe", 1), ("Bread", 6), ("Water Flask", 6), ("Apple", 3)],
    "Healer":     [("Staff", 1), ("Herbalism Kit", 1), ("Herbs", 5), ("Water Flask", 6), ("Bread", 5)],
    "Alchemist":  [("Herbalism Kit", 1), ("Herbs", 5), ("Mushrooms", 3), ("Flowers", 3), ("Bread", 5), ("Water Flask", 6)],
    "Scholar":    [("Staff", 1), ("Bread", 6), ("Water Flask", 6), ("Apple", 3)],
    "Philosopher":[("Bread", 5), ("Water Flask", 8), ("Apple", 3)],
    "Bard":       [("Bread", 5), ("Water Flask", 8), ("Ale", 3), ("Apple", 3)],
    "Innkeeper":  [("Bread", 10), ("Ale", 5), ("Water Flask", 8), ("Cooked Meat", 5), ("Apple", 5)],
    "Fisher":     [("Fishing Rod", 1), ("Bread", 5), ("Water Flask", 6), ("Fish", 4)],
    # D&D classes default
    "Fighter":    [("Iron Sword", 1), ("Bread", 6), ("Water Flask", 6), ("Cooked Meat", 3)],
    "Wizard":     [("Staff", 1), ("Bread", 5), ("Water Flask", 5), ("Apple", 3)],
    "Cleric":     [("Staff", 1), ("Bread", 6), ("Water Flask", 6), ("Herbs", 3)],
    "Rogue":      [("Thieves' Tools", 1), ("Lockpick", 3), ("Bread", 5), ("Water Flask", 5), ("Apple", 3)],
    "Paladin":    [("Iron Sword", 1), ("Bread", 6), ("Water Flask", 6), ("Cooked Meat", 2)],
    "Barbarian":  [("Axe", 1), ("Cooked Meat", 5), ("Water Flask", 6), ("Bread", 4)],
    "Druid":      [("Staff", 1), ("Herbs", 4), ("Bread", 5), ("Water Flask", 6), ("Apple", 4)],
    "Monk":       [("Bread", 5), ("Water Flask", 6), ("Apple", 4)],
    "Sorcerer":   [("Staff", 1), ("Bread", 5), ("Water Flask", 5), ("Apple", 3)],
    "Warlock":    [("Staff", 1), ("Bread", 5), ("Water Flask", 5), ("Herbs", 2)],
    # Financial professions
    "Banker":     [("Ledger", 1), ("Abacus", 1), ("Bread", 5), ("Water Flask", 8)],
    "Tax Collector": [("Ledger", 1), ("Iron Sword", 1), ("Bread", 5), ("Water Flask", 8)],
    "Moneylender": [("Ledger", 1), ("Strongbox", 1), ("Bread", 5), ("Water Flask", 8)],
}


def make_item(name: str) -> Item:
    """Create a copy of a predefined item."""
    template = ITEMS.get(name)
    if template is None:
        return Item(name, ITEM_RESOURCE, 1)
    i = Item(template.name, template.kind, template.value,
             template.damage, template.defense, template.heal,
             template.description, template.stackable)
    return i

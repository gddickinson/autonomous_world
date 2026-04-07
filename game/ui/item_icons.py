"""Procedural item icon generators for the inventory panel.

Each icon is drawn onto a small pygame surface (16x16 or similar) using
simple geometric shapes.  Icons are cached by item name for reuse.
"""

import pygame

# Icon cache: item_name_lower -> pygame.Surface
_icon_cache: dict = {}
_icon_size = 14  # px per icon


def get_item_icon(item_name: str, item_kind: str = "") -> pygame.Surface:
    """Get or create a procedural icon for the given item.

    Args:
        item_name: Display name of the item (e.g. "Iron Sword")
        item_kind: Item kind constant (weapon, armor, consumable, food, etc.)

    Returns:
        A small pygame.Surface with the icon drawn on it.
    """
    key = item_name.lower()
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached

    s = _icon_size
    surf = pygame.Surface((s, s), pygame.SRCALPHA)

    name_l = key
    kind_l = item_kind.lower() if item_kind else ""

    # Match specific item types by name keywords
    if _match(name_l, ("sword", "blade", "scimitar", "rapier", "dagger",
                        "knife", "cutlass")):
        _draw_sword_icon(surf, s)
    elif _match(name_l, ("axe", "hatchet")):
        _draw_axe_icon(surf, s)
    elif _match(name_l, ("bow", "longbow", "crossbow")):
        _draw_bow_icon(surf, s)
    elif _match(name_l, ("staff", "wand", "rod")):
        _draw_staff_icon(surf, s)
    elif _match(name_l, ("shield", "buckler")):
        _draw_shield_icon(surf, s)
    elif _match(name_l, ("helm", "helmet", "cap", "hat", "hood")):
        _draw_helm_icon(surf, s)
    elif _match(name_l, ("armor", "mail", "plate", "chain", "leather armor",
                          "breastplate", "tunic")):
        _draw_armor_icon(surf, s)
    elif _match(name_l, ("potion", "elixir", "draught", "vial", "flask")):
        _draw_potion_icon(surf, s)
    elif _match(name_l, ("bread", "loaf", "bun", "roll")):
        _draw_bread_icon(surf, s)
    elif _match(name_l, ("meat", "steak", "jerky", "venison", "pork",
                          "chicken leg", "fish")):
        _draw_meat_icon(surf, s)
    elif _match(name_l, ("apple", "berry", "fruit")):
        _draw_fruit_icon(surf, s)
    elif _match(name_l, ("gold", "coin", "coins")):
        _draw_coin_icon(surf, s)
    elif _match(name_l, ("ring",)):
        _draw_ring_icon(surf, s)
    elif _match(name_l, ("amulet", "necklace", "pendant")):
        _draw_amulet_icon(surf, s)
    elif _match(name_l, ("scroll", "tome", "book", "grimoire")):
        _draw_scroll_icon(surf, s)
    elif _match(name_l, ("gem", "ruby", "emerald", "sapphire", "diamond",
                          "crystal")):
        _draw_gem_icon(surf, s)
    elif _match(name_l, ("ore", "iron", "copper", "tin", "coal")):
        _draw_ore_icon(surf, s)
    elif _match(name_l, ("wood", "log", "plank", "lumber")):
        _draw_wood_icon(surf, s)
    elif _match(name_l, ("herb", "leaf", "moss", "root")):
        _draw_herb_icon(surf, s)
    elif _match(name_l, ("key",)):
        _draw_key_icon(surf, s)
    elif _match(name_l, ("torch", "lantern")):
        _draw_torch_icon(surf, s)
    elif _match(name_l, ("rope",)):
        _draw_rope_icon(surf, s)
    elif _match(name_l, ("hammer", "mace", "club")):
        _draw_hammer_icon(surf, s)
    elif _match(name_l, ("spear", "javelin", "pike", "lance")):
        _draw_spear_icon(surf, s)
    elif _match(name_l, ("water", "ale", "wine", "mead", "beer")):
        _draw_drink_icon(surf, s)
    elif _match(name_l, ("pick", "pickaxe")):
        _draw_pickaxe_icon(surf, s)
    # Fall back to kind-based icons
    elif kind_l == "weapon":
        _draw_sword_icon(surf, s)
    elif kind_l == "armor":
        _draw_armor_icon(surf, s)
    elif kind_l == "consumable":
        _draw_potion_icon(surf, s)
    elif kind_l == "food":
        _draw_bread_icon(surf, s)
    elif kind_l == "drink":
        _draw_drink_icon(surf, s)
    elif kind_l == "resource":
        _draw_ore_icon(surf, s)
    elif kind_l == "tool":
        _draw_hammer_icon(surf, s)
    elif kind_l == "quest":
        _draw_scroll_icon(surf, s)
    else:
        _draw_generic_icon(surf, s)

    _icon_cache[key] = surf
    return surf


def _match(name: str, keywords: tuple) -> bool:
    """Check if any keyword appears in the item name."""
    return any(kw in name for kw in keywords)


# ── Icon drawing functions ────────────────────────────────────────────

def _draw_sword_icon(surf, s):
    """Blade line + crossguard + handle."""
    cx = s // 2
    # Blade (silver line from top to 2/3 down)
    pygame.draw.line(surf, (200, 200, 210), (cx, 1), (cx, s * 2 // 3), 2)
    # Tip
    pygame.draw.line(surf, (220, 220, 230), (cx, 0), (cx, 1), 1)
    # Crossguard (horizontal bar)
    gy = s * 2 // 3
    pygame.draw.line(surf, (160, 140, 60), (cx - 3, gy), (cx + 3, gy), 2)
    # Handle
    pygame.draw.line(surf, (100, 70, 40), (cx, gy + 1), (cx, s - 2), 2)
    # Pommel
    pygame.draw.circle(surf, (180, 160, 60), (cx, s - 1), 1)


def _draw_axe_icon(surf, s):
    cx = s // 2
    # Handle
    pygame.draw.line(surf, (100, 70, 40), (cx, 2), (cx, s - 2), 2)
    # Axe head (triangle on right side)
    pts = [(cx, 2), (cx + 4, 4), (cx + 4, 8), (cx, 6)]
    pygame.draw.polygon(surf, (180, 180, 190), pts)
    pygame.draw.polygon(surf, (140, 140, 150), pts, 1)


def _draw_bow_icon(surf, s):
    cx = s // 2
    # Bow arc
    pygame.draw.arc(surf, (130, 90, 50),
                    (cx - 4, 1, 8, s - 2), 1.0, 5.3, 2)
    # String
    pygame.draw.line(surf, (200, 200, 180), (cx + 2, 2), (cx + 2, s - 2), 1)


def _draw_staff_icon(surf, s):
    cx = s // 2
    # Shaft
    pygame.draw.line(surf, (110, 80, 50), (cx, 3), (cx, s - 1), 2)
    # Orb at top
    pygame.draw.circle(surf, (120, 160, 220), (cx, 3), 2)
    pygame.draw.circle(surf, (180, 210, 255), (cx, 2), 1)


def _draw_shield_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Shield body (oval)
    pygame.draw.ellipse(surf, (100, 110, 140), (cx - 4, cy - 5, 8, 10))
    pygame.draw.ellipse(surf, (70, 80, 110), (cx - 4, cy - 5, 8, 10), 1)
    # Boss (center dot)
    pygame.draw.circle(surf, (180, 170, 100), (cx, cy), 2)
    pygame.draw.circle(surf, (140, 130, 70), (cx, cy), 2, 1)


def _draw_helm_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Dome
    pygame.draw.arc(surf, (160, 160, 170),
                    (cx - 4, cy - 4, 8, 6), 0, 3.15, 2)
    # Face opening
    pygame.draw.rect(surf, (40, 40, 50), (cx - 2, cy, 4, 4))
    # Rim
    pygame.draw.line(surf, (130, 130, 140), (cx - 4, cy + 2), (cx + 4, cy + 2), 1)


def _draw_armor_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Torso outline
    pts = [(cx - 4, cy - 4), (cx + 4, cy - 4),
           (cx + 3, cy + 4), (cx - 3, cy + 4)]
    pygame.draw.polygon(surf, (140, 140, 150), pts)
    pygame.draw.polygon(surf, (100, 100, 110), pts, 1)
    # Shoulder pads
    pygame.draw.line(surf, (120, 120, 130),
                     (cx - 5, cy - 3), (cx - 3, cy - 5), 2)
    pygame.draw.line(surf, (120, 120, 130),
                     (cx + 5, cy - 3), (cx + 3, cy - 5), 2)


def _draw_potion_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Bottle body (round)
    pygame.draw.ellipse(surf, (180, 60, 60), (cx - 3, cy - 1, 6, 7))
    # Neck (thin)
    pygame.draw.rect(surf, (180, 180, 200), (cx - 1, cy - 4, 2, 4))
    # Cork
    pygame.draw.rect(surf, (140, 110, 70), (cx - 1, cy - 5, 2, 2))
    # Liquid highlight
    pygame.draw.circle(surf, (220, 100, 100), (cx - 1, cy + 1), 1)


def _draw_bread_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Oval brown shape
    pygame.draw.ellipse(surf, (180, 140, 70), (cx - 5, cy - 2, 10, 6))
    # Score lines on top
    pygame.draw.line(surf, (150, 110, 50), (cx - 2, cy - 1), (cx + 2, cy - 1))
    # Highlight
    pygame.draw.ellipse(surf, (200, 165, 90), (cx - 3, cy - 2, 6, 3))


def _draw_meat_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Meat body
    pygame.draw.ellipse(surf, (160, 70, 50), (cx - 4, cy - 2, 8, 6))
    # Bone
    pygame.draw.line(surf, (220, 210, 190), (cx + 3, cy), (cx + 6, cy - 2), 2)
    pygame.draw.circle(surf, (220, 210, 190), (cx + 6, cy - 2), 1)


def _draw_fruit_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Apple shape
    pygame.draw.circle(surf, (200, 50, 40), (cx, cy + 1), 4)
    # Stem
    pygame.draw.line(surf, (80, 60, 30), (cx, cy - 3), (cx, cy - 5), 1)
    # Leaf
    pygame.draw.line(surf, (60, 140, 50), (cx, cy - 4), (cx + 2, cy - 5), 1)


def _draw_coin_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Stack of coins (3 overlapping circles)
    for i in range(3):
        y_off = 2 - i
        pygame.draw.circle(surf, (200, 180, 60), (cx, cy + y_off), 4)
        pygame.draw.circle(surf, (160, 140, 40), (cx, cy + y_off), 4, 1)
    # $ mark on top coin
    pygame.draw.line(surf, (140, 120, 30), (cx, cy - 2), (cx, cy + 1), 1)


def _draw_ring_icon(surf, s):
    cx, cy = s // 2, s // 2
    pygame.draw.circle(surf, (200, 180, 60), (cx, cy), 4, 2)
    # Gem on top
    pygame.draw.circle(surf, (100, 200, 220), (cx, cy - 3), 2)


def _draw_amulet_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Chain
    pygame.draw.arc(surf, (180, 170, 100),
                    (cx - 4, cy - 6, 8, 6), 0, 3.15, 1)
    # Pendant
    pts = [(cx, cy + 4), (cx - 3, cy - 1), (cx + 3, cy - 1)]
    pygame.draw.polygon(surf, (200, 180, 60), pts)
    pygame.draw.polygon(surf, (160, 140, 40), pts, 1)


def _draw_scroll_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Scroll body
    pygame.draw.rect(surf, (210, 195, 160), (cx - 3, cy - 4, 6, 8))
    # Rolled ends
    pygame.draw.ellipse(surf, (190, 175, 140), (cx - 4, cy - 5, 8, 3))
    pygame.draw.ellipse(surf, (190, 175, 140), (cx - 4, cy + 3, 8, 3))
    # Text lines
    for y in range(cy - 2, cy + 3, 2):
        pygame.draw.line(surf, (100, 80, 60), (cx - 2, y), (cx + 2, y))


def _draw_gem_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Diamond shape
    pts = [(cx, cy - 4), (cx + 3, cy), (cx, cy + 4), (cx - 3, cy)]
    pygame.draw.polygon(surf, (100, 180, 220), pts)
    pygame.draw.polygon(surf, (60, 130, 180), pts, 1)
    # Inner highlight
    pts2 = [(cx, cy - 2), (cx + 1, cy), (cx, cy + 1), (cx - 1, cy)]
    pygame.draw.polygon(surf, (160, 220, 255), pts2)


def _draw_ore_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Rock chunk
    pts = [(cx - 4, cy + 3), (cx - 2, cy - 3), (cx + 1, cy - 4),
           (cx + 4, cy - 1), (cx + 3, cy + 3)]
    pygame.draw.polygon(surf, (130, 120, 110), pts)
    pygame.draw.polygon(surf, (90, 80, 70), pts, 1)
    # Shiny ore specks
    pygame.draw.circle(surf, (200, 170, 80), (cx - 1, cy), 1)
    pygame.draw.circle(surf, (200, 170, 80), (cx + 2, cy - 1), 1)


def _draw_wood_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Log shape (horizontal oval)
    pygame.draw.ellipse(surf, (120, 80, 40), (cx - 5, cy - 2, 10, 5))
    # End grain circle
    pygame.draw.circle(surf, (100, 70, 35), (cx + 4, cy), 2)
    pygame.draw.circle(surf, (140, 100, 50), (cx + 4, cy), 1)


def _draw_herb_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Stem
    pygame.draw.line(surf, (60, 100, 40), (cx, cy + 4), (cx, cy - 2), 1)
    # Leaves
    pygame.draw.ellipse(surf, (70, 160, 50), (cx - 3, cy - 4, 3, 4))
    pygame.draw.ellipse(surf, (70, 160, 50), (cx, cy - 3, 3, 4))
    pygame.draw.ellipse(surf, (80, 140, 55), (cx - 1, cy - 5, 2, 3))


def _draw_key_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Key ring (top)
    pygame.draw.circle(surf, (200, 180, 60), (cx, cy - 3), 3, 1)
    # Shaft
    pygame.draw.line(surf, (200, 180, 60), (cx, cy), (cx, cy + 4), 2)
    # Teeth
    pygame.draw.line(surf, (200, 180, 60), (cx, cy + 3), (cx + 2, cy + 3), 1)
    pygame.draw.line(surf, (200, 180, 60), (cx, cy + 4), (cx + 2, cy + 4), 1)


def _draw_torch_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Handle
    pygame.draw.line(surf, (100, 70, 40), (cx, cy), (cx, cy + 5), 2)
    # Flame
    pts = [(cx, cy - 4), (cx - 2, cy), (cx + 2, cy)]
    pygame.draw.polygon(surf, (255, 180, 40), pts)
    pygame.draw.polygon(surf, (255, 220, 80),
                        [(cx, cy - 2), (cx - 1, cy), (cx + 1, cy)])


def _draw_rope_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Coiled rope
    pygame.draw.circle(surf, (160, 130, 80), (cx, cy), 4, 2)
    pygame.draw.arc(surf, (140, 110, 60), (cx - 3, cy - 3, 6, 6), 0, 2.5, 1)


def _draw_hammer_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Handle
    pygame.draw.line(surf, (100, 70, 40), (cx, cy), (cx, cy + 5), 2)
    # Head
    pygame.draw.rect(surf, (160, 160, 170), (cx - 3, cy - 3, 6, 4))
    pygame.draw.rect(surf, (120, 120, 130), (cx - 3, cy - 3, 6, 4), 1)


def _draw_spear_icon(surf, s):
    cx = s // 2
    # Shaft
    pygame.draw.line(surf, (120, 90, 50), (cx, 3), (cx, s - 1), 1)
    # Spearhead
    pts = [(cx, 0), (cx - 2, 4), (cx + 2, 4)]
    pygame.draw.polygon(surf, (180, 180, 200), pts)


def _draw_drink_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Mug body
    pygame.draw.rect(surf, (160, 140, 100), (cx - 3, cy - 2, 6, 7))
    # Handle
    pygame.draw.arc(surf, (140, 120, 80),
                    (cx + 2, cy - 1, 4, 5), -1.5, 1.5, 1)
    # Liquid top
    pygame.draw.rect(surf, (180, 140, 50), (cx - 2, cy - 1, 4, 2))
    # Foam
    pygame.draw.rect(surf, (240, 230, 200), (cx - 2, cy - 2, 4, 2))


def _draw_pickaxe_icon(surf, s):
    cx, cy = s // 2, s // 2
    # Handle (diagonal)
    pygame.draw.line(surf, (100, 70, 40), (cx - 3, cy + 3), (cx + 3, cy - 3), 2)
    # Pick head
    pygame.draw.line(surf, (160, 160, 170), (cx + 1, cy - 4), (cx + 5, cy - 1), 2)
    pygame.draw.line(surf, (160, 160, 170), (cx + 1, cy - 4), (cx - 2, cy - 1), 2)


def _draw_generic_icon(surf, s):
    """Fallback: simple square with dot."""
    cx, cy = s // 2, s // 2
    pygame.draw.rect(surf, (120, 120, 130), (cx - 3, cy - 3, 6, 6))
    pygame.draw.rect(surf, (90, 90, 100), (cx - 3, cy - 3, 6, 6), 1)
    pygame.draw.circle(surf, (160, 160, 170), (cx, cy), 1)

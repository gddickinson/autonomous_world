"""Profession-specific sprite hints — visual differentiation for NPC professions.

Draws small visual indicators on NPC body parts based on their profession:
- Guards/Soldiers: helmet on head, darker armor torso
- Merchants: wider tan apron on torso
- Farmers: straw hat (wide brim, yellow-brown)
- Blacksmiths: darker sooty arms, hammer tool
- Fishermen: blue tint, fishing rod
- Priests/Clerics: white/gold lighter torso
- Scholars/Wizards: purple/blue robe, pointy hat
- Innkeepers: apron + small barrel indicator
"""

import pygame


# ---------------------------------------------------------------------------
# Profession -> visual config
# ---------------------------------------------------------------------------

# Maps profession keyword -> (torso_color_override, arm_color_override,
#                              head_type, extra_draw_func_name)
# head_type: None, "helmet", "straw_hat", "pointy_hat"
# Colors can be None to keep defaults.

PROFESSION_VISUALS = {
    # Guards / Soldiers
    "guard":     {"torso": (130, 135, 145), "arms": None, "head": "helmet"},
    "soldier":   {"torso": (125, 130, 140), "arms": None, "head": "helmet"},
    "knight":    {"torso": (150, 155, 170), "arms": None, "head": "helmet"},
    "mercenary": {"torso": (120, 115, 110), "arms": None, "head": "helmet"},

    # Merchants
    "merchant":  {"torso": (180, 155, 110), "arms": None, "head": None,
                  "torso_wide": True},
    "trader":    {"torso": (175, 150, 105), "arms": None, "head": None,
                  "torso_wide": True},
    "shopkeeper": {"torso": (170, 145, 100), "arms": None, "head": None,
                   "torso_wide": True},

    # Farmers
    "farmer":    {"torso": (140, 120, 80), "arms": None, "head": "straw_hat"},
    "rancher":   {"torso": (140, 120, 80), "arms": None, "head": "straw_hat"},
    "shepherd":  {"torso": (135, 115, 75), "arms": None, "head": "straw_hat"},

    # Blacksmiths
    "blacksmith": {"torso": (100, 90, 80), "arms": (80, 70, 60),
                   "head": None, "tool": "hammer"},
    "smith":      {"torso": (100, 90, 80), "arms": (80, 70, 60),
                   "head": None, "tool": "hammer"},
    "armorer":    {"torso": (95, 85, 75), "arms": (75, 65, 55),
                   "head": None, "tool": "hammer"},

    # Fishermen
    "fisherman":  {"torso": (90, 120, 150), "arms": (100, 130, 160),
                   "head": None, "tool": "fishing_rod"},
    "fisher":     {"torso": (90, 120, 150), "arms": (100, 130, 160),
                   "head": None, "tool": "fishing_rod"},

    # Priests / Clerics
    "priest":    {"torso": (230, 220, 200), "arms": (225, 215, 195),
                  "head": None},
    "cleric":    {"torso": (220, 210, 170), "arms": (215, 205, 165),
                  "head": None},
    "monk":      {"torso": (160, 130, 80), "arms": (155, 125, 75),
                  "head": None},

    # Scholars / Wizards
    "scholar":   {"torso": (100, 80, 140), "arms": (95, 75, 135),
                  "head": "pointy_hat"},
    "wizard":    {"torso": (80, 60, 150), "arms": (75, 55, 145),
                  "head": "pointy_hat"},
    "mage":      {"torso": (90, 70, 160), "arms": (85, 65, 155),
                  "head": "pointy_hat"},
    "sage":      {"torso": (110, 90, 130), "arms": (105, 85, 125),
                  "head": "pointy_hat"},

    # Innkeepers
    "innkeeper": {"torso": (170, 140, 100), "arms": None, "head": None,
                  "torso_wide": True, "tool": "barrel"},
    "barkeep":   {"torso": (165, 135, 95), "arms": None, "head": None,
                  "torso_wide": True, "tool": "barrel"},
    "tavern keeper": {"torso": (165, 135, 95), "arms": None, "head": None,
                      "torso_wide": True, "tool": "barrel"},
}

# Build a quick lookup: lowercase profession -> config
_PROF_CACHE = {}


def _get_prof_visual(profession: str) -> dict:
    """Look up profession visuals, with caching."""
    if not profession:
        return {}
    key = profession.lower()
    cached = _PROF_CACHE.get(key)
    if cached is not None:
        return cached
    # Direct match
    result = PROFESSION_VISUALS.get(key, {})
    if not result:
        # Partial match — check if any key is contained in profession
        for prof_key, config in PROFESSION_VISUALS.items():
            if prof_key in key:
                result = config
                break
    _PROF_CACHE[key] = result
    return result


# ---------------------------------------------------------------------------
# Override helpers — called from draw_npc_body
# ---------------------------------------------------------------------------

def get_profession_torso_color(profession: str) -> tuple:
    """Return torso color override for a profession, or None."""
    vis = _get_prof_visual(profession)
    return vis.get("torso")


def get_profession_arm_color(profession: str) -> tuple:
    """Return arm color override for a profession, or None."""
    vis = _get_prof_visual(profession)
    return vis.get("arms")


def should_widen_torso(profession: str) -> bool:
    """Return True if this profession should have a wider torso (apron)."""
    vis = _get_prof_visual(profession)
    return vis.get("torso_wide", False)


def get_head_type(profession: str) -> str:
    """Return head decoration type: 'helmet', 'straw_hat', 'pointy_hat', or None."""
    vis = _get_prof_visual(profession)
    return vis.get("head")


def get_tool_type(profession: str) -> str:
    """Return tool type: 'hammer', 'fishing_rod', 'barrel', or None."""
    vis = _get_prof_visual(profession)
    return vis.get("tool")


# ---------------------------------------------------------------------------
# Drawing functions for head decorations and tools
# ---------------------------------------------------------------------------

def draw_profession_head(screen, profession: str, head_x: int, head_y: int,
                         head_r: int, rs: int):
    """Draw profession-specific head decoration on top of the normal head."""
    head_type = get_head_type(profession)
    if not head_type:
        return

    draw = pygame.draw

    if head_type == "helmet":
        # Grey rectangle helmet on top of head
        hw = max(3, head_r * 2)
        hh = max(2, rs)
        hx = head_x - hw // 2
        hy = head_y - head_r - hh // 2
        draw.rect(screen, (160, 165, 175), (hx, hy, hw, hh))
        # Visor line
        draw.line(screen, (120, 125, 135),
                  (hx, hy + hh), (hx + hw, hy + hh), 1)
        # Nose guard (small vertical line)
        if rs >= 3:
            draw.line(screen, (140, 145, 155),
                      (head_x, hy + hh), (head_x, hy + hh + 2), 1)

    elif head_type == "straw_hat":
        # Wide brim straw hat — yellow-brown
        brim_w = max(5, head_r * 3)
        brim_h = max(1, rs // 2)
        crown_w = max(3, head_r + 2)
        crown_h = max(2, rs)
        # Brim
        bx = head_x - brim_w // 2
        by = head_y - head_r - 1
        draw.rect(screen, (200, 175, 100), (bx, by, brim_w, brim_h))
        # Crown
        cx = head_x - crown_w // 2
        cy = by - crown_h
        draw.rect(screen, (190, 165, 90), (cx, cy, crown_w, crown_h))

    elif head_type == "pointy_hat":
        # Pointy wizard/scholar hat — purple/blue
        base_w = max(4, head_r * 2 + 2)
        hat_h = max(4, rs * 2 + 2)
        base_y = head_y - head_r
        # Triangle from base to point
        pts = [
            (head_x - base_w // 2, base_y),       # left base
            (head_x + base_w // 2, base_y),        # right base
            (head_x + 1, base_y - hat_h),          # tip (slightly off-center)
        ]
        draw.polygon(screen, (80, 60, 140), pts)
        # Star at tip
        if rs >= 3:
            draw.circle(screen, (220, 200, 100),
                        (head_x + 1, base_y - hat_h), max(1, rs // 3))
        # Hat brim
        draw.line(screen, (70, 50, 130),
                  (head_x - base_w // 2 - 1, base_y),
                  (head_x + base_w // 2 + 1, base_y), 1)


def draw_profession_tool(screen, profession: str, hand_x: int, hand_y: int,
                         rs: int):
    """Draw a profession-specific tool near the NPC's hand."""
    tool = get_tool_type(profession)
    if not tool:
        return

    draw = pygame.draw

    if tool == "hammer":
        # Small hammer: handle + head
        handle_len = max(3, rs * 2)
        # Handle from hand downward-right
        hx2 = hand_x + max(2, rs)
        hy2 = hand_y - handle_len
        draw.line(screen, (120, 90, 50), (hand_x, hand_y), (hx2, hy2),
                  max(1, rs // 3))
        # Hammer head (small rect at top)
        hw = max(3, rs + 2)
        hh = max(2, rs)
        draw.rect(screen, (140, 140, 150), (hx2 - hw // 2, hy2 - hh, hw, hh))

    elif tool == "fishing_rod":
        # Fishing rod: line from hand curving up
        rod_len = max(5, rs * 3)
        tip_x = hand_x + max(3, rs * 2)
        tip_y = hand_y - rod_len
        draw.line(screen, (140, 110, 60), (hand_x, hand_y), (tip_x, tip_y),
                  max(1, rs // 3))
        # Fishing line drooping from tip
        line_end_y = tip_y + max(4, rs * 2)
        draw.line(screen, (180, 180, 200),
                  (tip_x, tip_y), (tip_x + 1, line_end_y), 1)
        # Small hook/bobber
        if rs >= 2:
            draw.circle(screen, (220, 60, 60),
                        (tip_x + 1, line_end_y), max(1, rs // 3))

    elif tool == "barrel":
        # Small barrel indicator near NPC
        bw = max(3, rs + 1)
        bh = max(4, rs + 2)
        bx = hand_x + max(2, rs)
        by = hand_y - bh // 2
        draw.rect(screen, (140, 100, 50), (bx, by, bw, bh))
        # Barrel bands
        draw.line(screen, (100, 70, 30),
                  (bx, by + bh // 3), (bx + bw, by + bh // 3), 1)
        draw.line(screen, (100, 70, 30),
                  (bx, by + 2 * bh // 3), (bx + bw, by + 2 * bh // 3), 1)

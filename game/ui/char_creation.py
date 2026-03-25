"""
Character creation screen — shown before the game world loads.

Lets the player pick race, class, and roll ability scores.
Returns a dict with character parameters or None if cancelled.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_HIGHLIGHT, WHITE, GRAY, YELLOW
from game.data.dnd import (
    RACES, RACE_NAMES, CLASSES, CLASS_NAMES,
    roll_ability_scores, ability_modifier, get_class_hp,
    get_class_abilities, get_proficiency_bonus, WEAPONS, ARMOR,
)


# ----------------------------------------------------------------
# Colour palette (matches MenuSystem style)
# ----------------------------------------------------------------
BG = (10, 10, 20)
TITLE_COLOR = UI_HIGHLIGHT
TEXT = (220, 220, 230)
TEXT_DIM = (140, 140, 155)
TEXT_BRIGHT = (255, 255, 255)
HIGHLIGHT_BG = (50, 65, 110)
BOX_BG = (30, 30, 45)
BOX_BORDER = (70, 70, 90)
BOX_ACTIVE = (80, 100, 160)
ACCENT_GREEN = (80, 200, 120)
ACCENT_RED = (220, 80, 80)
ACCENT_GOLD = (220, 200, 80)

# Panel geometry
LEFT_X = 30
MID_X = 260
RIGHT_X = 500
PANEL_TOP = 80
LIST_ITEM_H = 30
BUTTON_H = 44


# ----------------------------------------------------------------
# Starting equipment per class
# ----------------------------------------------------------------
CLASS_STARTING_EQUIPMENT = {
    "Fighter":   ["Longsword", "Chain Mail", "Health Potion"],
    "Wizard":    ["Quarterstaff", "Bread", "Health Potion"],
    "Cleric":    ["Mace", "Chain Shirt", "Health Potion"],
    "Rogue":     ["Shortsword", "Leather", "Health Potion"],
    "Ranger":    ["Longbow", "Studded", "Health Potion"],
    "Paladin":   ["Longsword", "Chain Mail", "Health Potion"],
    "Barbarian": ["Greatsword", "Leather", "Health Potion"],
    "Bard":      ["Rapier", "Leather", "Health Potion"],
    "Druid":     ["Quarterstaff", "Leather", "Health Potion"],
    "Monk":      ["Quarterstaff", "Bread", "Health Potion"],
    "Sorcerer":  ["Dagger", "Bread", "Health Potion"],
    "Warlock":   ["Dagger", "Leather", "Health Potion"],
}


# ----------------------------------------------------------------
# Helper: build preview data for current selections
# ----------------------------------------------------------------
def _build_preview(race_name, class_name, scores):
    """Return a dict of computed preview values."""
    cls = CLASSES.get(class_name, {})
    race = RACES.get(race_name, {})
    con_mod = ability_modifier(scores.get("constitution", 10))
    dex_mod = ability_modifier(scores.get("dexterity", 10))
    hp = get_class_hp(class_name, 1, con_mod)
    ac = 10 + dex_mod
    abilities = get_class_abilities(class_name, 1)
    if cls.get("spellcaster"):
        from game.data.dnd import SPELLS as _DND_SPELLS
        full_list = list(cls.get("spell_list", []))
        cantrips = [s for s in full_list if _DND_SPELLS.get(s, {}).get("level", 99) == 0]
        lvl1 = [s for s in full_list if _DND_SPELLS.get(s, {}).get("level", 99) == 1]
        spells = cantrips[:3] + lvl1[:2]
        if not spells:
            spells = full_list[:5]
    else:
        spells = []
    traits = race.get("traits", [])
    equip = CLASS_STARTING_EQUIPMENT.get(class_name, [])
    return {
        "hp": hp, "ac": ac, "abilities": abilities,
        "spells": spells, "traits": traits, "equipment": equip,
        "description": cls.get("description", ""),
        "race_desc": race.get("description", ""),
    }


# ----------------------------------------------------------------
# Draw helpers
# ----------------------------------------------------------------
def _draw_list(surface, font, items, selected, x, y, w, active_panel, panel_id):
    """Draw a selectable list. Returns list of rects for click detection."""
    rects = []
    for i, name in enumerate(items):
        ry = y + i * LIST_ITEM_H
        rect = pygame.Rect(x, ry, w, LIST_ITEM_H - 2)
        rects.append(rect)
        is_sel = (i == selected)
        bg = HIGHLIGHT_BG if is_sel else BOX_BG
        border = BOX_ACTIVE if (active_panel == panel_id and is_sel) else BOX_BORDER
        pygame.draw.rect(surface, bg, rect)
        pygame.draw.rect(surface, border, rect, 1)
        color = TEXT_BRIGHT if is_sel else TEXT
        txt = font.render(name, True, color)
        surface.blit(txt, (x + 8, ry + 5))
    return rects


def _draw_button(surface, font, label, rect, hover=False):
    """Draw a button; return the rect."""
    bg = BOX_ACTIVE if hover else BOX_BG
    pygame.draw.rect(surface, bg, rect)
    pygame.draw.rect(surface, ACCENT_GREEN if "START" in label else BOX_BORDER, rect, 2)
    txt = font.render(label, True, TEXT_BRIGHT)
    surface.blit(txt, (rect.x + (rect.w - txt.get_width()) // 2,
                       rect.y + (rect.h - txt.get_height()) // 2))
    return rect


def _draw_preview(surface, fonts, preview, scores, x, y, w):
    """Draw the right-panel character preview."""
    font_md, font_sm = fonts
    cy = y

    # Ability scores
    heading = font_md.render("Ability Scores", True, ACCENT_GOLD)
    surface.blit(heading, (x, cy))
    cy += 22
    for attr in ("strength", "dexterity", "constitution",
                 "intelligence", "wisdom", "charisma"):
        val = scores.get(attr, 10)
        mod = ability_modifier(val)
        sign = "+" if mod >= 0 else ""
        line = f"{attr[:3].upper()} {val:2d} ({sign}{mod})"
        surface.blit(font_sm.render(line, True, TEXT), (x, cy))
        cy += 16

    cy += 6
    # HP & AC
    surface.blit(font_md.render(f"HP: {preview['hp']}   AC: {preview['ac']}", True, TEXT_BRIGHT), (x, cy))
    cy += 24

    # Class abilities
    if preview["abilities"]:
        surface.blit(font_md.render("Abilities", True, ACCENT_GOLD), (x, cy))
        cy += 20
        for ab in preview["abilities"][:5]:
            surface.blit(font_sm.render(f"- {ab}", True, TEXT), (x, cy))
            cy += 15
        cy += 4

    # Spells
    if preview["spells"]:
        surface.blit(font_md.render("Starting Spells", True, ACCENT_GOLD), (x, cy))
        cy += 20
        for sp in preview["spells"]:
            surface.blit(font_sm.render(f"- {sp}", True, TEXT), (x, cy))
            cy += 15
        cy += 4

    # Equipment
    surface.blit(font_md.render("Equipment", True, ACCENT_GOLD), (x, cy))
    cy += 20
    for eq in preview["equipment"]:
        surface.blit(font_sm.render(f"- {eq}", True, TEXT), (x, cy))
        cy += 15
    cy += 4

    # Race traits
    if preview["traits"]:
        surface.blit(font_md.render("Race Traits", True, ACCENT_GOLD), (x, cy))
        cy += 20
        for t in preview["traits"]:
            surface.blit(font_sm.render(f"- {t}", True, TEXT), (x, cy))
            cy += 15
        cy += 4

    # Descriptions (wrapped crudely)
    if preview.get("race_desc"):
        surface.blit(font_sm.render(preview["race_desc"][:60], True, TEXT_DIM), (x, cy))
        cy += 14
    if preview.get("description"):
        surface.blit(font_sm.render(preview["description"][:60], True, TEXT_DIM), (x, cy))


# ----------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------
def show_character_creation(screen, clock):
    """Run the character creation screen.

    Returns:
        dict  {"race": str, "char_class": str, "ability_scores": dict}
        None  if the user cancelled (ESC).
    """
    font_title = pygame.font.SysFont("monospace", 36, bold=True)
    font_lg = pygame.font.SysFont("monospace", 20)
    font_md = pygame.font.SysFont("monospace", 16)
    font_sm = pygame.font.SysFont("monospace", 13)

    race_idx = 0
    class_idx = 0
    active_panel = 0  # 0 = race, 1 = class
    scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])

    # Button rects (created once, repositioned each frame)
    start_rect = pygame.Rect(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT - 70, 240, BUTTON_H)
    reroll_rect = pygame.Rect(SCREEN_WIDTH // 2 + 140, SCREEN_HEIGHT - 70, 180, BUTTON_H)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        # --- events ---
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return None
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return None
                elif ev.key == pygame.K_TAB:
                    active_panel = 1 - active_panel
                elif ev.key == pygame.K_UP:
                    if active_panel == 0:
                        race_idx = (race_idx - 1) % len(RACE_NAMES)
                    else:
                        class_idx = (class_idx - 1) % len(CLASS_NAMES)
                    scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])
                elif ev.key == pygame.K_DOWN:
                    if active_panel == 0:
                        race_idx = (race_idx + 1) % len(RACE_NAMES)
                    else:
                        class_idx = (class_idx + 1) % len(CLASS_NAMES)
                    scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])
                elif ev.key == pygame.K_r:
                    scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])
                elif ev.key == pygame.K_RETURN:
                    return {
                        "race": RACE_NAMES[race_idx],
                        "char_class": CLASS_NAMES[class_idx],
                        "ability_scores": dict(scores),
                    }
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                # Check race list clicks
                for i, r in enumerate(race_rects):
                    if r.collidepoint(mouse_pos):
                        race_idx = i
                        active_panel = 0
                        scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])
                # Check class list clicks
                for i, r in enumerate(class_rects):
                    if r.collidepoint(mouse_pos):
                        class_idx = i
                        active_panel = 1
                        scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])
                # Buttons
                if start_rect.collidepoint(mouse_pos):
                    return {
                        "race": RACE_NAMES[race_idx],
                        "char_class": CLASS_NAMES[class_idx],
                        "ability_scores": dict(scores),
                    }
                if reroll_rect.collidepoint(mouse_pos):
                    scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])

        # --- draw ---
        screen.fill(BG)

        # Title
        title = font_title.render("CREATE YOUR CHARACTER", True, TITLE_COLOR)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 20))

        # Left panel: Race
        screen.blit(font_lg.render("Race", True, ACCENT_GOLD), (LEFT_X, PANEL_TOP - 24))
        race_rects = _draw_list(screen, font_md, RACE_NAMES, race_idx,
                                LEFT_X, PANEL_TOP, 200, active_panel, 0)

        # Middle panel: Class
        screen.blit(font_lg.render("Class", True, ACCENT_GOLD), (MID_X, PANEL_TOP - 24))
        class_rects = _draw_list(screen, font_md, CLASS_NAMES, class_idx,
                                 MID_X, PANEL_TOP, 210, active_panel, 1)

        # Right panel: Preview
        preview = _build_preview(RACE_NAMES[race_idx], CLASS_NAMES[class_idx], scores)
        _draw_preview(screen, (font_md, font_sm), preview, scores, RIGHT_X, PANEL_TOP, 400)

        # Buttons
        _draw_button(screen, font_md, "[ START GAME ]", start_rect,
                     start_rect.collidepoint(mouse_pos))
        _draw_button(screen, font_md, "[ REROLL  R ]", reroll_rect,
                     reroll_rect.collidepoint(mouse_pos))

        # Controls hint
        hint = "UP/DOWN: navigate   TAB: switch panel   R: reroll   ENTER: start   ESC: cancel"
        screen.blit(font_sm.render(hint, True, TEXT_DIM),
                    (SCREEN_WIDTH // 2 - font_sm.size(hint)[0] // 2, SCREEN_HEIGHT - 22))

        pygame.display.flip()
        clock.tick(30)

    return None

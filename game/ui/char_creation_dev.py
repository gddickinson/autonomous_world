"""
Developer / cheat character creation screen.

Allows manual control over every character attribute:
level, ability scores, gold, HP, god mode, starting location, items.

Returns a dict of overrides or None if cancelled.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_HIGHLIGHT
from game.data.dnd import (
    RACES, RACE_NAMES, CLASSES, CLASS_NAMES,
    roll_ability_scores, ability_modifier, get_class_hp,
)

# ----------------------------------------------------------------
# Colours (same palette as char_creation.py)
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
ACCENT_GOLD = (220, 200, 80)
ACCENT_RED = (220, 80, 80)

ABILITY_NAMES = ["strength", "dexterity", "constitution",
                 "intelligence", "wisdom", "charisma"]

SPAWN_LOCATIONS = ["mainland", "test_island"]

# Items that can be added in dev mode
DEV_ITEMS = [
    "Longsword", "Greatsword", "Rapier", "Longbow",
    "Plate", "Chain Mail", "Leather",
    "Health Potion", "Gold Nugget", "Ancient Relic",
    "Bread", "Iron Ore", "Mana Potion",
]

ROW_H = 28
COL1_X = 40
COL2_X = 400
COL3_X = 740


# ----------------------------------------------------------------
# Editable numeric field
# ----------------------------------------------------------------
class _NumField:
    """Small editable integer field."""
    __slots__ = ("label", "value", "min_val", "max_val", "editing", "buf")

    def __init__(self, label, value, min_val=1, max_val=9999):
        self.label = label
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.editing = False
        self.buf = ""

    def start_edit(self):
        self.editing = True
        self.buf = str(self.value)

    def finish_edit(self):
        self.editing = False
        try:
            v = int(self.buf)
            self.value = max(self.min_val, min(self.max_val, v))
        except ValueError:
            pass

    def key_input(self, key, unicode_char):
        if key == pygame.K_RETURN or key == pygame.K_TAB:
            self.finish_edit()
        elif key == pygame.K_BACKSPACE:
            self.buf = self.buf[:-1]
        elif unicode_char.isdigit():
            self.buf += unicode_char


# ----------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------
def show_dev_creation(screen, clock):
    """Run the dev character creation screen.

    Returns:
        dict with keys:
            race, char_class, ability_scores, level, gold, hp, max_hp,
            god_mode, extra_items, spawn_location
        None if cancelled.
    """
    font_title = pygame.font.SysFont("monospace", 32, bold=True)
    font_md = pygame.font.SysFont("monospace", 16)
    font_sm = pygame.font.SysFont("monospace", 13)

    race_idx = 0
    class_idx = 0
    scores = roll_ability_scores(RACE_NAMES[0], CLASS_NAMES[0])

    # Editable fields
    level_field = _NumField("Level", 1, 1, 20)
    gold_field = _NumField("Gold", 100, 0, 99999)
    hp_field = _NumField("HP", 0, 1, 99999)  # 0 = auto-calculate
    ability_fields = {a: _NumField(a[:3].upper(), scores[a], 1, 30) for a in ABILITY_NAMES}
    all_fields = [level_field, gold_field, hp_field] + list(ability_fields.values())

    god_mode = False
    spawn_idx = 0
    extra_items = []  # list of item name strings

    # Track which field is being edited
    active_field = None

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return None

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    if active_field and active_field.editing:
                        active_field.finish_edit()
                        active_field = None
                    else:
                        return None

                elif active_field and active_field.editing:
                    active_field.key_input(ev.key, ev.unicode)
                    if not active_field.editing:
                        # Tab finished — sync ability scores
                        _sync_ability_fields(ability_fields, scores)
                        active_field = None

                elif ev.key == pygame.K_RETURN:
                    # Finish and return
                    return _build_result(
                        race_idx, class_idx, ability_fields, level_field,
                        gold_field, hp_field, god_mode, extra_items, spawn_idx,
                        scores,
                    )
                elif ev.key == pygame.K_r:
                    scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[class_idx])
                    for a in ABILITY_NAMES:
                        ability_fields[a].value = scores[a]
                elif ev.key == pygame.K_g:
                    god_mode = not god_mode

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                _handle_click(
                    mouse_pos, race_rects, class_rects, field_rects,
                    item_rects, start_rect, god_rect, spawn_rect,
                    race_idx, class_idx, scores, ability_fields,
                    all_fields, extra_items, level_field, gold_field,
                    hp_field, god_mode, spawn_idx, active_field,
                )
                # Re-extract mutable state after click handler
                race_idx, class_idx, scores, god_mode, spawn_idx, active_field = (
                    _click_state["race_idx"], _click_state["class_idx"],
                    _click_state["scores"], _click_state["god_mode"],
                    _click_state["spawn_idx"], _click_state["active_field"],
                )
                if _click_state.get("start"):
                    return _build_result(
                        race_idx, class_idx, ability_fields, level_field,
                        gold_field, hp_field, god_mode, extra_items, spawn_idx,
                        scores,
                    )

        # --- draw ---
        screen.fill(BG)
        title = font_title.render("DEV CHARACTER CREATION", True, ACCENT_RED)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 12))

        # Column 1: Race + Class lists
        cy = 60
        screen.blit(font_md.render("Race", True, ACCENT_GOLD), (COL1_X, cy))
        cy += 20
        race_rects = _draw_mini_list(screen, font_sm, RACE_NAMES, race_idx, COL1_X, cy, 160)
        cy += len(RACE_NAMES) * 20 + 10
        screen.blit(font_md.render("Class", True, ACCENT_GOLD), (COL1_X, cy))
        cy += 20
        class_rects = _draw_mini_list(screen, font_sm, CLASS_NAMES, class_idx, COL1_X, cy, 160)

        # Column 2: Editable fields
        cy = 60
        screen.blit(font_md.render("Ability Scores  (click to edit)", True, ACCENT_GOLD), (COL2_X, cy))
        cy += 22
        field_rects = {}
        for a in ABILITY_NAMES:
            f = ability_fields[a]
            rect = _draw_field(screen, font_sm, f, COL2_X, cy, active_field)
            field_rects[a] = rect
            cy += 22

        cy += 10
        screen.blit(font_md.render("Character Stats", True, ACCENT_GOLD), (COL2_X, cy))
        cy += 22
        for f in (level_field, gold_field, hp_field):
            rect = _draw_field(screen, font_sm, f, COL2_X, cy, active_field)
            field_rects[f.label] = rect
            cy += 22

        cy += 10
        # God mode toggle
        god_label = f"God Mode: {'ON' if god_mode else 'OFF'}  [G]"
        god_color = ACCENT_GREEN if god_mode else TEXT_DIM
        god_rect = pygame.Rect(COL2_X, cy, 220, 22)
        screen.blit(font_md.render(god_label, True, god_color), (COL2_X, cy))
        cy += 26

        # Spawn location
        spawn_label = f"Spawn: {SPAWN_LOCATIONS[spawn_idx]}"
        spawn_rect = pygame.Rect(COL2_X, cy, 220, 22)
        screen.blit(font_md.render(spawn_label, True, TEXT), (COL2_X, cy))
        cy += 26

        # HP note
        if hp_field.value == 0:
            screen.blit(font_sm.render("HP=0 means auto-calculate from class/level", True, TEXT_DIM), (COL2_X, cy))

        # Column 3: Items
        cy = 60
        screen.blit(font_md.render("Add Items (click to toggle)", True, ACCENT_GOLD), (COL3_X, cy))
        cy += 22
        item_rects = []
        for item_name in DEV_ITEMS:
            in_list = item_name in extra_items
            color = ACCENT_GREEN if in_list else TEXT_DIM
            rect = pygame.Rect(COL3_X, cy, 220, 18)
            item_rects.append((rect, item_name))
            prefix = "[x]" if in_list else "[ ]"
            screen.blit(font_sm.render(f"{prefix} {item_name}", True, color), (COL3_X, cy))
            cy += 18

        # Start button
        start_rect = pygame.Rect(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT - 60, 240, 40)
        _draw_button(screen, font_md, "[ START GAME ]", start_rect,
                     start_rect.collidepoint(mouse_pos))

        # Hints
        hint = "R: reroll stats   G: toggle god   ENTER: start   ESC: cancel"
        screen.blit(font_sm.render(hint, True, TEXT_DIM),
                    (SCREEN_WIDTH // 2 - font_sm.size(hint)[0] // 2, SCREEN_HEIGHT - 18))

        pygame.display.flip()
        clock.tick(30)

    return None


# ----------------------------------------------------------------
# Internal draw helpers
# ----------------------------------------------------------------
def _draw_mini_list(surface, font, items, selected, x, y, w):
    """Compact selectable list. Returns list of rects."""
    rects = []
    for i, name in enumerate(items):
        ry = y + i * 20
        rect = pygame.Rect(x, ry, w, 19)
        rects.append(rect)
        bg = HIGHLIGHT_BG if i == selected else BG
        pygame.draw.rect(surface, bg, rect)
        color = TEXT_BRIGHT if i == selected else TEXT
        surface.blit(font.render(name, True, color), (x + 4, ry + 2))
    return rects


def _draw_field(surface, font, field, x, y, active_field):
    """Draw one editable numeric field. Returns its rect."""
    rect = pygame.Rect(x, y, 200, 20)
    is_active = (active_field is field and field.editing)
    display = field.buf + "_" if is_active else str(field.value)
    color = ACCENT_GREEN if is_active else TEXT
    label = f"{field.label:5s}: {display}"
    surface.blit(font.render(label, True, color), (x, y + 2))
    return rect


def _draw_button(surface, font, label, rect, hover=False):
    bg = BOX_ACTIVE if hover else BOX_BG
    pygame.draw.rect(surface, bg, rect)
    pygame.draw.rect(surface, ACCENT_GREEN, rect, 2)
    txt = font.render(label, True, TEXT_BRIGHT)
    surface.blit(txt, (rect.x + (rect.w - txt.get_width()) // 2,
                       rect.y + (rect.h - txt.get_height()) // 2))


# ----------------------------------------------------------------
# Click handling (uses module-level dict to pass mutable state back)
# ----------------------------------------------------------------
_click_state = {}


def _handle_click(mouse_pos, race_rects, class_rects, field_rects,
                  item_rects, start_rect, god_rect, spawn_rect,
                  race_idx, class_idx, scores, ability_fields,
                  all_fields, extra_items, level_field, gold_field,
                  hp_field, god_mode, spawn_idx, active_field):
    """Process a mouse click. Updates _click_state dict."""
    _click_state.update({
        "race_idx": race_idx, "class_idx": class_idx, "scores": scores,
        "god_mode": god_mode, "spawn_idx": spawn_idx, "active_field": active_field,
        "start": False,
    })

    # Finish any editing field first
    if active_field and active_field.editing:
        active_field.finish_edit()
        _sync_ability_fields(ability_fields, scores)
        _click_state["active_field"] = None

    # Race list
    for i, r in enumerate(race_rects):
        if r.collidepoint(mouse_pos):
            _click_state["race_idx"] = i
            new_scores = roll_ability_scores(RACE_NAMES[i], CLASS_NAMES[class_idx])
            _click_state["scores"] = new_scores
            for a in ABILITY_NAMES:
                ability_fields[a].value = new_scores[a]
            return

    # Class list
    for i, r in enumerate(class_rects):
        if r.collidepoint(mouse_pos):
            _click_state["class_idx"] = i
            new_scores = roll_ability_scores(RACE_NAMES[race_idx], CLASS_NAMES[i])
            _click_state["scores"] = new_scores
            for a in ABILITY_NAMES:
                ability_fields[a].value = new_scores[a]
            return

    # Editable fields
    for key, rect in field_rects.items():
        if rect.collidepoint(mouse_pos):
            # Find the field object
            if key in ability_fields:
                field = ability_fields[key]
            elif key == "Level":
                field = level_field
            elif key == "Gold":
                field = gold_field
            elif key == "HP":
                field = hp_field
            else:
                continue
            field.start_edit()
            _click_state["active_field"] = field
            return

    # Item toggles
    for rect, item_name in item_rects:
        if rect.collidepoint(mouse_pos):
            if item_name in extra_items:
                extra_items.remove(item_name)
            else:
                extra_items.append(item_name)
            return

    # God mode toggle
    if god_rect.collidepoint(mouse_pos):
        _click_state["god_mode"] = not god_mode
        return

    # Spawn toggle
    if spawn_rect.collidepoint(mouse_pos):
        _click_state["spawn_idx"] = (spawn_idx + 1) % len(SPAWN_LOCATIONS)
        return

    # Start button
    if start_rect.collidepoint(mouse_pos):
        _click_state["start"] = True


def _sync_ability_fields(ability_fields, scores):
    """Copy field values back into scores dict."""
    for a in ABILITY_NAMES:
        scores[a] = ability_fields[a].value


def _build_result(race_idx, class_idx, ability_fields, level_field,
                  gold_field, hp_field, god_mode, extra_items, spawn_idx,
                  scores):
    """Build the result dict from current state."""
    _sync_ability_fields(ability_fields, scores)
    con_mod = ability_modifier(scores.get("constitution", 10))
    class_name = CLASS_NAMES[class_idx]
    level = level_field.value
    hp = hp_field.value
    if hp == 0:
        hp = get_class_hp(class_name, level, con_mod)

    return {
        "race": RACE_NAMES[race_idx],
        "char_class": class_name,
        "ability_scores": dict(scores),
        "level": level,
        "gold": gold_field.value,
        "hp": hp,
        "max_hp": hp,
        "god_mode": god_mode,
        "extra_items": list(extra_items),
        "spawn_location": SPAWN_LOCATIONS[spawn_idx],
    }

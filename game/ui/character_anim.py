"""Procedural character animation — body parts, walk cycles, combat poses, death."""

import math
import pygame
from game.settings import TILE_SIZE
import game.ui.profession_sprites as _prof_sprites
from game.ui.character_detail import (
    draw_detailed_head, draw_detailed_eyes, draw_detailed_torso,
    draw_detailed_arm, draw_detailed_legs, _race_width,
)

_sin = math.sin
_cos = math.cos
_sqrt = math.sqrt
_tau = math.tau

SKIN_TONES = {
    "human":    (210, 185, 155),
    "elf":      (220, 205, 175),
    "dwarf":    (195, 165, 130),
    "halfling": (215, 190, 155),
    "gnome":    (210, 195, 165),
    "half-orc": (140, 160, 120),
    "orc":      (120, 145, 100),
    "tiefling": (180, 130, 130),
    "goblin":   (130, 150, 90),
    "dragonborn": (160, 170, 150),
}

ARMOR_TINTS = {
    "Fighter":   (170, 175, 185),
    "Paladin":   (190, 195, 210),
    "Barbarian": (140, 120, 100),
    "Ranger":    (100, 130, 90),
    "Rogue":     (70, 70, 80),
    "Knight":    (170, 175, 185),
    "Guard":     (150, 155, 165),
    "Soldier":   (145, 150, 160),
}

_RACE_SIZES = {
    "halfling": 0.7, "gnome": 0.7, "goblin": 0.7,
    "dwarf": 0.85,
    "human": 1.0, "elf": 1.0, "half-elf": 1.0, "tiefling": 1.0,
    "dragonborn": 1.15,
    "half-orc": 1.15, "orc": 1.2,
    "goliath": 1.3,
}

_PASSIVE_TYPES = frozenset({"deer", "rabbit", "chicken", "cow", "pig", "sheep",
                            "goat", "horse", "elk", "pheasant", "fox", "fish_school"})
_BEAST_TYPES = frozenset({"wolf", "bear", "boar", "dire_wolf", "owlbear", "wild_boar"})
_HUMANOID_TYPES = frozenset({"bandit", "goblin", "orc", "gnoll", "bugbear", "skeleton",
                             "zombie", "kobold", "hobgoblin"})
_LARGE_TYPES = frozenset({"ogre", "troll", "hill_giant", "minotaur", "young_dragon"})

_ARMED_MELEE_CLASSES = frozenset({"Fighter", "Paladin", "Barbarian", "Rogue", "Ranger"})
_ARMED_MELEE_PROFS = frozenset({"Guard", "Soldier", "Knight", "Mercenary"})
_ARMED_RANGED = frozenset({"Ranger", "Archer"})
_MAGE_CLASSES = frozenset({"Wizard", "Sorcerer", "Warlock", "Cleric", "Druid", "Bard"})
_ARMORED_CLASSES = frozenset({"Fighter", "Paladin", "Barbarian"})
_ARMORED_PROFS = frozenset({"Guard", "Soldier", "Knight"})

_MAGE_ORB_COLORS = {
    "Wizard": (80, 120, 220), "Sorcerer": (200, 80, 200),
    "Warlock": (140, 60, 180), "Cleric": (220, 200, 100),
    "Druid": (80, 180, 80), "Bard": (200, 140, 200),
}

_EYE_COLOR = (40, 40, 40)
_RED_EYE = (200, 40, 40)
_BROWN_EYE = (60, 40, 20)

_darken_cache = {}
_lighten_cache = {}


def _darken(color, amount=30):
    key = (color, amount)
    cached = _darken_cache.get(key)
    if cached is not None:
        return cached
    result = (max(0, color[0] - amount), max(0, color[1] - amount),
              max(0, color[2] - amount))
    _darken_cache[key] = result
    return result


def _lighten(color, amount=30):
    key = (color, amount)
    cached = _lighten_cache.get(key)
    if cached is not None:
        return cached
    result = (min(255, color[0] + amount), min(255, color[1] + amount),
              min(255, color[2] + amount))
    _lighten_cache[key] = result
    return result

def _get_skin(race: str) -> tuple:
    return SKIN_TONES.get(race.lower() if race else "", (210, 185, 155))

def _race_size(race: str) -> float:
    return _RACE_SIZES.get(race.lower() if race else "", 1.0)

_SPIDER_ANGLES = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
                   for a in range(0, 360, 45)]


class AnimState:
    """Lightweight per-entity animation state. Attached to entities as `_anim`."""
    __slots__ = ('walk_phase', 'idle_phase', 'death_timer', 'death_done',
                 'prev_x', 'prev_y', 'moving',
                 '_cached_skin', '_cached_race_size', '_cached_colors')

    def __init__(self):
        self.walk_phase = 0.0
        self.idle_phase = 0.0
        self.death_timer = -1.0
        self.death_done = False
        self.prev_x = 0.0
        self.prev_y = 0.0
        self.moving = False
        self._cached_skin = None
        self._cached_race_size = None
        self._cached_colors = None


def get_anim(entity) -> AnimState:
    """Get or create animation state for an entity."""
    anim = getattr(entity, '_anim', None)
    if anim is None:
        anim = AnimState()
        anim.prev_x = entity.x
        anim.prev_y = entity.y
        entity._anim = anim
    return anim

def update_anim(entity, dt: float):
    """Update animation state based on entity movement and status."""
    anim = get_anim(entity)

    dx = entity.x - anim.prev_x
    dy = entity.y - anim.prev_y
    anim.moving = abs(dx) > 0.01 or abs(dy) > 0.01
    anim.prev_x = entity.x
    anim.prev_y = entity.y

    if anim.moving:
        speed = _sqrt(dx * dx + dy * dy) / max(dt, 0.001)
        anim.walk_phase += dt * speed * 3.0
        if anim.walk_phase > _tau:
            anim.walk_phase -= _tau
    else:
        anim.walk_phase *= 0.85

    anim.idle_phase += dt * 1.5
    if anim.idle_phase > _tau:
        anim.idle_phase -= _tau

    if not entity.alive and anim.death_timer < 0:
        anim.death_timer = 0.0
    if anim.death_timer >= 0 and not anim.death_done:
        anim.death_timer = min(1.0, anim.death_timer + dt * 2.0)
        if anim.death_timer >= 1.0:
            anim.death_done = True


def draw_npc_body(screen, npc, sx: int, sy: int, s: int, mounted=False):
    """Draw an NPC with assembled body parts and animation.

    s = scale factor (TILE_SIZE // 4, usually 4).
    mounted: if True, skip legs and lower torso position (rider mode).
    """
    anim = get_anim(npc)
    body_color = npc.color

    # Death: minimal draw
    if anim.death_timer >= 0:
        _draw_death(screen, npc, sx, sy, s, anim, body_color)
        return

    # Pose-based rendering for non-walking/standing actions
    if not mounted:
        from game.ui.poses import get_pose, draw_lying_body, draw_sitting_body, \
            draw_kneeling_body, draw_working_body, draw_combat_body, \
            draw_fishing_body, draw_alert_body, draw_status_overlay
        pose = get_pose(npc)
        race = getattr(npc, 'race', 'human')
        skin = _get_skin(race)
        _pose_funcs = {
            "lying": draw_lying_body, "sitting": draw_sitting_body,
            "kneeling": draw_kneeling_body, "working": draw_working_body,
            "combat": draw_combat_body, "fishing": draw_fishing_body,
            "alert": draw_alert_body,
        }
        if pose in _pose_funcs:
            _pose_funcs[pose](screen, npc, sx, sy, s, body_color, skin)
            draw_status_overlay(screen, npc, sx, sy, s)
            return

    # Cache per-entity derived values
    if anim._cached_skin is None:
        race = getattr(npc, 'race', 'human')
        anim._cached_skin = _get_skin(race)
        anim._cached_race_size = _race_size(race)
        char_class = getattr(npc, 'char_class', '')
        profession = getattr(npc, 'profession', '')
        armored = char_class in _ARMORED_CLASSES or profession in _ARMORED_PROFS
        armor_color = ARMOR_TINTS.get(char_class, ARMOR_TINTS.get(profession, None))
        # Weapon type: 0=none, 1=melee, 2=ranged, 3=mage
        if char_class in _ARMED_MELEE_CLASSES or profession in _ARMED_MELEE_PROFS:
            weapon_type = 1
        elif char_class in _ARMED_RANGED or profession in _ARMED_RANGED:
            weapon_type = 2
        elif char_class in _MAGE_CLASSES:
            weapon_type = 3
        else:
            weapon_type = 0
        orb_color = _MAGE_ORB_COLORS.get(char_class, (140, 140, 220))
        anim._cached_colors = (char_class, profession, armored, armor_color,
                               weapon_type, orb_color)

    skin = anim._cached_skin
    size_mult = anim._cached_race_size
    char_class, profession, armored, armor_color, weapon_type, orb_color = anim._cached_colors

    rs = max(1, int(s * size_mult))

    # Walk swing — vertical offset simulates depth (front/back) in 2.5D
    walk_sin = _sin(anim.walk_phase)
    breath = _sin(anim.idle_phase) * 0.5
    breath_offset = int(breath * 0.5)
    head_bob = int(abs(_cos(anim.walk_phase)) * rs * 0.3) if anim.moving else 0

    # Leg/arm vertical swing (pixels) — sliding up/down = closer/further
    if anim.moving:
        leg_swing = int(walk_sin * rs * 1.2)
        arm_swing = int(-walk_sin * rs * 0.9)
    else:
        leg_swing = 0
        arm_swing = 0

    state = getattr(npc, 'state', 'idle')
    current_action = getattr(npc, 'current_action', '')

    # Talking gesture detection
    _talking = (state in ('talking', 'socializing')
                or 'talking' in (current_action or '')
                or 'conversation' in (current_action or ''))

    fleeing = state == 'fleeing'
    if fleeing:
        leg_swing = int(leg_swing * 1.6)
        arm_swing = int(arm_swing * 1.6)

    # Profession-based visual overrides
    prof_torso = _prof_sprites.get_profession_torso_color(profession)
    prof_arms = _prof_sprites.get_profession_arm_color(profession)
    prof_wide = _prof_sprites.should_widen_torso(profession)
    torso_color = (prof_torso if prof_torso and not (armored and armor_color)
                   else (armor_color if armored and armor_color else body_color))
    dark_body = _darken(body_color, 20)
    dark_body2 = _darken(body_color, 35)
    dark_torso = _darken(torso_color, 25)

    # Geometry
    leg_w = max(1, rs)
    leg_h = max(2, rs * 2)
    torso_w = max(3, rs * 3)
    if prof_wide:
        torso_w = max(4, int(rs * 3.6))  # wider torso for apron professions
    torso_h = max(3, rs * 3)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs + breath_offset
    arm_w = max(1, rs)
    arm_h = max(2, rs * 2)
    arm_top = torso_y + max(1, rs // 2)
    la_x = torso_x - arm_w
    ra_x = torso_x + torso_w
    head_r = max(2, rs + 1)
    head_x = sx
    head_y = torso_y - head_r + breath_offset - head_bob

    # Talking idle gestures: head nod + hand wave
    _talk_head_dy = 0
    _talk_arm_dx = 0
    if _talking:
        _phase = anim.idle_phase
        # Head nod: +-1 pixel, period ~1.5s (idle_phase runs at 1.5 rad/s)
        _talk_head_dy = int(round(_sin(_phase * 1.0) * 1.0))
        # Hand wave: +-2 pixels horizontal, slower period ~2s
        _talk_arm_dx = int(round(_sin(_phase * 0.75) * 2.0))
    head_y += _talk_head_dy
    hip_y = torso_y + torso_h

    draw = pygame.draw

    # ── Race width adjustment ─────────────────────────────────────
    race = getattr(npc, 'race', 'human')
    width_mult = _race_width(race)
    torso_w = max(3, int(torso_w * width_mult))
    torso_x = sx - torso_w // 2
    la_x = torso_x - arm_w
    ra_x = torso_x + torso_w

    has_robe = char_class in ("Wizard", "Sorcerer", "Warlock", "Druid",
                               "Cleric", "Bard")

    # ── Legs (skip when mounted — rider is sitting) ─────────────────
    if not mounted:
        draw_detailed_legs(screen, sx, hip_y, rs, leg_w, leg_h, dark_body,
                           leg_swing, breath_offset, dark_body2,
                           has_robe=has_robe, race=race)

    # ── Torso (enhanced with collar, belt, armor texture) ──────────
    draw_detailed_torso(screen, torso_x, torso_y, torso_w, torso_h,
                        torso_color, rs, char_class=char_class,
                        armored=armored)

    # ── Arms (enhanced with hands) ─────────────────────────────────
    arm_color = prof_arms if prof_arms else skin
    l_arm_y = arm_top + arm_swing
    r_arm_y = arm_top - arm_swing
    if fleeing:
        draw_detailed_arm(screen, la_x, torso_y - rs, arm_w, arm_h // 2,
                          arm_color, rs, skin_color=skin)
        draw_detailed_arm(screen, ra_x, torso_y - rs, arm_w, arm_h // 2,
                          arm_color, rs, skin_color=skin)
        l_arm_y = torso_y - rs
        r_arm_y = torso_y - rs
    else:
        _ra_draw_x = ra_x + _talk_arm_dx if _talking else ra_x
        draw_detailed_arm(screen, la_x, l_arm_y, arm_w, arm_h,
                          arm_color, rs, skin_color=skin)
        draw_detailed_arm(screen, _ra_draw_x, r_arm_y, arm_w, arm_h,
                          arm_color, rs, skin_color=skin)

    # ── Head (enhanced with hair, ears, nose) ──────────────────────
    entity_id = id(npc) % 10000
    facing = getattr(npc, 'facing', (0, 1))
    draw_detailed_head(screen, skin, head_x, head_y, head_r, rs, race,
                       entity_id, facing=facing, talking=_talking)

    # ── Eyes (enhanced with sclera and pupils) ─────────────────────
    draw_detailed_eyes(screen, head_x, head_y, head_r, rs,
                       facing=facing, eye_color=_EYE_COLOR)

    # ── Profession head decoration (hat/helmet) ────────────────────
    _prof_sprites.draw_profession_head(screen, profession, head_x, head_y, head_r, rs)

    # ── Hand positions (outer edge, bottom of arm) ─────────────────
    r_hand_x = ra_x + arm_w
    r_hand_y = r_arm_y + arm_h if not fleeing else torso_y - rs + arm_h // 2
    l_hand_x = la_x
    l_hand_y = l_arm_y + arm_h if not fleeing else torso_y - rs + arm_h // 2

    # ── Profession tool (hammer, fishing rod, barrel) ────────────────
    if weapon_type == 0 and _prof_sprites.get_tool_type(profession):
        _prof_sprites.draw_profession_tool(screen, profession, r_hand_x, r_hand_y, rs)

    # ── Equipment (conditional — most NPCs are civilians) ───────────
    if weapon_type == 1:
        _draw_melee(screen, draw, r_hand_x, r_hand_y, rs, npc)
    elif weapon_type == 2:
        _draw_bow(screen, draw, l_hand_x, l_hand_y, r_hand_x, r_hand_y, rs)
    elif weapon_type == 3:
        _draw_staff(screen, draw, r_hand_x, r_hand_y, rs, orb_color)

    # ── Shield (angled opposite to sword, overlapping lower arm) ──
    if armored and rs >= 2:
        sh_len = max(4, rs * 3)     # shield height
        sh_w = max(2, rs + 1)       # shield thickness for polygon
        # Anchor near middle of left arm, tilted up-left (opposite to sword)
        anchor_x = la_x + arm_w // 2 + max(1, rs // 2)
        anchor_y = l_hand_y - max(1, rs // 2)
        # Top of shield angles up and to the left
        tilt_x = max(2, int(rs * 0.9))
        top_x = anchor_x - tilt_x
        top_y = anchor_y - sh_len
        # Shield as angled polygon (4 corners with width)
        hw = max(1, sh_w // 2)
        pts = [
            (top_x - hw, top_y),
            (top_x + hw, top_y),
            (anchor_x + hw, anchor_y),
            (anchor_x - hw, anchor_y),
        ]
        draw.polygon(screen, (140, 100, 50), pts)
        draw.polygon(screen, (110, 75, 35), pts, 1)
        # Shield boss (center dot)
        if rs >= 3:
            boss_x = (top_x + anchor_x) // 2
            boss_y = (top_y + anchor_y) // 2
            draw.circle(screen, (170, 140, 70), (boss_x, boss_y),
                        max(1, rs // 4))


def _draw_melee(screen, draw, hx, hy, rs, npc):
    """Draw sword angling up-and-out from the right hand."""
    blade_len = max(3, rs * 2)
    # Blade angles diagonally: up and to the right at ~30 degrees
    tip_x = hx + max(2, int(rs * 1.2))
    tip_y = hy - blade_len
    # Blade
    draw.line(screen, (195, 200, 210), (hx, hy), (tip_x, tip_y),
              max(1, rs // 2))
    # Crossguard perpendicular to blade at hand position
    cg_len = max(2, rs)
    draw.line(screen, (160, 160, 170),
              (hx - max(1, cg_len // 3), hy - 1),
              (hx + cg_len, hy + 1), max(1, rs // 3))
    # Pommel extends opposite to blade
    if rs >= 3:
        pmx = hx - max(1, rs // 2)
        pmy = hy + max(1, rs // 2)
        draw.circle(screen, (140, 130, 110), (pmx, pmy), max(1, rs // 4))


def _draw_bow(screen, draw, l_hx, l_hy, r_hx, r_hy, rs):
    """Draw bow held in left hand with string to right hand."""
    bow_h = max(4, rs * 3)
    # Bow arc in left hand
    bow_rect = (l_hx - rs, l_hy - bow_h // 2, rs * 2, bow_h)
    draw.arc(screen, (140, 100, 50), bow_rect, -0.8, 0.8, max(1, rs // 3))
    # Bowstring from top to bottom of arc
    string_x = l_hx + max(1, rs // 2)
    draw.line(screen, (180, 170, 150),
              (string_x, l_hy - bow_h // 2 + 1),
              (string_x, l_hy + bow_h // 2 - 1), 1)
    # Arrow nocked (small line from string toward facing)
    if rs >= 3:
        draw.line(screen, (160, 140, 80),
                  (string_x, l_hy),
                  (string_x + max(2, rs), l_hy), 1)


def _draw_staff(screen, draw, hx, hy, rs, orb_color):
    """Draw staff extending from right hand upward, with orb at top."""
    staff_len = max(4, rs * 3)
    staff_top_y = hy - staff_len
    # Staff shaft from hand upward
    draw.line(screen, (120, 90, 50),
              (hx, hy), (hx, staff_top_y), max(1, rs // 3))
    # Orb at staff top
    orb_r = max(2, rs // 2 + 1)
    draw.circle(screen, orb_color, (hx, staff_top_y), orb_r)
    # Orb glow
    if rs >= 3:
        glow = pygame.Surface((orb_r * 4, orb_r * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*orb_color, 40), (orb_r * 2, orb_r * 2), orb_r * 2)
        screen.blit(glow, (hx - orb_r * 2, staff_top_y - orb_r * 2))


def _draw_death(screen, npc, sx, sy, s, anim, body_color):
    """Draw death — collapse animation then skull and crossbones."""
    t = anim.death_timer
    rs = max(1, int(s * _race_size(getattr(npc, 'race', 'human'))))
    if anim.death_done:
        _draw_skull(screen, sx, sy, rs)
        return
    tw = max(3, int(rs * 3 * (1.0 + t * 0.5)))
    th = max(2, int(rs * 3 * (1.0 - t * 0.7)))
    ty = sy - rs + int(t * rs * 2)
    alpha = max(40, int(255 * (1.0 - t * 0.6)))
    surf = pygame.Surface((tw + 4, th + 4), pygame.SRCALPHA)
    pygame.draw.rect(surf, (*body_color, alpha), (2, 2, tw, th),
                     border_radius=max(1, rs // 2))
    screen.blit(surf, (sx - tw // 2 - 2, ty - 2))


def _draw_skull(screen, sx, sy, rs):
    """Draw a small skull and crossbones icon."""
    draw = pygame.draw
    bone, dark = (210, 200, 180), (160, 150, 130)
    skull_r = max(2, rs + 1)
    bone_len, bone_w = max(3, rs * 2), max(1, rs // 3)
    draw.line(screen, bone, (sx - bone_len, sy + skull_r // 2),
              (sx + bone_len, sy - skull_r + 2), bone_w)
    draw.line(screen, bone, (sx - bone_len, sy - skull_r + 2),
              (sx + bone_len, sy + skull_r // 2), bone_w)
    knob_r = max(1, rs // 3)
    for bx, by in [(sx - bone_len, sy + skull_r // 2),
                    (sx + bone_len, sy + skull_r // 2),
                    (sx - bone_len, sy - skull_r + 2),
                    (sx + bone_len, sy - skull_r + 2)]:
        draw.circle(screen, bone, (bx, by), knob_r)
    draw.circle(screen, bone, (sx, sy - skull_r // 2), skull_r)
    draw.ellipse(screen, dark, (sx - max(2, skull_r + rs // 2) // 2, sy,
                                max(2, skull_r + rs // 2), max(1, skull_r // 2)))
    eye_r = max(1, rs // 2)
    eye_y = sy - skull_r // 2 - 1
    draw.circle(screen, (30, 25, 20), (sx - eye_r - 1, eye_y), eye_r)
    draw.circle(screen, (30, 25, 20), (sx + eye_r + 1, eye_y), eye_r)
    if rs >= 2:
        draw.polygon(screen, (40, 35, 25),
                      [(sx, sy - 1 - max(1, rs // 3)), (sx - 1, sy), (sx + 1, sy)])


# Re-export creature drawing from its own module for backward compatibility
from game.ui.creature_anim import draw_creature_body  # noqa: F401

"""Mounted entity rendering — draws mount underneath, side-profile rider on top.

Works for NPCs, players, and any entity with a `.mount` attribute.
The mount is drawn as its creature type using the creature sprite system,
and the rider is drawn in side profile (one arm, one eye) sitting on top.
"""

import pygame
from game.ui.character_anim import (
    get_anim, update_anim, _sin, _cos,
    _get_skin, _race_size, _darken, _EYE_COLOR,
    SKIN_TONES, ARMOR_TINTS,
    _ARMORED_CLASSES, _ARMORED_PROFS,
    _ARMED_MELEE_CLASSES, _ARMED_MELEE_PROFS,
    _MAGE_CLASSES, _MAGE_ORB_COLORS,
)
from game.ui.creatures.configs import CREATURE_CONFIGS
from game.ui.creatures.dispatch import draw_creature_body as _draw_creature

# Mount type → creature kind for rendering
_MOUNT_CREATURE_KIND = {
    "horse": "horse",
    "war_horse": "horse",
    "donkey": "donkey",
    "mule": "donkey",
    "camel": "horse",  # similar body shape
}

# Mount type → color
_MOUNT_COLORS = {
    "horse": (140, 100, 60),
    "war_horse": (80, 70, 65),
    "donkey": (130, 120, 110),
    "mule": (120, 105, 85),
    "camel": (190, 170, 130),
}


class _MountProxy:
    """Lightweight proxy so a Mount object can be drawn as a creature."""
    __slots__ = ('x', 'y', 'vx', 'vy', 'kind', 'color', 'cr', 'hp', 'max_hp',
                 'alive', '_anim')

    def __init__(self, mount, entity):
        self.x = entity.x
        self.y = entity.y
        self.vx = getattr(entity, 'vx', 0)
        self.vy = getattr(entity, 'vy', 0)
        mount_type = getattr(mount, 'mount_type', 'horse')
        self.kind = _MOUNT_CREATURE_KIND.get(mount_type, 'horse')
        self.color = _MOUNT_COLORS.get(mount_type, (140, 100, 60))
        self.cr = 0.5  # medium-sized
        self.hp = getattr(mount, 'health', 60)
        self.max_hp = getattr(mount, 'max_health', 60)
        self.alive = getattr(mount, 'is_alive', True)
        # Share anim state with mount object if possible
        self._anim = getattr(mount, '_anim', None)

    def sync_anim_back(self, mount):
        """Store anim state back on the mount for persistence."""
        if self._anim is not None:
            mount._anim = self._anim


def is_mounted(entity) -> bool:
    """Check if an entity is currently mounted."""
    mount = getattr(entity, 'mount', None)
    return mount is not None and getattr(mount, 'is_alive', True)


def get_rider_offset(s: int, mount_type: str = "horse") -> int:
    """Get the Y pixel offset for a rider sitting on a mount's back.

    s = scale factor (TILE_SIZE // 4).
    Returns negative value (rider drawn higher up).
    """
    rs = max(1, s)
    # Rider sits at mount's back height — torso overlaps mount body slightly
    base = max(2, int(rs * 2.2))
    # Larger mounts raise the rider more
    if mount_type in ("war_horse", "camel"):
        base = max(3, int(rs * 2.5))
    elif mount_type in ("donkey", "mule"):
        base = max(2, int(rs * 1.8))
    return -base


def draw_mounted_entity(screen, entity, sx: int, sy: int, s: int,
                        draw_rider_func=None, rider_args=()):
    """Draw a mounted entity: mount underneath, side-profile rider on top.

    draw_rider_func is ignored — we always use the side-profile rider.
    """
    mount = entity.mount
    mount_type = getattr(mount, 'mount_type', 'horse')

    # Create mount proxy for creature drawing
    proxy = _MountProxy(mount, entity)
    update_anim(proxy, getattr(entity, '_last_dt', 0.016))

    # Draw mount body at entity position
    _draw_creature(screen, proxy, sx, sy, s)

    # Sync anim state back for persistence
    proxy.sync_anim_back(mount)

    # Draw side-profile rider elevated above mount
    rider_offset = get_rider_offset(s, mount_type)
    anim = get_anim(proxy)
    bob = int(abs(_cos(anim.walk_phase)) * max(1, s // 3)) if anim.moving else 0
    rider_sy = sy + rider_offset - bob

    _draw_rider_side(screen, entity, sx, rider_sy, s, anim.moving)


def _draw_rider_side(screen, entity, sx, sy, s, mount_moving):
    """Draw rider in side profile — one arm, one eye, narrower torso.

    Looks like the rider is facing the same direction as the mount (right).
    """
    rs = max(1, s)
    draw = pygame.draw

    # Determine colors from entity type
    mode = getattr(entity, 'mode', None)
    if mode == "god":
        body_color = (200, 180, 60)
        skin = (255, 240, 180)
    elif mode == "ghost":
        body_color = (150, 170, 220)
        skin = (200, 210, 240)
    elif mode is not None:
        # Player mortal
        body_color = (60, 100, 180)
        skin = (220, 190, 160)
    else:
        # NPC
        body_color = getattr(entity, 'color', (120, 120, 120))
        race = getattr(entity, 'race', 'human')
        skin = _get_skin(race)
        char_class = getattr(entity, 'char_class', '')
        profession = getattr(entity, 'profession', '')
        if char_class in _ARMORED_CLASSES or profession in _ARMORED_PROFS:
            armor_c = ARMOR_TINTS.get(char_class, ARMOR_TINTS.get(profession, None))
            if armor_c:
                body_color = armor_c

    dark_body = _darken(body_color, 20)

    # Side-profile dimensions (narrower than front view)
    torso_w = max(2, int(rs * 1.8))  # narrower — seen from side
    torso_h = max(3, rs * 3)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs

    # ── Torso (narrow, side view) ──────────────────────────────────
    br = max(1, rs // 2)
    draw.rect(screen, body_color, (torso_x, torso_y, torso_w, torso_h),
              border_radius=br)

    # ── One arm (near side, slightly forward) ──────────────────────
    arm_w = max(1, rs)
    arm_h = max(2, int(rs * 1.5))
    arm_x = torso_x + torso_w // 4  # slightly offset from center
    arm_y = torso_y + max(1, rs // 2)
    # Arm hangs down, slight forward lean
    draw.rect(screen, skin, (arm_x, arm_y, arm_w, arm_h))
    # Hand
    draw.circle(screen, skin, (arm_x + arm_w // 2, arm_y + arm_h), max(1, rs // 2))

    # ── Head (circle, one eye visible) ─────────────────────────────
    head_r = max(2, rs + 1)
    head_x = sx
    head_y = torso_y - head_r
    draw.circle(screen, skin, (head_x, head_y), head_r)

    # One eye (facing right — toward the front of the mount)
    if rs >= 2:
        eye_r = max(1, rs // 3)
        draw.circle(screen, _EYE_COLOR, (head_x + head_r // 3, head_y - 1), eye_r)

    # ── Weapon (side view — extends forward from hand) ─────────────
    char_class = getattr(entity, 'char_class', '')
    profession = getattr(entity, 'profession', '')
    hand_x = arm_x + arm_w // 2
    hand_y = arm_y + arm_h

    if char_class in _ARMED_MELEE_CLASSES or profession in _ARMED_MELEE_PROFS:
        # Sword angling forward and up
        blade_len = max(3, rs * 2)
        tip_x = hand_x + max(2, int(rs * 1.5))
        tip_y = hand_y - blade_len
        draw.line(screen, (195, 200, 210), (hand_x, hand_y), (tip_x, tip_y),
                  max(1, rs // 2))
        # Crossguard
        cg = max(1, rs // 2)
        draw.line(screen, (160, 160, 170),
                  (hand_x - cg // 2, hand_y), (hand_x + cg, hand_y), max(1, rs // 3))
    elif char_class in _MAGE_CLASSES:
        # Staff pointing up
        staff_len = max(4, rs * 3)
        draw.line(screen, (120, 90, 50),
                  (hand_x, hand_y), (hand_x, hand_y - staff_len), max(1, rs // 3))
        orb_c = _MAGE_ORB_COLORS.get(char_class, (140, 140, 220))
        draw.circle(screen, orb_c, (hand_x, hand_y - staff_len), max(1, rs // 2 + 1))

    # ── Shield (near side, covers torso) ───────────────────────────
    if char_class in _ARMORED_CLASSES or profession in _ARMORED_PROFS:
        if rs >= 2:
            sw = max(2, rs + 1)
            sh = max(3, int(rs * 1.8))
            shield_x = torso_x - sw + 1
            shield_y = torso_y + rs // 2
            draw.rect(screen, (140, 100, 50),
                      (shield_x, shield_y, sw, sh),
                      border_radius=max(1, rs // 3))
            draw.rect(screen, (110, 75, 35),
                      (shield_x, shield_y, sw, sh), 1,
                      border_radius=max(1, rs // 3))

    # ── Crown (god mode) ──────────────────────────────────────────
    if mode == "god":
        crown_y = head_y - head_r
        for dx in [0, rs // 2]:
            draw.line(screen, (255, 215, 0),
                      (head_x + dx, crown_y),
                      (head_x + dx, crown_y - max(2, rs)), max(1, rs // 3))


def draw_mount_hp_bar(screen, mount, sx: int, sy: int, s: int):
    """Draw a small HP bar for the mount below the entity."""
    if not mount or not getattr(mount, 'is_alive', True):
        return
    hp = getattr(mount, 'health', 60)
    max_hp = getattr(mount, 'max_health', 60)
    if hp >= max_hp:
        return
    rs = max(1, s)
    bar_w = max(8, rs * 4)
    bar_h = max(1, rs // 3)
    bar_x = sx - bar_w // 2
    bar_y = sy + rs * 3  # below the mount
    pygame.draw.rect(screen, (30, 30, 30), (bar_x, bar_y, bar_w, bar_h))
    hp_w = max(1, int(bar_w * hp / max(1, max_hp)))
    hp_color = (200, 150, 50)  # amber for mount HP
    pygame.draw.rect(screen, hp_color, (bar_x, bar_y, hp_w, bar_h))

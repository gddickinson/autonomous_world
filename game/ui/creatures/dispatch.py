"""Dispatch — routes creature kinds to their template drawing functions."""

import pygame
from game.ui.character_anim import get_anim, _sin
from game.ui.creatures.configs import CREATURE_CONFIGS
from game.ui.creatures.templates_beasts import (
    draw_quadruped, draw_ungulate, draw_bear, draw_small
)
from game.ui.creatures.templates_others import (
    draw_bird, draw_serpent, draw_reptile, draw_arachnid, draw_aquatic
)
from game.ui.creatures.templates_humanoid import (
    draw_humanoid, draw_large, draw_winged, draw_ethereal
)

TEMPLATE_FUNCS = {
    "quadruped": draw_quadruped,
    "ungulate": draw_ungulate,
    "bear": draw_bear,
    "small": draw_small,
    "bird": draw_bird,
    "serpent": draw_serpent,
    "reptile": draw_reptile,
    "arachnid": draw_arachnid,
    "aquatic": draw_aquatic,
    "humanoid": draw_humanoid,
    "large": draw_large,
    "winged": draw_winged,
    "ethereal": draw_ethereal,
}


def draw_creature_body(screen, creature, sx: int, sy: int, s: int):
    """Draw a creature using its type-specific template."""
    anim = get_anim(creature)
    cr = getattr(creature, 'cr', 0.25)
    cs = max(2, int(s * (1.0 + min(1.5, cr * 0.3))))
    color = creature.color

    # Death animation (shared across all templates)
    if anim.death_timer >= 0:
        _draw_death(screen, creature, sx, sy, cs, anim, color)
        return

    kind = getattr(creature, 'kind', '')
    walk_sin = _sin(anim.walk_phase) if anim.moving else 0
    breath = int(_sin(anim.idle_phase) * 0.5)

    # Look up config and template
    cfg = CREATURE_CONFIGS.get(kind)
    if not cfg:
        _draw_fallback(screen, sx, sy, cs, color, walk_sin, breath)
        return

    template_name = cfg.get("t", "quadruped")

    # Check for pose-specific drawing (sleeping, resting, combat, etc.)
    from game.ui.creatures.creature_poses import (
        get_creature_pose, draw_quadruped_sleeping, draw_quadruped_resting,
        draw_quadruped_combat, draw_bird_perching, draw_serpent_coiled,
    )
    pose = get_creature_pose(creature)
    if pose == "sleeping" and template_name in ("quadruped", "ungulate", "bear"):
        draw_quadruped_sleeping(screen, sx, sy, cs, color, cfg)
    elif pose == "resting" and template_name in ("quadruped", "ungulate", "bear"):
        draw_quadruped_resting(screen, sx, sy, cs, color, cfg)
    elif pose == "combat" and template_name in ("quadruped", "ungulate", "bear"):
        draw_quadruped_combat(screen, sx, sy, cs, color, cfg)
    elif pose == "sleeping" and template_name == "bird":
        draw_bird_perching(screen, sx, sy, cs, color, cfg)
    elif pose == "resting" and template_name == "bird":
        draw_bird_perching(screen, sx, sy, cs, color, cfg)
    elif pose in ("sleeping", "resting") and template_name == "serpent":
        draw_serpent_coiled(screen, sx, sy, cs, color, cfg)
    elif pose in ("sleeping", "resting", "combat") and template_name == "humanoid":
        # Humanoid creatures use NPC-like poses
        from game.ui.poses import draw_lying_body, draw_combat_body, \
            draw_sitting_body
        skin = color  # humanoid creatures use body color as skin
        if pose == "sleeping":
            draw_lying_body(screen, creature, sx, sy, s, color, skin)
        elif pose == "combat":
            draw_combat_body(screen, creature, sx, sy, s, color, skin)
        else:
            draw_sitting_body(screen, creature, sx, sy, s, color, skin)
    else:
        # Default: use the walking/standing template
        func = TEMPLATE_FUNCS.get(template_name)
        if func:
            func(screen, sx, sy, cs, color, walk_sin, breath, cfg)
        else:
            _draw_fallback(screen, sx, sy, cs, color, walk_sin, breath)

    # Kind initial letter overlay
    if cs >= 4:
        if not hasattr(draw_creature_body, '_font'):
            draw_creature_body._font = pygame.font.SysFont("monospace", 9, bold=True)
        letter = draw_creature_body._font.render(
            kind[0].upper() if kind else "?", True, (255, 255, 255))
        screen.blit(letter, (sx - letter.get_width() // 2,
                             sy - letter.get_height() // 2))

    # HP bar
    if creature.hp < creature.max_hp:
        bar_w = max(8, cs * 5)
        bar_h = max(2, cs // 2)
        bar_x = sx - bar_w // 2
        bar_y = sy - cs * 3
        pygame.draw.rect(screen, (30, 30, 30), (bar_x, bar_y, bar_w, bar_h))
        hp_w = int(bar_w * creature.hp / creature.max_hp)
        hp_color = (200, 50, 50) if creature.hp < creature.max_hp * 0.3 else (50, 180, 50)
        pygame.draw.rect(screen, hp_color, (bar_x, bar_y, hp_w, bar_h))


def _draw_death(screen, creature, sx, sy, cs, anim, color):
    """Shared death collapse for all creature types."""
    t = anim.death_timer
    alpha = max(40, int(255 * (1.0 - t * 0.6)))
    squash = 1.0 - t * 0.6
    surf = pygame.Surface((cs * 6, cs * 4), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (*color, alpha),
                        (0, int(cs * (1 - squash)), cs * 6, int(cs * 3 * squash)))
    screen.blit(surf, (sx - cs * 3, sy - cs + int(t * cs)))


def _draw_fallback(screen, sx, sy, cs, color, walk_sin, breath):
    """Generic fallback for unknown creature types."""
    pygame.draw.ellipse(screen, color,
                        (sx - cs * 2, sy - cs + breath, cs * 4, cs * 2))

"""God selection screen — choose which deity to play as in god mode.

Shows the 7 gods from the pantheon with their sphere, alignment,
and personality. Each god gets different visual aura colors and
a thematic description.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT

GOD_INFO = {
    "Tharion": {
        "sphere": "War",
        "alignment": "Neutral Good",
        "color": (200, 60, 40),
        "aura": (220, 80, 50),
        "desc": "God of battle, honor, and martial glory. Favors the brave.",
        "traits": "Aggressive, Honorable",
        "bonus": "2x melee damage, armies fight harder",
    },
    "Sylvana": {
        "sphere": "Nature",
        "alignment": "Neutral Good",
        "color": (60, 180, 60),
        "aura": (80, 200, 80),
        "desc": "Goddess of forests, beasts, and the wild. Protects the natural world.",
        "traits": "Patient, Protective",
        "bonus": "Animals are friendly, nature spells cost no mana",
    },
    "Verithos": {
        "sphere": "Knowledge",
        "alignment": "True Neutral",
        "color": (80, 120, 220),
        "aura": (100, 140, 240),
        "desc": "God of wisdom, magic, and forbidden lore. Seeks all truths.",
        "traits": "Curious, Detached",
        "bonus": "All spells unlocked, double spell range",
    },
    "Morwen": {
        "sphere": "Death",
        "alignment": "Neutral Evil",
        "color": (120, 80, 160),
        "aura": (140, 100, 180),
        "desc": "Goddess of death, souls, and the inevitable end. Fair but merciless.",
        "traits": "Inevitable, Fair",
        "bonus": "Undead obey you, soul sight always active",
    },
    "Auriel": {
        "sphere": "Commerce",
        "alignment": "Neutral Good",
        "color": (220, 200, 60),
        "aura": (240, 220, 80),
        "desc": "God of trade, wealth, and prosperity. Every deal is sacred.",
        "traits": "Pragmatic, Generous",
        "bonus": "Infinite gold, NPCs always willing to trade",
    },
    "Lyria": {
        "sphere": "Love",
        "alignment": "Chaotic Good",
        "color": (220, 120, 180),
        "aura": (240, 140, 200),
        "desc": "Goddess of love, compassion, and bonds. Heals all wounds.",
        "traits": "Compassionate, Jealous",
        "bonus": "All NPCs friendly, healing spells cost no mana",
    },
    "Xaotl": {
        "sphere": "Chaos",
        "alignment": "Chaotic Neutral",
        "color": (180, 60, 220),
        "aura": (200, 80, 240),
        "desc": "God of chaos, change, and wild magic. Nothing is predictable.",
        "traits": "Unpredictable, Creative",
        "bonus": "Spells have random bonus effects, weather obeys you",
    },
}

GOD_NAMES = list(GOD_INFO.keys())


def show_god_selection(screen, clock) -> dict:
    """Show god selection screen. Returns dict with god name or None."""
    font_lg = pygame.font.SysFont("monospace", 28, bold=True)
    font_md = pygame.font.SysFont("monospace", 16, bold=True)
    font_sm = pygame.font.SysFont("monospace", 13)

    selected = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(GOD_NAMES)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(GOD_NAMES)
                elif event.key == pygame.K_RETURN:
                    return {"god_name": GOD_NAMES[selected]}

        screen.fill((15, 10, 25))

        # Title
        title = font_lg.render("CHOOSE YOUR DIVINE FORM", True, (220, 200, 140))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 20))
        sub = font_sm.render("You will walk among mortals as a god", True, (140, 130, 120))
        screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 55))

        # God list (left)
        list_x = 40
        list_y = 90
        for i, name in enumerate(GOD_NAMES):
            info = GOD_INFO[name]
            y = list_y + i * 80

            # Selection highlight
            if i == selected:
                pygame.draw.rect(screen, (30, 25, 45),
                                 (list_x - 5, y - 2, 320, 74), border_radius=4)
                pygame.draw.rect(screen, info["color"],
                                 (list_x - 5, y - 2, 320, 74), 1, border_radius=4)

            # God name with sphere icon (colored dot)
            pygame.draw.circle(screen, info["color"], (list_x + 8, y + 12), 6)
            name_color = (255, 255, 255) if i == selected else (160, 160, 170)
            name_surf = font_md.render(f"{name} — {info['sphere']}", True, name_color)
            screen.blit(name_surf, (list_x + 22, y + 2))

            # Alignment
            align_surf = font_sm.render(info["alignment"], True, (120, 120, 140))
            screen.blit(align_surf, (list_x + 22, y + 22))

            # Short desc (truncated)
            desc_short = info["desc"][:50] + ("..." if len(info["desc"]) > 50 else "")
            desc_surf = font_sm.render(desc_short, True, (100, 100, 120))
            screen.blit(desc_surf, (list_x + 22, y + 38))

            # Traits
            trait_surf = font_sm.render(info["traits"], True, (130, 130, 100))
            screen.blit(trait_surf, (list_x + 22, y + 54))

        # Detail panel (right)
        panel_x = 400
        panel_y = 90
        panel_w = SCREEN_WIDTH - panel_x - 30
        panel_h = 480
        pygame.draw.rect(screen, (20, 18, 32), (panel_x, panel_y, panel_w, panel_h),
                         border_radius=6)

        god_name = GOD_NAMES[selected]
        info = GOD_INFO[god_name]

        # God name (large, colored)
        gn_surf = font_lg.render(god_name, True, info["color"])
        screen.blit(gn_surf, (panel_x + 20, panel_y + 15))

        # Sphere
        sphere_surf = font_md.render(f"God of {info['sphere']}", True, (200, 200, 220))
        screen.blit(sphere_surf, (panel_x + 20, panel_y + 55))

        # Alignment
        screen.blit(font_sm.render(f"Alignment: {info['alignment']}", True, (160, 160, 180)),
                    (panel_x + 20, panel_y + 80))

        # Description
        screen.blit(font_sm.render("Description:", True, (180, 180, 200)),
                    (panel_x + 20, panel_y + 110))
        # Word-wrap description
        words = info["desc"].split()
        lines = []
        line = ""
        for w in words:
            test = line + " " + w if line else w
            if font_sm.size(test)[0] > panel_w - 40:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        for j, ln in enumerate(lines):
            screen.blit(font_sm.render(ln, True, (200, 200, 210)),
                        (panel_x + 20, panel_y + 128 + j * 16))

        # Traits
        trait_y = panel_y + 128 + len(lines) * 16 + 15
        screen.blit(font_sm.render(f"Traits: {info['traits']}", True, (180, 170, 130)),
                    (panel_x + 20, trait_y))

        # Divine bonus
        bonus_y = trait_y + 30
        screen.blit(font_md.render("Divine Power:", True, info["aura"]),
                    (panel_x + 20, bonus_y))
        screen.blit(font_sm.render(info["bonus"], True, (220, 220, 200)),
                    (panel_x + 20, bonus_y + 22))

        # Aura preview (glowing circle)
        aura_x = panel_x + panel_w // 2
        aura_y = bonus_y + 100
        for r in range(60, 10, -10):
            alpha = max(10, 60 - r)
            aura_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(aura_surf, (*info["aura"], alpha), (r, r), r)
            screen.blit(aura_surf, (aura_x - r, aura_y - r))
        # God symbol in center
        sym = font_lg.render(god_name[0], True, (255, 255, 255))
        screen.blit(sym, (aura_x - sym.get_width() // 2, aura_y - sym.get_height() // 2))

        # Controls
        ctrl_y = SCREEN_HEIGHT - 35
        screen.blit(font_sm.render("UP/DOWN: select    ENTER: become this god    ESC: cancel",
                                    True, (120, 120, 140)),
                    (SCREEN_WIDTH // 2 - 220, ctrl_y))

        pygame.display.flip()
        clock.tick(30)

    return None

#!/usr/bin/env python3
"""Mount & Rider Viewer — shows different rider/mount combinations.

Displays riders (NPCs and player) mounted on various creatures,
showing the legless rider sitting on the mount's back.

Controls:
  LEFT/RIGHT: cycle rider type
  UP/DOWN: cycle mount type
  SPACE: toggle walking
  Z: cycle view scale
  S: screenshot
  Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1000, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Mount & Rider Viewer")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 13)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.ui.character_anim import draw_npc_body, update_anim, get_anim
from game.ui.player_anim import draw_player_body
from game.ui.mount_render import draw_mounted_entity


# ── Mock classes ─────────────────────────────────────────────────────────

class MockMount:
    def __init__(self, mount_type="horse"):
        self.mount_type = mount_type
        self.health = 60
        self.max_health = 60
        self.is_alive = True
        self._anim = None


class MockNPC:
    def __init__(self, name, profession, char_class, race, color):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.name = name
        self.profession = profession
        self.char_class = char_class
        self.race = race
        self.color = color
        self.alive = True
        self.state = "idle"
        self.current_action = ""
        self.facing = (0, 1)
        self.consciousness = 0
        self._anim = None
        self._last_dt = 0.016
        self.mount = None


class MockPlayer:
    def __init__(self, mode="mortal"):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.mode = mode
        self.alive = True
        self.facing = (0, 1)
        self.attack_timer = 0.0
        self._anim = None
        self._last_dt = 0.016
        self.mount = None


# ── Presets ──────────────────────────────────────────────────────────────

RIDERS = [
    ("Player (mortal)", "player", "mortal"),
    ("Player (god)",    "player", "god"),
    ("Human Fighter",   "npc", ("Fighter Guard", "Guard", "Fighter", "human", (180, 60, 60))),
    ("Elf Ranger",      "npc", ("Elf Ranger", "Ranger", "Ranger", "elf", (80, 140, 80))),
    ("Dwarf Paladin",   "npc", ("Dwarf Paladin", "Knight", "Paladin", "dwarf", (180, 160, 60))),
    ("Halfling Rogue",  "npc", ("Halfling Rogue", "Thief", "Rogue", "halfling", (100, 100, 100))),
    ("Orc Barbarian",   "npc", ("Orc Barbarian", "Merc", "Barbarian", "orc", (80, 110, 70))),
    ("Gnome Wizard",    "npc", ("Gnome Wizard", "Sage", "Wizard", "gnome", (60, 60, 180))),
]

MOUNTS = [
    "horse", "war_horse", "donkey", "mule", "camel",
]

VIEW_SCALES = [
    ("Strategy (16px)", 4),
    ("Adventure (32px)", 8),
    ("Detail (64px)", 16),
]


def _make_rider(preset):
    _, kind, data = preset
    if kind == "player":
        return MockPlayer(data)
    else:
        return MockNPC(*data)


def _rider_draw_func(preset):
    _, kind, _ = preset
    if kind == "player":
        return draw_player_body
    else:
        return draw_npc_body


def main():
    rider_idx = 0
    mount_idx = 0
    view_idx = 1  # start at adventure scale
    walking = False
    walk_time = 0.0

    # Persistent rider+mount objects
    rider = _make_rider(RIDERS[rider_idx])
    rider.mount = MockMount(MOUNTS[mount_idx])

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    rider_idx = (rider_idx - 1) % len(RIDERS)
                    rider = _make_rider(RIDERS[rider_idx])
                    rider.mount = MockMount(MOUNTS[mount_idx])
                elif event.key == pygame.K_RIGHT:
                    rider_idx = (rider_idx + 1) % len(RIDERS)
                    rider = _make_rider(RIDERS[rider_idx])
                    rider.mount = MockMount(MOUNTS[mount_idx])
                elif event.key == pygame.K_UP:
                    mount_idx = (mount_idx - 1) % len(MOUNTS)
                    rider.mount = MockMount(MOUNTS[mount_idx])
                elif event.key == pygame.K_DOWN:
                    mount_idx = (mount_idx + 1) % len(MOUNTS)
                    rider.mount = MockMount(MOUNTS[mount_idx])
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                elif event.key == pygame.K_z:
                    view_idx = (view_idx + 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_mount_viewer.png")

        # Simulate movement
        if walking:
            walk_time += dt
            rider.x = math.sin(walk_time * 2) * 0.4
            rider.y = math.cos(walk_time * 2) * 0.4
        rider._last_dt = dt

        # ── Render ──────────────────────────────────────────────────
        screen.fill((30, 30, 40))
        _draw_grid(screen)

        view_name, scale = VIEW_SCALES[view_idx]
        draw_func = _rider_draw_func(RIDERS[rider_idx])

        # Main mounted view (center)
        cx, cy = SCREEN_W // 2, SCREEN_H // 3 + 20
        draw_mounted_entity(screen, rider, cx, cy, scale, draw_func)

        # Comparison: unmounted rider next to mounted
        comp_y = cy
        # Unmounted (left)
        unmounted = _make_rider(RIDERS[rider_idx])
        unmounted._last_dt = dt
        if walking:
            unmounted.x = math.sin(walk_time * 2 + 1) * 0.3
        update_anim(unmounted, dt)
        uf = _rider_draw_func(RIDERS[rider_idx])
        uf(screen, unmounted, cx - scale * 12, comp_y, scale)
        screen.blit(font.render("On foot", True, (160, 160, 180)),
                    (cx - scale * 12 - 20, comp_y + scale * 5))

        screen.blit(font.render("Mounted", True, (160, 160, 180)),
                    (cx - 25, comp_y + scale * 5))

        # ── Bottom panel: all mounts with current rider ─────────────
        panel_y = SCREEN_H - 180
        _draw_panel_bg(screen, 0, panel_y - 15, SCREEN_W, 195)
        screen.blit(font.render("All mount types:", True, (180, 180, 200)),
                    (20, panel_y - 10))

        spacing = SCREEN_W // (len(MOUNTS) + 1)
        for mi, mt in enumerate(MOUNTS):
            mx = spacing * (mi + 1)
            my = panel_y + 60

            r = _make_rider(RIDERS[rider_idx])
            r.mount = MockMount(mt)
            r._last_dt = dt
            if walking:
                r.x = math.sin(walk_time * 2 + mi * 0.7) * 0.3
            draw_mounted_entity(screen, r, mx, my, scale, draw_func)

            # Label
            label_c = (255, 220, 100) if mi == mount_idx else (140, 140, 160)
            screen.blit(font.render(mt.replace("_", " "), True, label_c),
                        (mx - len(mt) * 3, my + scale * 5))

        # ── All scales panel (right side) ───────────────────────────
        for vi, (vn, vs) in enumerate(VIEW_SCALES):
            vx = SCREEN_W - 120
            vy = 80 + vi * 90
            r = _make_rider(RIDERS[rider_idx])
            r.mount = MockMount(MOUNTS[mount_idx])
            r._last_dt = dt
            if walking:
                r.x = math.sin(walk_time * 2 + vi) * 0.2
            draw_mounted_entity(screen, r, vx, vy, vs, draw_func)
            screen.blit(font.render(vn, True, (120, 120, 140)),
                        (vx - 55, vy + vs * 4))

        # ── HUD ─────────────────────────────────────────────────────
        rider_name = RIDERS[rider_idx][0]
        mount_name = MOUNTS[mount_idx].replace("_", " ")
        title = font_lg.render(f"{rider_name} on {mount_name}", True, (255, 255, 255))
        screen.blit(title, (20, 15))

        info = f"View: {view_name} | Walk: {'ON' if walking else 'OFF'}"
        screen.blit(font.render(info, True, (160, 160, 180)), (20, 40))

        controls = [
            "LEFT/RIGHT: rider", "UP/DOWN: mount", "SPACE: walk",
            "Z: view scale", "S: screenshot",
        ]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (110, 110, 130)),
                        (SCREEN_W - 170, 15 + i * 15))

        pygame.display.flip()

    pygame.quit()


def _draw_grid(screen):
    for x in range(0, SCREEN_W, 20):
        pygame.draw.line(screen, (40, 40, 50), (x, 0), (x, SCREEN_H))
    for y in range(0, SCREEN_H, 20):
        pygame.draw.line(screen, (40, 40, 50), (0, y), (SCREEN_W, y))


def _draw_panel_bg(screen, x, y, w, h):
    pygame.draw.rect(screen, (25, 25, 35), (x, y, w, h))
    pygame.draw.line(screen, (50, 50, 60), (x, y), (x + w, y))


if __name__ == "__main__":
    main()

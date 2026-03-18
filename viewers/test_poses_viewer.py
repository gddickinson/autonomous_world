#!/usr/bin/env python3
"""Entity Pose Viewer — all action poses for NPCs, player, creatures.

Shows standing, sitting, lying, kneeling, working, combat, fishing,
alert, and dead poses at multiple scales.

Controls:
  LEFT/RIGHT: cycle pose
  UP/DOWN: cycle view scale
  TAB: cycle entity type (NPC classes)
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1100, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Entity Pose Viewer — All Actions")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 12)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.ui.character_anim import draw_npc_body, update_anim, get_anim
from game.ui.poses import (
    draw_lying_body, draw_sitting_body, draw_kneeling_body,
    draw_working_body, draw_combat_body, draw_fishing_body,
    draw_alert_body, draw_status_overlay, get_pose,
)
from game.ui.character_anim import _get_skin


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
        self.body = None


NPC_TYPES = [
    ("Human Fighter", "Guard",    "Fighter",  "human",     (180, 60, 60)),
    ("Elf Wizard",    "Sage",     "Wizard",   "elf",       (60, 60, 180)),
    ("Dwarf Paladin", "Knight",   "Paladin",  "dwarf",     (180, 160, 60)),
    ("Human Farmer",  "Farmer",   "Commoner", "human",     (140, 120, 80)),
    ("Orc Soldier",   "Soldier",  "Fighter",  "orc",       (80, 110, 70)),
]

POSES = [
    ("Standing (idle)",      "idle",     ""),
    ("Walking",              "walking",  ""),
    ("Sleeping",             "sleeping", "sleeping"),
    ("Sitting (talking)",    "idle",     "talking"),
    ("Kneeling (praying)",   "idle",     "praying"),
    ("Kneeling (mining)",    "idle",     "mining"),
    ("Working (chopping)",   "idle",     "chopping"),
    ("Working (smithing)",   "idle",     "smithing"),
    ("Combat (fighting)",    "idle",     "fighting"),
    ("Fishing",              "idle",     "fishing"),
    ("Guard (alert)",        "idle",     "guarding"),
    ("Collapsed",            "idle",     "collapsed_exhaustion"),
    ("Fleeing",              "fleeing",  "fleeing"),
    ("Dead",                 "dead",     ""),
]

VIEW_SCALES = [("Small (4)", 4), ("Medium (8)", 8), ("Large (16)", 16)]


def main():
    pose_idx = 0
    view_idx = 1
    npc_idx = 0
    walk_time = 0.0

    # Persistent NPC objects so death animation can complete
    def _make_all_npcs():
        """Create persistent NPCs for all pose × npc_type combos."""
        main = {}
        strip = {}
        types = {}
        for ni, nd in enumerate(NPC_TYPES):
            for pi, (_, pstate, paction) in enumerate(POSES):
                n = MockNPC(*nd)
                n.state = pstate
                n.current_action = paction
                if pstate == "dead":
                    n.alive = False
                strip[(ni, pi)] = n
            main[ni] = {pi: MockNPC(*nd) for pi in range(len(POSES))}
            types[ni] = {}
        return main, strip, types

    main_npcs, strip_npcs, type_npcs = _make_all_npcs()
    prev_npc_idx = npc_idx

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        walk_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    pose_idx = (pose_idx - 1) % len(POSES)
                elif event.key == pygame.K_RIGHT:
                    pose_idx = (pose_idx + 1) % len(POSES)
                elif event.key == pygame.K_UP:
                    view_idx = (view_idx - 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_DOWN:
                    view_idx = (view_idx + 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_TAB:
                    npc_idx = (npc_idx + 1) % len(NPC_TYPES)
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_poses.png")

        screen.fill((30, 30, 40))

        pose_name, state, action = POSES[pose_idx]
        view_name, scale = VIEW_SCALES[view_idx]
        npc_data = NPC_TYPES[npc_idx]

        # Title
        title = font_lg.render(f"{npc_data[0]} — {pose_name} | {view_name}",
                                True, (255, 255, 255))
        screen.blit(title, (20, 15))

        # Rebuild persistent NPCs if NPC type changed
        if npc_idx != prev_npc_idx:
            main_npcs, strip_npcs, type_npcs = _make_all_npcs()
            prev_npc_idx = npc_idx

        # Main display (persistent)
        cx, cy = SCREEN_W // 2, SCREEN_H // 3
        if pose_idx not in main_npcs[npc_idx]:
            main_npcs[npc_idx][pose_idx] = MockNPC(*npc_data)
        npc = main_npcs[npc_idx][pose_idx]
        npc.state = state
        npc.current_action = action
        if state == "dead":
            npc.alive = False
        if state == "walking":
            npc.x = math.sin(walk_time * 2) * 0.3
            npc.y = math.cos(walk_time * 2) * 0.3
        update_anim(npc, dt)
        draw_npc_body(screen, npc, cx, cy, scale)

        # ── All poses strip (persistent objects) ─────────────────────
        panel_y = SCREEN_H // 2 + 40
        pygame.draw.rect(screen, (25, 25, 35), (0, panel_y - 10, SCREEN_W, SCREEN_H - panel_y + 10))
        pygame.draw.line(screen, (50, 50, 60), (0, panel_y - 10), (SCREEN_W, panel_y - 10))
        screen.blit(font.render("All poses:", True, (180, 180, 200)), (10, panel_y - 5))

        spacing = SCREEN_W // (len(POSES) + 1)
        strip_scale = min(scale, 8)
        for pi, (pname, pstate, paction) in enumerate(POSES):
            px = spacing * (pi + 1)
            py_s = panel_y + 70

            n = strip_npcs[(npc_idx, pi)]
            n.state = pstate
            n.current_action = paction
            if pstate == "dead":
                n.alive = False
            if pstate == "walking":
                n.x = math.sin(walk_time * 2 + pi) * 0.2
            update_anim(n, dt)
            draw_npc_body(screen, n, px, py_s, strip_scale)

            lbl_c = (255, 220, 100) if pi == pose_idx else (120, 120, 140)
            short = pname.split("(")[0].strip()[:8]
            screen.blit(font.render(short, True, lbl_c),
                        (px - len(short) * 3, py_s + strip_scale * 5))

        # ── All NPC types in current pose (persistent) ───────────────
        type_y = panel_y + 160
        screen.blit(font.render("All NPC types in this pose:", True, (180, 180, 200)),
                    (10, type_y - 5))
        for ni, nd in enumerate(NPC_TYPES):
            nx = 100 + ni * 180
            if pose_idx not in type_npcs.get(ni, {}):
                if ni not in type_npcs:
                    type_npcs[ni] = {}
                n = MockNPC(*nd)
                n.state = state
                n.current_action = action
                if state == "dead":
                    n.alive = False
                type_npcs[ni][pose_idx] = n
            n = type_npcs[ni][pose_idx]
            n.state = state
            n.current_action = action
            if state == "dead":
                n.alive = False
            if state == "walking":
                n.x = math.sin(walk_time * 2 + ni) * 0.2
            update_anim(n, dt)
            draw_npc_body(screen, n, nx, type_y + 50, scale)
            lbl_c = (255, 220, 100) if ni == npc_idx else (120, 120, 140)
            screen.blit(font.render(nd[0][:12], True, lbl_c),
                        (nx - 35, type_y + 50 + scale * 5))

        # Controls
        controls = ["LEFT/RIGHT: pose", "UP/DOWN: scale", "TAB: NPC type", "S: screenshot"]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (110, 110, 130)),
                        (SCREEN_W - 180, 15 + i * 14))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()

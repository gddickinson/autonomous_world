"""Graphics Phase 2 Test — verify enhanced character/NPC sprites.

Starts a HeadlessGame, captures screenshots at different zoom levels
showing NPCs, creatures, and the player with the new detailed rendering.
Runs simulation ticks to verify no crashes.

Output: viewers/graphics_test_output/phase2_*.png
"""

import os
import sys
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "viewers", "graphics_test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_screenshot(screen, name):
    """Save a screenshot to the output directory."""
    import pygame
    path = os.path.join(OUTPUT_DIR, name)
    pygame.image.save(screen, path)
    print(f"  Saved: {path}")
    return path


def render_npc_showcase():
    """Render a grid of NPCs with different races and professions."""
    import pygame
    pygame.init()
    from game.ui.character_anim import draw_npc_body, get_anim, AnimState

    W, H = 600, 500
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((40, 45, 55))

    font = pygame.font.SysFont("monospace", 10)
    title = font.render("Phase 2: Enhanced NPC Sprites (32px scale)", True,
                        (255, 255, 200))
    surf.blit(title, (10, 5))

    # Create mock NPCs with different races, classes, and professions
    races = ["human", "elf", "dwarf", "halfling", "half-orc",
             "gnome", "tiefling", "orc", "dragonborn", "goblin"]
    classes = ["Fighter", "Wizard", "Ranger", "Rogue", "Cleric",
               "Paladin", "Barbarian", "Sorcerer", "Druid", "Bard"]
    professions = ["guard", "farmer", "blacksmith", "merchant", "fisherman",
                   "priest", "scholar", "innkeeper", "soldier", "knight"]
    colors = [
        (120, 80, 60), (60, 100, 160), (100, 130, 80), (80, 70, 90),
        (180, 160, 100), (150, 120, 90), (70, 80, 120), (140, 100, 70),
        (100, 110, 130), (90, 80, 60),
    ]

    class MockNPC:
        def __init__(self, race, char_class, profession, color, idx):
            self.race = race
            self.char_class = char_class
            self.profession = profession
            self.color = color
            self.x = float(idx * 10)
            self.y = 100.0
            self.alive = True
            self.state = "idle"
            self.current_action = ""
            self.facing = (0, 1)
            self.hp = 50
            self.max_hp = 50
            self._anim = None

    # Scale factor s=8 simulates 32px tiles (TILE_SIZE=32, s=32//4=8)
    s = 8
    col_w = 58
    row_h = 70
    y_start = 30

    for idx, (race, cls, prof, clr) in enumerate(
            zip(races, classes, professions, colors)):
        col = idx % 5
        row = idx // 5
        npc = MockNPC(race, cls, prof, clr, idx)
        anim = get_anim(npc)
        # Vary walk phase for variety
        anim.walk_phase = idx * 0.7
        anim.idle_phase = idx * 0.5

        cx = 40 + col * col_w
        cy = y_start + 40 + row * row_h
        draw_npc_body(surf, npc, cx, cy, s)

        # Label
        label = font.render(f"{race[:6]}", True, (180, 180, 180))
        surf.blit(label, (cx - label.get_width() // 2, cy + 30))
        label2 = font.render(f"{cls[:6]}", True, (150, 150, 200))
        surf.blit(label2, (cx - label2.get_width() // 2, cy + 40))

    # Second batch: walking NPCs at different phases
    y_base = y_start + 180
    subtitle = font.render("Walking animation phases:", True, (200, 200, 180))
    surf.blit(subtitle, (10, y_base - 15))

    for i in range(8):
        npc = MockNPC("human", "Fighter", "guard", (100, 110, 140), 100 + i)
        anim = get_anim(npc)
        anim.walk_phase = i * 0.785  # 0 to 2*pi in 8 steps
        anim.moving = True
        cx = 40 + i * col_w
        draw_npc_body(surf, npc, cx, y_base + 30, s)

    # Third batch: 16px scale (strategy view)
    y_base2 = y_base + 90
    subtitle2 = font.render("Strategy view (16px, s=4):", True, (200, 200, 180))
    surf.blit(subtitle2, (10, y_base2 - 15))

    s_small = 4
    for idx, (race, cls, prof, clr) in enumerate(
            zip(races, classes, professions, colors)):
        npc = MockNPC(race, cls, prof, clr, idx)
        anim = get_anim(npc)
        anim.idle_phase = idx * 0.3
        cx = 25 + idx * 35
        draw_npc_body(surf, npc, cx, y_base2 + 25, s_small)
        label = font.render(race[:4], True, (160, 160, 160))
        surf.blit(label, (cx - label.get_width() // 2, y_base2 + 40))

    # Talking NPCs
    y_base3 = y_base2 + 70
    subtitle3 = font.render("Talking NPCs:", True, (200, 200, 180))
    surf.blit(subtitle3, (10, y_base3 - 15))

    for i in range(5):
        npc = MockNPC(races[i], classes[i], professions[i], colors[i], 200+i)
        npc.state = "talking"
        anim = get_anim(npc)
        anim.idle_phase = i * 1.2
        cx = 40 + i * col_w
        draw_npc_body(surf, npc, cx, y_base3 + 30, s)

    return save_screenshot(surf, "phase2_npc_showcase.png")


def render_creature_showcase():
    """Render creatures with the enhanced beast templates."""
    import pygame
    pygame.init()
    from game.ui.creatures.dispatch import draw_creature_body

    W, H = 500, 350
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((35, 50, 35))

    font = pygame.font.SysFont("monospace", 10)
    title = font.render("Phase 2: Enhanced Creature Sprites", True,
                        (255, 255, 200))
    surf.blit(title, (10, 5))

    creature_kinds = [
        "wolf", "bear", "deer", "rabbit", "boar",
        "hawk", "owl", "chicken", "fox", "cow",
        "goblin", "orc", "skeleton", "bandit", "ogre",
    ]

    creature_colors = {
        "wolf": (120, 120, 120), "bear": (100, 70, 40), "deer": (160, 130, 80),
        "rabbit": (180, 160, 130), "boar": (100, 80, 60), "hawk": (130, 100, 60),
        "owl": (140, 120, 90), "chicken": (200, 180, 140), "fox": (180, 100, 40),
        "cow": (160, 140, 110), "goblin": (100, 130, 70), "orc": (110, 130, 80),
        "skeleton": (200, 195, 180), "bandit": (100, 90, 80), "ogre": (130, 110, 80),
    }

    class MockCreature:
        def __init__(self, kind, x, y):
            self.kind = kind
            self.x = x
            self.y = y
            self.hp = 50
            self.max_hp = 50
            self.alive = True
            self.state = ""
            self.color = creature_colors.get(kind, (120, 120, 120))
            self.cr = 0.5
            self._anim = None

    s = 6  # ~24px tiles
    col_w = 65
    row_h = 70
    for idx, kind in enumerate(creature_kinds):
        col = idx % 5
        row = idx // 5
        cx = 45 + col * col_w
        cy = 50 + row * row_h
        c = MockCreature(kind, float(idx * 5), float(idx * 3))
        try:
            draw_creature_body(surf, c, cx, cy, s)
        except Exception as e:
            print(f"  Warning: {kind} draw failed: {e}")
        label = font.render(kind, True, (180, 180, 180))
        surf.blit(label, (cx - label.get_width() // 2, cy + 28))

    return save_screenshot(surf, "phase2_creature_showcase.png")


def render_player_showcase():
    """Render the player character with enhanced detail."""
    import pygame
    pygame.init()
    from game.ui.player_anim import draw_player_body, get_anim

    W, H = 400, 200
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((30, 30, 50))

    font = pygame.font.SysFont("monospace", 10)
    title = font.render("Phase 2: Enhanced Player Sprites", True,
                        (255, 255, 200))
    surf.blit(title, (10, 5))

    class MockPlayer:
        def __init__(self, mode):
            self.x = 100.0
            self.y = 100.0
            self.mode = mode
            self.race = "human"
            self.char_class = "Fighter"
            self.facing = (0, 1)
            self.alive = True
            self.state = "idle"
            self.current_action = ""
            self.hp = 100
            self.max_hp = 100
            self.attack_timer = 0
            self._anim = None
            self._last_dt = 0.016
            self._disguise = None
            self.god = (mode == "god")

    modes = ["mortal", "god"]
    for i, mode in enumerate(modes):
        p = MockPlayer(mode)
        anim = get_anim(p)
        anim.idle_phase = i * 1.5
        cx = 80 + i * 120
        cy = 80
        draw_player_body(surf, p, cx, cy, 8)
        label = font.render(mode, True, (200, 200, 200))
        surf.blit(label, (cx - label.get_width() // 2, cy + 40))

    # Walking player
    p_walk = MockPlayer("mortal")
    anim = get_anim(p_walk)
    anim.walk_phase = 2.0
    anim.moving = True
    draw_player_body(surf, p_walk, 320, 80, 8)
    label = font.render("walking", True, (200, 200, 200))
    surf.blit(label, (305, 120))

    return save_screenshot(surf, "phase2_player_showcase.png")


def run_headless_gameplay():
    """Run headless game ticks to verify no crashes with new rendering."""
    import pygame
    pygame.init()
    try:
        from game.ui.screenshot import HeadlessGame
        print("  Creating HeadlessGame (use_chunked=True, seed=42)...")
        hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                          use_chunked=True)
        print(f"  World created. Spawn: {hg.world.spawn_point}")
        print(f"  NPCs: {len(hg.world_mgr.npcs)}")
        print(f"  Creatures: {len(hg.world_mgr.creatures)}")

        # Run 100 ticks
        print("  Running 100 simulation ticks...")
        hg.tick(100)
        print("  100 ticks completed without crash.")

        # Capture gameplay
        path = hg.capture("gameplay", suffix="phase2_gameplay")
        print(f"  Saved gameplay: {path}")

        # Find a settlement and capture there
        if hg.world.structures:
            s = hg.world.structures[0]
            hg.move_player(float(s.x), float(s.y))
            hg.tick(5)
            path2 = hg.capture("gameplay", suffix="phase2_settlement")
            print(f"  Saved settlement: {path2}")

        return True
    except Exception as e:
        print(f"  HeadlessGame error: {e}")
        traceback.print_exc()
        return False


def main():
    print("=== Graphics Phase 2 Test: Enhanced Character Sprites ===")
    print()
    results = {}

    print("1. NPC Showcase (races, classes, animation phases)...")
    try:
        results["npc"] = render_npc_showcase()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["npc"] = None

    print("2. Creature Showcase (beasts, humanoids, birds)...")
    try:
        results["creature"] = render_creature_showcase()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["creature"] = None

    print("3. Player Showcase (mortal, god, walking)...")
    try:
        results["player"] = render_player_showcase()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["player"] = None

    print("4. Headless Gameplay (100 ticks, no-crash verification)...")
    results["gameplay"] = run_headless_gameplay()

    print()
    print("=== Results ===")
    for key, val in results.items():
        status = "OK" if val else "FAILED"
        print(f"  {key}: {status}")
    print(f"\nOutput dir: {OUTPUT_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()

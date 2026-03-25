"""Tutorial Island — interactive step-by-step tutorial on the test island.

When a player spawns on the test island, this triggers a guided tutorial
sequence with specific completion conditions per step. Each step shows
instructions at the top of the screen and highlights the relevant key.

Steps:
  1. Move with WASD (walk 5 tiles)
  2. Open inventory with I
  3. Attack with Space (spawn practice dummy)
  4. Talk to NPCs with E (spawn tutorial NPC)
  5. Open map with F
  6. Craft with U
  7. Ready — find the boat to the mainland
"""

import math
import time
from typing import Optional, List

import pygame

from game.settings import SCREEN_WIDTH


# ---------------------------------------------------------------------------
# Step Definitions
# ---------------------------------------------------------------------------

ISLAND_STEPS = [
    {
        "id": "move",
        "title": "Movement",
        "text": "Move with WASD",
        "hint": "Walk at least 5 tiles from your starting position.",
        "key_highlight": "WASD",
        "tiles_needed": 5,
    },
    {
        "id": "inventory",
        "title": "Inventory",
        "text": "Open your inventory with I",
        "hint": "Press I to see your items.",
        "key_highlight": "I",
    },
    {
        "id": "attack",
        "title": "Combat",
        "text": "Attack with Space",
        "hint": "Hit the practice dummy with Space!",
        "key_highlight": "SPACE",
        "spawn": "dummy",
    },
    {
        "id": "talk",
        "title": "Talk to NPCs",
        "text": "Talk to NPCs with E",
        "hint": "Walk up to the tutorial guide and press E.",
        "key_highlight": "E",
        "spawn": "tutorial_npc",
    },
    {
        "id": "map",
        "title": "Map",
        "text": "Open the map with F",
        "hint": "Press F to see the world map.",
        "key_highlight": "F",
    },
    {
        "id": "craft",
        "title": "Crafting",
        "text": "Open crafting with U",
        "hint": "Press U to see the crafting menu.",
        "key_highlight": "U",
    },
    {
        "id": "ready",
        "title": "Ready!",
        "text": "You're ready! Find the boat to the mainland.",
        "hint": "Head to the dock at the edge of the island.",
        "key_highlight": None,
        "auto_complete_secs": 10,
    },
]


# ---------------------------------------------------------------------------
# Practice Dummy (minimal entity for attack target)
# ---------------------------------------------------------------------------

class PracticeDummy:
    """A stationary target that takes damage but doesn't fight back."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.hp = 50
        self.max_hp = 50
        self.alive = True
        self.name = "Practice Dummy"
        self.kind = "dummy"
        self.color = (180, 140, 80)
        self.damage = 0
        self.speed = 0
        self.passive = True
        self.armor_class = 5
        self.xp_value = 0
        self.state = "idle"
        self._hit = False

    def take_damage(self, amount: int):
        self._hit = True
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0


# ---------------------------------------------------------------------------
# Tutorial NPC (minimal for conversation target)
# ---------------------------------------------------------------------------

class TutorialGuide:
    """A friendly NPC that exists to be talked to during the tutorial."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.hp = 100
        self.max_hp = 100
        self.alive = True
        self.name = "Tutorial Guide"
        self.profession = "Guide"
        self.char_class = ""
        self.race = "human"
        self.color = (100, 180, 100)
        self.level = 1
        self.title = "Guide"
        self.state = "idle"
        self.facing = (0, 1)
        self.dialog_text = (
            "Welcome to the island! Complete the tutorial to learn "
            "the basics. When you're ready, take the boat south to "
            "reach the mainland."
        )


# ---------------------------------------------------------------------------
# Completion Checkers
# ---------------------------------------------------------------------------

def _check_move(tut, game) -> bool:
    dx = game.player.x - tut.start_pos[0]
    dy = game.player.y - tut.start_pos[1]
    return math.hypot(dx, dy) >= 5.0


def _check_inventory(tut, game) -> bool:
    return getattr(game.ui, 'show_inventory', False) or tut._inventory_opened


def _check_attack(tut, game) -> bool:
    if tut._dummy and tut._dummy._hit:
        return True
    # Also check if combat system engaged
    return getattr(game.combat, 'active', False) or tut._attack_done


def _check_talk(tut, game) -> bool:
    return getattr(game.ui, 'dialog_active', False) or tut._talked


def _check_map(tut, game) -> bool:
    return getattr(game.ui, 'show_map', False) or tut._map_opened


def _check_craft(tut, game) -> bool:
    return getattr(game.ui, 'show_crafting', False) or tut._craft_opened


def _check_ready(tut, game) -> bool:
    elapsed = time.time() - tut._step_start_time
    auto = ISLAND_STEPS[tut.current_step].get("auto_complete_secs", 0)
    if auto and elapsed >= auto:
        return True
    # Also complete if player moves far enough (heading to boat)
    dx = game.player.x - tut.start_pos[0]
    dy = game.player.y - tut.start_pos[1]
    return math.hypot(dx, dy) >= 30.0


_CHECKERS = [
    _check_move,
    _check_inventory,
    _check_attack,
    _check_talk,
    _check_map,
    _check_craft,
    _check_ready,
]


# ---------------------------------------------------------------------------
# Key Highlight Colors
# ---------------------------------------------------------------------------

_KEY_COLORS = {
    "WASD":  (80, 200, 80),
    "I":     (200, 180, 80),
    "SPACE": (200, 80, 80),
    "E":     (80, 180, 200),
    "F":     (180, 80, 200),
    "U":     (200, 140, 80),
}


# ---------------------------------------------------------------------------
# Island Tutorial System
# ---------------------------------------------------------------------------

class IslandTutorial:
    """Interactive tutorial triggered on the test island.

    Manages step progression, entity spawning, key highlighting,
    and overlay rendering.
    """

    def __init__(self, player):
        self.player = player
        self.start_pos = (player.x, player.y)
        self.current_step = 0
        self.total_steps = len(ISLAND_STEPS)
        self.active = True
        self.completed = False

        # Tracking flags
        self._inventory_opened = False
        self._attack_done = False
        self._talked = False
        self._map_opened = False
        self._craft_opened = False

        # Spawned entities
        self._dummy: Optional[PracticeDummy] = None
        self._guide: Optional[TutorialGuide] = None
        self._spawned_for_step = set()

        # Timers
        self._pulse_timer = 0.0
        self._completion_flash = 0.0
        self._step_start_time = time.time()

    def handle_event(self, event):
        """Track key presses for step completion."""
        if not self.active:
            return
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_i:
            self._inventory_opened = True
        elif event.key == pygame.K_SPACE:
            self._attack_done = True
        elif event.key == pygame.K_e:
            self._talked = True
        elif event.key == pygame.K_f:
            self._map_opened = True
        elif event.key == pygame.K_u:
            self._craft_opened = True
        elif event.key == pygame.K_F7:
            self.skip()

    def update(self, dt: float, game):
        """Check step completion and spawn entities as needed."""
        if not self.active:
            return

        self._pulse_timer += dt
        if self._completion_flash > 0:
            self._completion_flash -= dt

        if self.current_step >= self.total_steps:
            self._finish(game)
            return

        # Spawn entities for current step if needed
        step = ISLAND_STEPS[self.current_step]
        spawn_type = step.get("spawn")
        if spawn_type and spawn_type not in self._spawned_for_step:
            self._spawn_entity(spawn_type, game)

        # Check completion
        checker = _CHECKERS[self.current_step]
        if checker(self, game):
            self._advance_step(game)

    def get_spawned_entities(self) -> list:
        """Return spawned tutorial entities for the game to track."""
        entities = []
        if self._dummy and self._dummy.alive:
            entities.append(self._dummy)
        if self._guide:
            entities.append(self._guide)
        return entities

    def draw(self, screen, font_md, font_sm=None):
        """Draw the tutorial overlay at the top of the screen."""
        if not self.active or self.current_step >= self.total_steps:
            return

        step = ISLAND_STEPS[self.current_step]
        sm = font_sm or font_md

        # Title and instruction
        step_label = f"Tutorial {self.current_step + 1}/{self.total_steps}"
        instruction = step["text"]
        hint = step.get("hint", "")
        key = step.get("key_highlight")

        label_surf = font_md.render(step_label, True, (255, 220, 100))
        instr_surf = font_md.render(instruction, True, (240, 240, 250))

        # Box sizing
        text_w = max(label_surf.get_width(), instr_surf.get_width())
        box_w = text_w + 50
        box_h = 56
        if hint:
            hint_surf = sm.render(hint, True, (170, 170, 190))
            box_h += hint_surf.get_height() + 4
            box_w = max(box_w, hint_surf.get_width() + 50)
        else:
            hint_surf = None
        if key:
            box_h += 20  # room for key highlight

        box_w = min(box_w, SCREEN_WIDTH - 20)
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = 8

        # Background
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill((10, 20, 40, 220))
        screen.blit(bg, (box_x, box_y))

        # Pulsing border
        pulse = (math.sin(self._pulse_timer * 3.0) + 1.0) / 2.0
        border_a = int(100 + 100 * pulse)
        border_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (60, 150, 230, border_a),
                         (0, 0, box_w, box_h), 2, border_radius=4)
        screen.blit(border_surf, (box_x, box_y))

        # Completion flash
        if self._completion_flash > 0:
            flash_a = int(140 * (self._completion_flash / 0.5))
            flash = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            flash.fill((80, 255, 80, flash_a))
            screen.blit(flash, (box_x, box_y))

        # Step label
        screen.blit(label_surf, (box_x + 12, box_y + 6))

        # Instruction text (centered)
        ix = box_x + (box_w - instr_surf.get_width()) // 2
        iy = box_y + 24
        screen.blit(instr_surf, (ix, iy))

        # Hint
        if hint_surf:
            hx = box_x + (box_w - hint_surf.get_width()) // 2
            hy = iy + instr_surf.get_height() + 3
            screen.blit(hint_surf, (hx, hy))

        # Key highlight badge
        if key:
            key_color = _KEY_COLORS.get(key, (200, 200, 200))
            # Pulsing brightness
            bright = int(180 + 75 * pulse)
            kc = (min(255, key_color[0] + int(75 * pulse)),
                  min(255, key_color[1] + int(75 * pulse)),
                  min(255, key_color[2] + int(75 * pulse)))
            key_surf = font_md.render(f"[ {key} ]", True, kc)
            kx = box_x + (box_w - key_surf.get_width()) // 2
            ky = box_y + box_h - key_surf.get_height() - 4
            screen.blit(key_surf, (kx, ky))

        # Skip text
        skip_surf = sm.render("[F7] Skip", True, (110, 110, 130))
        screen.blit(skip_surf,
                    (box_x + box_w - skip_surf.get_width() - 6,
                     box_y + 4))

    def skip(self):
        """Skip the entire tutorial."""
        self.active = False
        self.completed = True
        self.current_step = self.total_steps

    # -- Internal ---------------------------------------------------------

    def _spawn_entity(self, spawn_type: str, game):
        """Spawn a tutorial entity near the player."""
        self._spawned_for_step.add(spawn_type)
        px, py = self.player.x, self.player.y

        if spawn_type == "dummy":
            self._dummy = PracticeDummy(px + 4, py + 2)
            # Register with game if possible
            if hasattr(game, 'creatures'):
                game.creatures.append(self._dummy)

        elif spawn_type == "tutorial_npc":
            self._guide = TutorialGuide(px + 3, py - 2)
            if hasattr(game, 'npcs'):
                game.npcs.append(self._guide)

    def _advance_step(self, game):
        """Complete current step, show notification, advance."""
        step = ISLAND_STEPS[self.current_step]
        self._completion_flash = 0.5

        if hasattr(game, 'notifications'):
            game.notifications.add(
                f"Tutorial: {step['title']} complete!",
                3.0, (80, 255, 80))

        self.current_step += 1
        self._step_start_time = time.time()

        if self.current_step >= self.total_steps:
            self._finish(game)

    def _finish(self, game):
        """Mark the tutorial as complete."""
        self.active = False
        self.completed = True
        if hasattr(game, 'notifications'):
            game.notifications.add(
                "Tutorial complete! Find the boat to the mainland.",
                6.0, (255, 220, 80))


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_active_tutorials = {}


def start_island_tutorial(player) -> IslandTutorial:
    """Create and register a tutorial for a player on the test island."""
    tut = IslandTutorial(player)
    _active_tutorials[id(player)] = tut
    return tut


def get_island_tutorial(player) -> Optional[IslandTutorial]:
    """Get active island tutorial for a player, if any."""
    return _active_tutorials.get(id(player))


def remove_island_tutorial(player):
    """Remove a finished tutorial."""
    _active_tutorials.pop(id(player), None)

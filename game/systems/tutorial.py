"""
Tutorial quest system for new players on the test island.

Guides players through game basics with step-by-step instructions.
Observes game state without modifying other systems.
"""

import math
import time

import pygame

from game.settings import SCREEN_WIDTH


# -- Tutorial step definitions ------------------------------------------------

TUTORIAL_STEPS = [
    {
        "id": "movement",
        "title": "Movement",
        "text": "Use WASD to move around. Try walking to the nearby signpost.",
        "hint": "Walk at least 10 tiles from your starting position.",
    },
    {
        "id": "look_around",
        "title": "Look Around",
        "text": "Press V to switch view modes. Try Strategy, Adventure, and 3D views.",
        "hint": "Press V once to cycle view modes.",
    },
    {
        "id": "interact",
        "title": "Interact",
        "text": "Walk up to an NPC and press E to talk to them.",
        "hint": "Open a dialog with any NPC.",
    },
    {
        "id": "combat",
        "title": "Combat",
        "text": (
            "A wild creature is nearby! Press SPACE to attack it, "
            "or use the mouse to click on it."
        ),
        "hint": "Deal damage to any creature.",
    },
    {
        "id": "inventory",
        "title": "Inventory",
        "text": "Press I to check your inventory. You have a sword and some bread.",
        "hint": "Open your inventory with I.",
    },
    {
        "id": "character",
        "title": "Character",
        "text": (
            "Press C to see your character sheet "
            "-- your abilities, skills, and class."
        ),
        "hint": "Open your character sheet with C.",
    },
    {
        "id": "quest",
        "title": "Quest",
        "text": (
            "Talk to the NPC with the yellow marker (!) "
            "above their head to get a quest."
        ),
        "hint": "Accept a quest from an NPC.",
    },
    {
        "id": "magic",
        "title": "Magic",
        "text": (
            "Press a number key (1-9) to select a spell, "
            "then click to cast it."
        ),
        "hint": "Cast any spell.",
        "spellcaster_only": True,
    },
    {
        "id": "explore",
        "title": "Explore",
        "text": (
            "You're ready to explore the world! "
            "Head south to find the nearest village."
        ),
        "hint": "Move 50+ tiles from spawn, or wait 2 minutes.",
    },
]

TOTAL_STEPS = len(TUTORIAL_STEPS)


# -- Completion checkers ------------------------------------------------------

def _check_movement(tut, game):
    """Step 0: player moved 10+ tiles from spawn."""
    dx = game.player.x - tut.start_pos[0]
    dy = game.player.y - tut.start_pos[1]
    return math.hypot(dx, dy) >= 10.0


def _check_look_around(tut, game):
    """Step 1: player pressed V (view mode changed at least once)."""
    return tut._view_changed


def _check_interact(tut, game):
    """Step 2: player opened a dialog."""
    return getattr(game.ui, "dialog_active", False)


def _check_combat(tut, game):
    """Step 3: combat system became active (player dealt damage)."""
    return getattr(game.combat, "active", False)


def _check_inventory(tut, game):
    """Step 4: inventory panel is open."""
    return getattr(game.ui, "show_inventory", False)


def _check_character(tut, game):
    """Step 5: character sheet is open."""
    return getattr(game.ui, "show_character", False)


def _check_quest(tut, game):
    """Step 6: player has at least one active quest."""
    quests = getattr(game.quest_sys, "active_quests", [])
    return len(quests) > 0


def _check_magic(tut, game):
    """Step 7: player cast a spell (mana decreased or spell effect active)."""
    return tut._spell_cast


def _check_explore(tut, game):
    """Step 8: player 50+ tiles from spawn or 2 minutes elapsed."""
    dx = game.player.x - tut.start_pos[0]
    dy = game.player.y - tut.start_pos[1]
    if math.hypot(dx, dy) >= 50.0:
        return True
    elapsed = time.time() - tut._explore_start_time
    return elapsed >= 120.0


STEP_CHECKERS = [
    _check_movement,
    _check_look_around,
    _check_interact,
    _check_combat,
    _check_inventory,
    _check_character,
    _check_quest,
    _check_magic,
    _check_explore,
]


# -- Tutorial system ----------------------------------------------------------

class TutorialSystem:
    """Manages a step-by-step tutorial for new players.

    Observes game state each frame to detect step completion.
    Draws hint overlay at the top of the screen.
    """

    def __init__(self, player):
        self.player = player
        self.start_pos = (player.x, player.y)

        self.current_step = 0
        self.steps_completed = set()
        self.active = True
        self.messages = []

        # Build the step list (skip magic for non-spellcasters)
        is_caster = getattr(player, "is_spellcaster", False)
        self.steps = []
        self._step_index_map = []  # maps our index -> global index
        for i, step in enumerate(TUTORIAL_STEPS):
            if step.get("spellcaster_only") and not is_caster:
                continue
            self.steps.append(step)
            self._step_index_map.append(i)

        self.total_steps = len(self.steps)

        # Internal tracking flags
        self._view_changed = False
        self._spell_cast = False
        self._explore_start_time = time.time()
        self._prev_mana = getattr(player, "mana", 0)
        self._pulse_timer = 0.0
        self._completion_flash = 0.0
        self._step_start_time = time.time()

    # -- Public API -----------------------------------------------------------

    def update(self, dt, game):
        """Check completion conditions for the current step."""
        if not self.active:
            return

        self._pulse_timer += dt
        if self._completion_flash > 0:
            self._completion_flash -= dt

        # Detect view mode change (for step 1)
        if hasattr(game, "_view_mode_prev"):
            if game.view_mode != game._view_mode_prev:
                self._view_changed = True
        game._view_mode_prev = getattr(game, "view_mode", "strategy")

        # Detect spell cast via mana decrease
        current_mana = getattr(self.player, "mana", 0)
        if current_mana < self._prev_mana:
            self._spell_cast = True
        self._prev_mana = current_mana

        # Check current step
        if self.current_step >= self.total_steps:
            self.active = False
            return

        global_idx = self._step_index_map[self.current_step]
        checker = STEP_CHECKERS[global_idx]
        if checker(self, game):
            self._complete_current_step(game)

    def draw_hint(self, screen, font_md, font_sm=None):
        """Draw the tutorial hint overlay at the top-center of the screen."""
        if not self.active:
            return
        if self.current_step >= self.total_steps:
            return

        step = self.steps[self.current_step]
        step_label = f"Step {self.current_step + 1}/{self.total_steps}"
        instruction = step["text"]
        hint = step.get("hint", "")

        # Measure text
        label_surf = font_md.render(step_label, True, (255, 220, 100))
        instr_surf = font_md.render(instruction, True, (230, 230, 240))
        skip_text = "[F7] Skip tutorial"
        sm = font_sm or font_md
        skip_surf = sm.render(skip_text, True, (140, 140, 160))

        # Calculate box size
        text_w = max(label_surf.get_width(), instr_surf.get_width())
        box_w = text_w + 40
        box_h = 60
        if hint:
            hint_surf = sm.render(hint, True, (170, 170, 190))
            box_h += hint_surf.get_height() + 4
            box_w = max(box_w, hint_surf.get_width() + 40)
        else:
            hint_surf = None

        box_w = min(box_w, SCREEN_WIDTH - 20)
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = 8

        # Draw semi-transparent background
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill((15, 15, 35, 210))
        screen.blit(bg, (box_x, box_y))

        # Pulsing border
        pulse = (math.sin(self._pulse_timer * 2.5) + 1.0) / 2.0
        border_alpha = int(100 + 80 * pulse)
        border_color = (80, 140, 220, border_alpha)
        border_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, border_color, (0, 0, box_w, box_h), 2)
        screen.blit(border_surf, (box_x, box_y))

        # Completion flash effect
        if self._completion_flash > 0:
            flash_alpha = int(120 * (self._completion_flash / 0.5))
            flash = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            flash.fill((100, 255, 100, flash_alpha))
            screen.blit(flash, (box_x, box_y))

        # Draw step label (top-left of box)
        screen.blit(label_surf, (box_x + 12, box_y + 6))

        # Draw instruction text (centered below label)
        instr_x = box_x + (box_w - instr_surf.get_width()) // 2
        instr_y = box_y + 26
        screen.blit(instr_surf, (instr_x, instr_y))

        # Draw hint text
        if hint_surf:
            hint_x = box_x + (box_w - hint_surf.get_width()) // 2
            hint_y = instr_y + instr_surf.get_height() + 4
            screen.blit(hint_surf, (hint_x, hint_y))

        # Draw skip text (bottom-right corner)
        skip_x = box_x + box_w - skip_surf.get_width() - 8
        skip_y = box_y + box_h - skip_surf.get_height() - 4
        screen.blit(skip_surf, (skip_x, skip_y))

    def skip(self):
        """Mark the tutorial as done (player pressed F7)."""
        self.active = False
        self.steps_completed = set(range(self.total_steps))
        self.current_step = self.total_steps

    def is_complete(self):
        """True when all steps are done."""
        return len(self.steps_completed) >= self.total_steps

    # -- Internal -------------------------------------------------------------

    def _complete_current_step(self, game):
        """Mark the current step complete and advance."""
        step = self.steps[self.current_step]
        self.steps_completed.add(self.current_step)
        self._completion_flash = 0.5

        # Notify the player
        if hasattr(game, "notifications"):
            game.notifications.add(
                f"Tutorial: {step['title']} complete!",
                3.0,
                (100, 255, 100),
            )

        self.current_step += 1
        self._step_start_time = time.time()

        # Set explore timer when reaching the explore step
        if self.current_step < self.total_steps:
            next_step = self.steps[self.current_step]
            if next_step["id"] == "explore":
                self._explore_start_time = time.time()

        # Check if tutorial is now complete
        if self.current_step >= self.total_steps:
            self.active = False
            if hasattr(game, "notifications"):
                game.notifications.add(
                    "Tutorial complete! You're ready to explore the world.",
                    5.0,
                    (255, 220, 100),
                )

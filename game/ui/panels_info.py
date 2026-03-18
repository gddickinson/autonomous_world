"""Information panels — character sheet, quest log, chronicle, planet view."""

import pygame
from typing import List
from game.settings import *


class PanelsInfoMixin:

    """Mixin — see parent class for context."""

    def draw_character_sheet(self, player: Player):
        if not self.show_character:
            return

        cw, ch = 620, 560
        cx = SCREEN_WIDTH // 2 - cw // 2
        cy = SCREEN_HEIGHT // 2 - ch // 2

        race = getattr(player, 'race', 'Human')
        char_class = getattr(player, 'char_class', 'Fighter')
        self._draw_panel(cx, cy, cw, ch,
                        f"{race} {char_class} - Level {player.level}")

        y = cy + 42
        col2 = cx + cw // 2 + 10

        # -- LEFT COLUMN: Ability Scores --
        self.screen.blit(self.font_md.render("Ability Scores", True, UI_HIGHLIGHT), (cx + 15, y))
        y += 22
        from game.data.dnd import ability_modifier
        scores = getattr(player, 'ability_scores', {})
        for attr in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
            val = scores.get(attr, 10)
            mod = ability_modifier(val)
            mod_str = f"+{mod}" if mod >= 0 else str(mod)
            label = f"{attr[:3].upper()}: {val} ({mod_str})"
            self.screen.blit(self.font_sm.render(label, True, UI_TEXT), (cx + 25, y))
            y += 16
        y += 6

        # -- Combat Stats --
        self.screen.blit(self.font_md.render("Combat", True, UI_HIGHLIGHT), (cx + 15, y))
        y += 22
        ac = getattr(player, 'armor_class', 10)
        prof = getattr(player, 'proficiency_bonus', 2)
        combat_stats = [
            f"HP: {int(player.hp)}/{player.max_hp}  |  AC: {ac}",
            f"Attack: {player.get_attack_damage()}  |  Prof: +{prof}",
            f"Energy: {int(player.energy)}/{player.max_energy}",
            f"Gold: {player.gold}  |  XP: {player.xp}/{player.xp_to_next}",
        ]
        for s in combat_stats:
            self.screen.blit(self.font_sm.render(s, True, UI_TEXT), (cx + 25, y))
            y += 16
        y += 6

        # -- Class Abilities --
        abilities_list = getattr(player, 'class_abilities', [])
        self.screen.blit(self.font_md.render("Class Abilities", True, UI_HIGHLIGHT), (cx + 15, y))
        y += 22
        if abilities_list:
            for ab in abilities_list[:6]:
                self.screen.blit(self.font_sm.render(f"  {ab}", True, (160, 200, 160)), (cx + 15, y))
                y += 15
        else:
            self.screen.blit(self.font_sm.render("  None yet", True, GRAY), (cx + 15, y))
            y += 15
        y += 4

        # -- RIGHT COLUMN (start from top) --
        ry = cy + 42

        # Spells
        is_caster = getattr(player, 'is_spellcaster', False)
        self.screen.blit(self.font_md.render("Spells", True, UI_HIGHLIGHT), (col2, ry))
        ry += 22
        if is_caster:
            slots = getattr(player, 'spell_slots', [0,0,0])
            used = getattr(player, 'spell_slots_used', [0,0,0])
            for i in range(3):
                if slots[i] > 0:
                    self.screen.blit(self.font_sm.render(
                        f"Lv{i+1} slots: {slots[i] - used[i]}/{slots[i]}", True, UI_TEXT), (col2 + 10, ry))
                    ry += 14
            ry += 4
            spells = getattr(player, 'known_spells', [])
            for sp in spells[:8]:
                self.screen.blit(self.font_sm.render(f"  {sp}", True, (140, 180, 220)), (col2 + 10, ry))
                ry += 14
        else:
            self.screen.blit(self.font_sm.render("  Not a spellcaster", True, GRAY), (col2 + 10, ry))
            ry += 14
        ry += 8

        # Active abilities (from skill system)
        active_abs = player.get_abilities()
        self.screen.blit(self.font_md.render("Active Abilities", True, UI_HIGHLIGHT), (col2, ry))
        ry += 22
        if active_abs:
            for name, desc, ready, hotkey in active_abs:
                color = GREEN if ready else (100, 100, 100)
                label = f"[{hotkey}] {name}"
                self.screen.blit(self.font_sm.render(label, True, color), (col2 + 10, ry))
                ry += 14
                self.screen.blit(self.font_sm.render(f"  {desc}", True, GRAY), (col2 + 10, ry))
                ry += 14
        else:
            self.screen.blit(self.font_sm.render("  Level up skills to unlock", True, GRAY), (col2 + 10, ry))
            ry += 14
        ry += 8

        # Skills (only show non-zero skills, sorted by level)
        self.screen.blit(self.font_md.render("Skills", True, UI_HIGHLIGHT), (col2, ry))
        ry += 22
        active_skills = sorted(
            [(s, l) for s, l in player.skills.items() if l > 0],
            key=lambda x: -x[1])
        if not active_skills:
            self.screen.blit(self.font_sm.render("  No skills learned yet", True, GRAY), (col2 + 10, ry))
            ry += 16
        for skill, slevel in active_skills:
            xp_frac = player.skill_xp.get(skill, 0) / (5.0 + slevel * 3.0)
            label = skill.replace("_", " ").title()
            self.screen.blit(self.font_sm.render(f"{label:<16s} Lv.{slevel}", True, UI_TEXT),
                            (col2 + 10, ry))
            bx = col2 + 180
            bw = 70
            pygame.draw.rect(self.screen, DARK_GRAY, (bx, ry + 3, bw, 7))
            pygame.draw.rect(self.screen, UI_HIGHLIGHT, (bx, ry + 3, int(bw * xp_frac), 7))
            ry += 16

        # Record at bottom
        y = max(y, ry) + 8
        if y < cy + ch - 50:
            pygame.draw.line(self.screen, UI_BORDER, (cx + 5, y), (cx + cw - 5, y))
            y += 6
            records = f"Kills: {player.kills}  |  Quests: {player.quests_completed}  |  Distance: {int(player.steps)} tiles"
            self.screen.blit(self.font_sm.render(records, True, GRAY), (cx + 15, y))

        hint = self.font_sm.render("[Escape/C] Close", True, (150, 150, 170))
        self.screen.blit(hint, (cx + cw // 2 - hint.get_width() // 2, cy + ch - 22))

    # ================================================================
    # ================================================================
    # PLANET VIEW (3D globe)
    # ================================================================

    def draw_planet_view(self, dt: float = 0.016, time_sys=None):
        """Draw the 3D planet globe view."""
        if not self.show_planet_view:
            return
        self.planet_view.update(dt)
        self.planet_view.draw(self.screen, self.font_sm, self.font_md, self.font_lg, time_sys)

    def draw_quest_log(self, quests: List[Quest]):
        if not self.show_quest_log:
            return

        qw, qh = 450, 350
        qx = SCREEN_WIDTH // 2 - qw // 2
        qy = SCREEN_HEIGHT // 2 - qh // 2

        self._draw_panel(qx, qy, qw, qh, f"Quest Log ({len(quests)}/5)")

        y = qy + 42
        if not quests:
            self.screen.blit(self.font_md.render("No active quests", True, GRAY),
                            (qx + qw // 2 - 70, y + 20))
        else:
            for quest in quests:
                color = GREEN if quest.completed else UI_TEXT
                self.screen.blit(self.font_md.render(quest.title, True, color), (qx + 15, y))
                prog = self.font_sm.render(f"[{quest.progress_text}]", True,
                                          GREEN if quest.completed else YELLOW)
                self.screen.blit(prog, (qx + qw - prog.get_width() - 15, y + 2))
                y += 20
                self.screen.blit(self.font_sm.render(quest.description, True, GRAY), (qx + 25, y))
                y += 18
                self.screen.blit(self.font_sm.render(f"From: {quest.giver_name}", True, (100, 100, 120)),
                                (qx + 25, y))
                y += 24

        hint = self.font_sm.render("[Escape/Q] Close", True, (150, 150, 170))
        self.screen.blit(hint, (qx + qw // 2 - hint.get_width() // 2, qy + qh - 22))

    # ================================================================
    # PAUSE MENU
    # ================================================================

    def draw_pause_menu(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        title = self.font_xl.render("PAUSED", True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 4))

        hints = [
            "Press ESC to resume",
            "",
            "=== MOVEMENT ===",
            "WASD / Arrows  - Move (always works)",
            "",
            "=== COMBAT ===",
            "Space          - Target/attack nearest enemy",
            "Escape         - Disengage from combat",
            "F1-F5          - Use abilities",
            "",
            "=== INTERACTION ===",
            "E              - Interact (talk/pickup/doors/gather)",
            "T              - Free-text chat with NPC",
            "R              - Recruit NPC to party",
            "Tab            - Cycle nearby NPCs",
            "",
            "=== MENUS (Arrow keys to navigate) ===",
            "I              - Inventory (Tab: cycle categories)",
            "C              - Character sheet",
            "Q              - Quest log / toggle tracker",
            "H              - Historical chronicle",
            "X              - Examine surroundings",
            "G              - Drop item",
            "P              - Toggle auto-play",
        ]
        y = SCREEN_HEIGHT // 4 + 60
        for hint in hints:
            self.screen.blit(self.font_md.render(hint, True, UI_TEXT),
                            (SCREEN_WIDTH // 2 - 180, y))
            y += 24

    def draw_chronicle(self, chronicle: 'ChronicleSystem'):
        """Draw the historical chronicle as a scrollable text panel."""
        if not self.show_chronicle:
            return

        cw, ch = 700, 520
        cx = SCREEN_WIDTH // 2 - cw // 2
        cy = SCREEN_HEIGHT // 2 - ch // 2

        self._draw_panel(cx, cy, cw, ch, "")

        # Title
        title_surf = self.font_lg.render("THE CHRONICLE OF THE REALM", True, (220, 200, 140))
        self.screen.blit(title_surf, (cx + cw // 2 - title_surf.get_width() // 2, cy + 8))
        pygame.draw.line(self.screen, (120, 110, 80), (cx + 10, cy + 34), (cx + cw - 10, cy + 34))

        # Current era
        era_surf = self.font_sm.render(f"Current Era: {chronicle.get_era_name(999999)}", True, (180, 160, 100))
        self.screen.blit(era_surf, (cx + cw // 2 - era_surf.get_width() // 2, cy + 38))

        # Generate chronicle text
        lines = chronicle.generate_chronicle()

        # Scrollable region
        content_y = cy + 56
        content_h = ch - 80
        max_visible = content_h // 16
        max_scroll = max(0, len(lines) - max_visible)
        self.chronicle_scroll = max(0, min(self.chronicle_scroll, max_scroll))

        visible_lines = lines[self.chronicle_scroll:self.chronicle_scroll + max_visible]

        y = content_y
        for line in visible_lines:
            # Color coding based on content
            color = UI_TEXT
            if line.startswith("===") or line.startswith("---"):
                color = (180, 160, 100)  # era markers in gold
            elif line.startswith("Year "):
                color = UI_HIGHLIGHT  # year headers in blue
            elif line.startswith("  ***"):
                color = (255, 215, 0)  # legendary events in gold
            elif line.startswith("  **"):
                color = (180, 100, 220)  # major events in purple
            elif line.startswith("  *"):
                color = (100, 200, 120)  # notable events in green
            elif line.strip().endswith(":"):
                color = (160, 160, 180)  # season headers

            line_surf = self.font_sm.render(line[:85], True, color)
            self.screen.blit(line_surf, (cx + 15, y))
            y += 16

        # Scroll indicator
        if len(lines) > max_visible:
            scroll_pct = self.chronicle_scroll / max(1, max_scroll)
            bar_h = content_h
            bar_x = cx + cw - 12
            pygame.draw.rect(self.screen, (40, 40, 55), (bar_x, content_y, 6, bar_h))
            thumb_h = max(20, int(bar_h * max_visible / len(lines)))
            thumb_y = content_y + int((bar_h - thumb_h) * scroll_pct)
            pygame.draw.rect(self.screen, UI_HIGHLIGHT, (bar_x, thumb_y, 6, thumb_h))

        # Entry count
        count_surf = self.font_sm.render(f"{len(chronicle.entries)} events recorded", True, GRAY)
        self.screen.blit(count_surf, (cx + 15, cy + ch - 20))

        hint = self.font_sm.render("[Up/Down] Scroll  [Escape/H] Close", True, (150, 150, 170))
        self.screen.blit(hint, (cx + cw // 2 - hint.get_width() // 2, cy + ch - 20))



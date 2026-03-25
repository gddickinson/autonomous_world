"""Spell bar UI — lets players select and cast spells with number keys.

Shows known spells in a hotbar at the bottom of the screen.
Press 1-9 to cast the corresponding spell at the nearest hostile target.
Press S to open/close the spell selection overlay.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT


class SpellBar:
    """Manages spell hotbar display and casting."""

    def __init__(self, font_sm, font_md):
        self.font_sm = font_sm
        self.font_md = font_md
        self.show_full_list = False  # S key toggles expanded view
        self.selected_slot = -1     # highlighted slot (-1 = none)
        self.hotbar_page = 0        # which page of 9 spells is shown
        self.list_scroll = 0        # scroll offset in full spell list
        self._spell_surf_cache = {}

    def draw(self, screen, player, targeting=None):
        """Draw the spell hotbar at the bottom of the screen."""
        if not getattr(player, 'is_spellcaster', False):
            return

        spells = getattr(player, 'known_spells', [])
        if not spells:
            return

        # Which spell is currently being targeted (if any)?
        active_spell_name = None
        if targeting and targeting.is_active():
            active_spell_name = getattr(targeting, 'spell_name', None)

        mana = getattr(player, 'mana', 0)
        max_mana = getattr(player, 'max_mana', 1)

        # Mana bar (above spell bar)
        bar_w = min(200, len(spells) * 36 + 10)
        bar_x = SCREEN_WIDTH // 2 - bar_w // 2
        bar_y = SCREEN_HEIGHT - 52
        pygame.draw.rect(screen, (20, 20, 40), (bar_x, bar_y, bar_w, 8))
        mana_w = int(bar_w * mana / max(1, max_mana))
        pygame.draw.rect(screen, (60, 100, 200), (bar_x, bar_y, mana_w, 8))
        pygame.draw.rect(screen, (40, 60, 120), (bar_x, bar_y, bar_w, 8), 1)
        # Mana text
        mana_txt = self.font_sm.render(f"{int(mana)}/{int(max_mana)}", True, (140, 170, 220))
        screen.blit(mana_txt, (bar_x + bar_w + 4, bar_y - 1))

        # Spell hotbar (bottom) — shows 9 spells from current page
        slot_size = 32
        max_pages = max(1, (len(spells) + 8) // 9)
        self.hotbar_page = min(self.hotbar_page, max_pages - 1)
        page_start = self.hotbar_page * 9
        hotbar_spells = spells[page_start:page_start + 9]
        total_w = len(hotbar_spells) * (slot_size + 4)
        start_x = SCREEN_WIDTH // 2 - total_w // 2
        bar_y = SCREEN_HEIGHT - 40

        for i, spell_name in enumerate(hotbar_spells):
            sx = start_x + i * (slot_size + 4)
            sy = bar_y

            # Check if this spell is the active targeting spell
            is_active = (active_spell_name is not None
                         and spell_name == active_spell_name)

            # Background — bright glow when active targeting
            if is_active:
                # Pulsing glow effect
                import math as _m
                pulse = int(abs(_m.sin(pygame.time.get_ticks() * 0.005)) * 40)
                glow_surf = pygame.Surface((slot_size + 6, slot_size + 6), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (255, 220, 80, 80 + pulse),
                                 (0, 0, slot_size + 6, slot_size + 6), border_radius=5)
                screen.blit(glow_surf, (sx - 3, sy - 3))
                bg_color = (70, 60, 30)
                border_color = (255, 220, 80)
            else:
                bg_color = (40, 40, 70)
                border_color = (80, 80, 120)
            pygame.draw.rect(screen, bg_color, (sx, sy, slot_size, slot_size),
                             border_radius=3)
            pygame.draw.rect(screen, border_color, (sx, sy, slot_size, slot_size),
                             2 if is_active else 1, border_radius=3)

            # Spell icon (first 2 letters + color based on school)
            short = spell_name[:2].upper()
            school_colors = {
                "Fi": (220, 100, 40), "Bu": (220, 120, 40), "Sc": (220, 80, 30),
                "Li": (180, 180, 255), "Th": (150, 150, 220),
                "Ma": (160, 120, 220), "Sh": (100, 140, 220), "Mi": (120, 120, 200),
                "Cu": (100, 220, 100), "He": (100, 200, 100), "Bl": (220, 200, 100),
                "Sa": (220, 200, 100), "Gu": (220, 200, 100),
                "Ch": (200, 140, 200), "Sl": (140, 100, 180),
                "El": (140, 60, 180), "He": (180, 60, 60),
                "De": (160, 160, 200), "En": (120, 200, 120),
                "Ra": (120, 160, 80), "Sp": (200, 200, 140),
            }
            icon_color = school_colors.get(short, (160, 160, 200))
            icon_surf = self.font_sm.render(short, True, icon_color)
            screen.blit(icon_surf, (sx + slot_size // 2 - icon_surf.get_width() // 2,
                                     sy + 4))

            # Key number
            key_surf = self.font_sm.render(str(i + 1), True, (180, 180, 200))
            screen.blit(key_surf, (sx + 2, sy + slot_size - 12))

            # Cooldown overlay
            cds = getattr(player, 'spell_cooldowns', {})
            if spell_name in cds:
                cd_surf = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
                cd_surf.fill((0, 0, 0, 140))
                screen.blit(cd_surf, (sx, sy))
                cd_txt = self.font_sm.render(f"{cds[spell_name]:.0f}", True, (200, 80, 80))
                screen.blit(cd_txt, (sx + slot_size // 2 - cd_txt.get_width() // 2,
                                      sy + slot_size // 2 - 5))

        # Active spell targeting indicator
        if active_spell_name:
            target_txt = self.font_md.render(
                f"TARGETING: {active_spell_name.replace('_', ' ').title()} — Click to cast",
                True, (255, 220, 80))
            screen.blit(target_txt, (SCREEN_WIDTH // 2 - target_txt.get_width() // 2,
                                      bar_y - 28))

        # Page indicator and hint
        if max_pages > 1:
            page_txt = self.font_sm.render(
                f"Page {self.hotbar_page + 1}/{max_pages} [</>]", True, (140, 140, 170))
            screen.blit(page_txt, (start_x + total_w + 8, bar_y + 10))
        hint = self.font_sm.render("1-9: cast  S: list  </> pages", True, (120, 120, 150))
        screen.blit(hint, (start_x - hint.get_width() - 8, bar_y + 10))

        # Full spell list overlay (when S pressed)
        if self.show_full_list:
            self._draw_spell_list(screen, player, spells)

    def _draw_spell_list(self, screen, player, spells):
        """Draw expanded spell list overlay."""
        ow = 300
        oh = min(400, len(spells) * 20 + 40)
        ox = SCREEN_WIDTH // 2 - ow // 2
        oy = SCREEN_HEIGHT // 2 - oh // 2

        # Background
        overlay = pygame.Surface((ow, oh), pygame.SRCALPHA)
        overlay.fill((20, 20, 35, 230))
        screen.blit(overlay, (ox, oy))
        pygame.draw.rect(screen, (80, 80, 120), (ox, oy, ow, oh), 1)

        # Title
        title = self.font_md.render("Known Spells", True, (220, 220, 240))
        screen.blit(title, (ox + ow // 2 - title.get_width() // 2, oy + 6))

        # Mana
        mana = getattr(player, 'mana', 0)
        max_mana = getattr(player, 'max_mana', 1)
        mana_txt = self.font_sm.render(f"Mana: {int(mana)}/{int(max_mana)}", True,
                                        (100, 150, 220))
        screen.blit(mana_txt, (ox + 10, oy + 28))

        # Spell list (scrollable)
        cds = getattr(player, 'spell_cooldowns', {})
        visible_count = (oh - 68) // 18
        for vi, i in enumerate(range(self.list_scroll, min(len(spells), self.list_scroll + visible_count))):
            spell_name = spells[i]
            sy = oy + 48 + vi * 18

            # Key binding (shows which key on current page)
            page_start = self.hotbar_page * 9
            if page_start <= i < page_start + 9:
                key_num = i - page_start + 1
                key_txt = self.font_sm.render(f"[{key_num}]", True, (180, 180, 100))
                screen.blit(key_txt, (ox + 8, sy))

            # Spell name
            on_cd = spell_name in cds
            color = (120, 120, 140) if on_cd else (200, 200, 220)
            name_txt = self.font_sm.render(spell_name, True, color)
            screen.blit(name_txt, (ox + 36, sy))

            # Cooldown
            if on_cd:
                cd_txt = self.font_sm.render(f"({cds[spell_name]:.0f}s)", True, (200, 80, 80))
                screen.blit(cd_txt, (ox + ow - 50, sy))

        # Scroll indicator
        if len(spells) > visible_count:
            scroll_txt = self.font_sm.render(
                f"UP/DOWN scroll ({self.list_scroll + 1}-{min(len(spells), self.list_scroll + visible_count)}/{len(spells)})",
                True, (120, 120, 140))
            screen.blit(scroll_txt, (ox + 10, oy + oh - 30))
        # Close hint
        close_txt = self.font_sm.render("[S] close  [</>] change page", True, (140, 140, 160))
        screen.blit(close_txt, (ox + ow // 2 - close_txt.get_width() // 2, oy + oh - 14))

    def handle_key(self, key, game) -> bool:
        """Handle spell-related key presses. Returns True if handled."""
        player = game.player
        if not getattr(player, 'is_spellcaster', False):
            return False

        # S toggles spell list
        if key == pygame.K_s:
            self.show_full_list = not self.show_full_list
            self.list_scroll = 0
            return True

        # < and > (comma/period) page through hotbar
        spells = getattr(player, 'known_spells', [])
        max_pages = max(1, (len(spells) + 8) // 9)
        if key == pygame.K_COMMA or key == pygame.K_LEFTBRACKET:
            self.hotbar_page = (self.hotbar_page - 1) % max_pages
            return True
        if key == pygame.K_PERIOD or key == pygame.K_RIGHTBRACKET:
            self.hotbar_page = (self.hotbar_page + 1) % max_pages
            return True

        # UP/DOWN scroll spell list when open
        if self.show_full_list:
            if key == pygame.K_UP:
                self.list_scroll = max(0, self.list_scroll - 1)
                return True
            if key == pygame.K_DOWN:
                self.list_scroll = min(max(0, len(spells) - 15), self.list_scroll + 1)
                return True

        # 1-9 cast spell from current hotbar page
        if pygame.K_1 <= key <= pygame.K_9:
            slot = key - pygame.K_1
            page_start = self.hotbar_page * 9
            actual_idx = page_start + slot
            if actual_idx < len(spells):
                spell_name = spells[actual_idx]
                self._cast_player_spell(game, spell_name)
                return True

        return False

    def _is_self_target_spell(self, spell_name, spell_data):
        """Check if a spell should be cast immediately (self-target)."""
        if spell_data is None:
            return False
        targets = getattr(spell_data, 'targets', 'single')
        if targets == "self":
            return True
        # Ally buffs on self: shield, armor, bless-like spells
        effect_type = getattr(spell_data, 'effect_type', '')
        if effect_type == "buff" and targets == "ally":
            return True
        # Name-based detection for common self-target spells
        name = spell_name.lower()
        if any(w in name for w in ("shield", "armor", "sanctuary",
                                    "flame_shield", "mage_armor")):
            return True
        return False

    def _cast_player_spell(self, game, spell_name):
        """Cast a spell — self-target immediately, others enter targeting."""
        from game.systems.magic import SPELL_REGISTRY, SOUL_SPELLS

        spell_data = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)

        # Self-target spells cast immediately without mouse targeting
        if self._is_self_target_spell(spell_name, spell_data):
            self._cast_immediate(game, spell_name)
            return

        # All other spells: enter targeting mode if targeting system exists
        targeting = getattr(game, 'targeting', None)
        if targeting and spell_data:
            caster_level = getattr(game.player, 'level', 1)
            targeting.begin_spell_target(spell_name, spell_data, caster_level)
            game.notifications.add(
                f"Targeting: {spell_name.replace('_', ' ').title()} — "
                f"click to cast, right-click to cancel",
                2.5, (180, 200, 240))
            return

        # Fallback: cast immediately (no targeting system)
        self._cast_immediate(game, spell_name)

    def _cast_immediate(self, game, spell_name):
        """Cast spell immediately without mouse targeting (original behavior)."""
        from game.systems.combat import CombatSystem
        result = CombatSystem.player_cast_spell(
            game.player,
            spell_name,
            game.world_mgr.creatures,
            game.world_mgr.npcs,
        )
        if result:
            # Color-code the notification
            if "Cannot" in result or "Unknown" in result:
                color = (200, 80, 80)
            elif "slain" in result.lower() or "damage" in result.lower():
                color = (220, 180, 60)
            elif "heal" in result.lower() or "cure" in result.lower():
                color = (80, 200, 80)
            else:
                color = (140, 180, 220)
            game.notifications.add(result, 3.0, color)

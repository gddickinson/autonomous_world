"""Inventory UI panel."""

import pygame
from typing import Optional
from game.settings import *
from game.ui.item_icons import get_item_icon

class PanelsInventoryMixin:
    """Inventory UI panel."""

    def draw_inventory(self, player: Player):
        if not self.show_inventory:
            return

        iw, ih = 540, 500
        ix = SCREEN_WIDTH // 2 - iw // 2
        iy = SCREEN_HEIGHT // 2 - ih // 2

        self._draw_panel(ix, iy, iw, ih, f"Inventory ({len(player.inventory)}/20)")

        # -- Equipped items section (top) --
        y = iy + 42
        equip_label = self.font_sm.render("EQUIPPED", True, (180, 160, 100))
        self.screen.blit(equip_label, (ix + 15, y))
        y += 16

        weapon_name = player.equipped_weapon.name if player.equipped_weapon else "None"
        armor_name = player.equipped_armor.name if player.equipped_armor else "None"

        # Weapon with rarity color + icon
        wlabel = self.font_sm.render("Weapon: ", True, (150, 150, 170))
        self.screen.blit(wlabel, (ix + 20, y))
        wlabel_end = ix + 20 + wlabel.get_width()
        if player.equipped_weapon:
            w_icon = get_item_icon(weapon_name, "weapon")
            self.screen.blit(w_icon, (wlabel_end, y))
            _, wcolor = self._get_item_rarity(player.equipped_weapon)
            durability_str = ""
            if hasattr(player.equipped_weapon, 'durability') and player.equipped_weapon.durability is not None:
                durability_str = f" [{player.equipped_weapon.durability}%]"
            wname_surf = self.font_sm.render(f"{weapon_name}{durability_str}", True, wcolor)
            self.screen.blit(wname_surf, (wlabel_end + 16, y))
        else:
            wname_surf = self.font_sm.render(weapon_name, True, GRAY)
            self.screen.blit(wname_surf, (wlabel_end, y))

        # Armor on same line (right side)
        alabel = self.font_sm.render("Armor: ", True, (150, 150, 170))
        ax = ix + iw // 2 + 10
        self.screen.blit(alabel, (ax, y))
        alabel_end = ax + alabel.get_width()
        if player.equipped_armor:
            a_icon = get_item_icon(armor_name, "armor")
            self.screen.blit(a_icon, (alabel_end, y))
            _, acolor = self._get_item_rarity(player.equipped_armor)
            aname_surf = self.font_sm.render(armor_name, True, acolor)
            self.screen.blit(aname_surf, (alabel_end + 16, y))
        else:
            aname_surf = self.font_sm.render(armor_name, True, GRAY)
            self.screen.blit(aname_surf, (alabel_end, y))
        y += 16

        self.screen.blit(self.font_sm.render(
            f"ATK: {player.get_attack_damage()}  DEF: {player.get_defense()}  Gold: {player.gold}",
            True, (180, 180, 200)), (ix + 20, y))
        y += 18

        pygame.draw.line(self.screen, UI_BORDER, (ix + 5, y), (ix + iw - 5, y))
        y += 4

        # -- Category tabs --
        tab_x = ix + 8
        for ti, (tab_name, _) in enumerate(self._INV_CATEGORIES):
            is_active = (ti == self.inv_category)
            tab_color = UI_HIGHLIGHT if is_active else (100, 100, 120)
            bg_color = (40, 40, 60) if is_active else (20, 20, 35)

            tab_surf = self.font_sm.render(tab_name, True, tab_color)
            tw = tab_surf.get_width() + 10
            tab_rect = pygame.Rect(tab_x, y, tw, 16)

            if is_active:
                pygame.draw.rect(self.screen, bg_color, tab_rect)
                pygame.draw.rect(self.screen, tab_color, tab_rect, 1)

            self.screen.blit(tab_surf, (tab_x + 5, y + 1))
            tab_x += tw + 2

            if tab_x > ix + iw - 40:
                break  # prevent overflow

        y += 20
        pygame.draw.line(self.screen, UI_BORDER, (ix + 5, y), (ix + iw - 5, y))
        y += 4

        # -- Filtered item list --
        filtered_items = self._filter_inventory(player)

        if not filtered_items:
            empty_msg = "Empty" if not player.inventory else "No items in this category"
            self.screen.blit(self.font_md.render(empty_msg, True, GRAY),
                            (ix + iw // 2 - 50, y + 20))
        else:
            # Clamp selection
            if self.inv_selected >= len(filtered_items):
                self.inv_selected = max(0, len(filtered_items) - 1)

            for i, item in enumerate(filtered_items):
                if y > iy + ih - 90:
                    more = len(filtered_items) - i
                    self.screen.blit(self.font_sm.render(f"... and {more} more items", True, GRAY),
                                    (ix + 22, y))
                    break

                # Rarity color for item name
                rarity_name, rarity_color = self._get_item_rarity(item)
                is_selected = (i == self.inv_selected)

                if is_selected:
                    pygame.draw.rect(self.screen, (40, 40, 60), (ix + 5, y - 2, iw - 10, 18))

                count_str = f" x{item.count}" if item.stackable and item.count > 1 else ""
                text = f"{item.name}{count_str}"

                # Item icon (procedural)
                icon = get_item_icon(item.name, getattr(item, 'kind', ''))
                self.screen.blit(icon, (ix + 6, y + 1))

                # Item name in rarity color (or highlighted if selected)
                name_color = YELLOW if is_selected else rarity_color
                self.screen.blit(self.font_sm.render(text, True, name_color), (ix + 22, y))

                # Quick stat summary on right
                stat_parts = []
                if item.damage:
                    stat_parts.append(f"+{item.damage}D")
                if item.defense:
                    stat_parts.append(f"+{item.defense}A")
                if item.heal:
                    stat_parts.append(f"+{item.heal}H")
                if stat_parts:
                    stat_str = " ".join(stat_parts)
                    stat_surf = self.font_sm.render(stat_str, True, (140, 140, 160))
                    self.screen.blit(stat_surf, (ix + iw - stat_surf.get_width() - 45, y))

                self.screen.blit(self.font_sm.render(f"{item.value}g", True, GRAY),
                                (ix + iw - 40, y))
                y += 18

        # -- Detail panel for selected item --
        if filtered_items and self.inv_selected < len(filtered_items):
            item = filtered_items[self.inv_selected]
            y = iy + ih - 82
            pygame.draw.line(self.screen, UI_BORDER, (ix + 5, y), (ix + iw - 5, y))
            y += 5

            # Rarity badge
            rarity_name, rarity_color = self._get_item_rarity(item)
            rarity_surf = self.font_sm.render(f"[{rarity_name}]", True, rarity_color)
            self.screen.blit(rarity_surf, (ix + 15, y))
            y += 14

            self.screen.blit(self.font_sm.render(item.description, True, GRAY), (ix + 15, y))
            y += 16
            stats = []
            if item.damage:
                stats.append(f"DMG:+{item.damage}")
            if item.defense:
                stats.append(f"DEF:+{item.defense}")
            if item.heal:
                stats.append(f"Heal:{item.heal}")
            if hasattr(item, 'durability') and item.durability is not None:
                stats.append(f"Dur:{item.durability}/{item.max_durability}")
            if stats:
                self.screen.blit(self.font_sm.render("  ".join(stats), True, UI_HIGHLIGHT), (ix + 15, y))
                y += 14

        hint = self.font_sm.render("[E] Use/Equip  [G/X] Drop  [Tab] Category  [Escape/I] Close", True, (150, 150, 170))
        self.screen.blit(hint, (ix + 15, iy + ih - 18))


    def handle_inventory_input(self, key, player: Player, world_mgr=None) -> Optional[str]:
        if not self.show_inventory:
            return None

        if key == pygame.K_ESCAPE or key == pygame.K_i:
            self.show_inventory = False
            return None

        # Tab to cycle category
        if key == pygame.K_TAB:
            self.inv_category = (self.inv_category + 1) % len(self._INV_CATEGORIES)
            self.inv_selected = 0
            return None

        if not player.inventory:
            return None

        # Work with filtered list
        filtered = self._filter_inventory(player)
        if not filtered:
            return None

        if key == pygame.K_UP:
            self.inv_selected = max(0, self.inv_selected - 1)
        elif key == pygame.K_DOWN:
            self.inv_selected = min(len(filtered) - 1, self.inv_selected + 1)
        elif key == pygame.K_e or key == pygame.K_RETURN:
            if self.inv_selected < len(filtered):
                item = filtered[self.inv_selected]
                result = player.use_item(item)
                if result:
                    self.inv_selected = min(self.inv_selected, max(0, len(self._filter_inventory(player)) - 1))
                    return result
        elif key in (pygame.K_x, pygame.K_g):
            if self.inv_selected < len(filtered):
                item = filtered[self.inv_selected]
                if item.kind != ITEM_QUEST:
                    player.inventory.remove(item)
                    self.inv_selected = min(self.inv_selected, max(0, len(self._filter_inventory(player)) - 1))
                    return ("drop", item)
                else:
                    return "Can't drop quest items!"
        return None

    # ================================================================
    # CHARACTER SHEET
    # ================================================================



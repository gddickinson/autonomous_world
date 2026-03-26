"""Shop, barter, and gift UI panels."""

import pygame
from typing import Optional
from game.settings import *

class PanelsShopMixin:
    """Shop, barter, and gift UI panels."""

    def open_shop(self, npc: NPC):
        # Support both formal shop_items and informal barter from npc_inventory
        if not npc.shop_items and not getattr(npc, 'npc_inventory', []):
            return
        self.shop_active = True
        self.shop_npc = npc
        self.shop_selected = 0
        self._shop_sell_mode = False
        # Track whether this is a barter (selling from personal inventory)
        self._shop_is_barter = not npc.shop_items and bool(getattr(npc, 'npc_inventory', []))


    def _get_shop_items(self):
        """Get displayable items - either shop_items or npc_inventory for barter."""
        npc = self.shop_npc
        if not npc:
            return []
        if npc.shop_items:
            return npc.shop_items
        return getattr(npc, 'npc_inventory', [])


    def draw_shop(self, player: Player):
        if not self.shop_active or not self.shop_npc:
            return

        is_barter = getattr(self, '_shop_is_barter', False)
        sell_mode = self._shop_sell_mode

        # Determine items to display based on mode
        if sell_mode:
            items = list(player.inventory)
        else:
            items = self._get_shop_items()

        sw, sh = 500, 350
        sx = SCREEN_WIDTH // 2 - sw // 2
        sy = SCREEN_HEIGHT // 2 - sh // 2

        mode_label = "SELL" if sell_mode else "BUY"
        if is_barter:
            title = f"Barter with {self.shop_npc.name} [{mode_label}]"
        else:
            title = f"{self.shop_npc.name}'s Shop [{mode_label}]"
        self._draw_panel(sx, sy, sw, sh, title)

        gold_text = self.font_md.render(f"Your Gold: {player.gold}", True, YELLOW)
        self.screen.blit(gold_text, (sx + sw - gold_text.get_width() - 15, sy + 8))

        if not items:
            msg = "You have nothing to sell." if sell_mode else "Nothing available to trade."
            no_items = self.font_md.render(msg, True, GRAY)
            self.screen.blit(no_items, (sx + 15, sy + 45))
            hint = self.font_sm.render("[Tab] Buy/Sell  [Escape] Close", True, (150, 150, 170))
            self.screen.blit(hint, (sx + sw // 2 - hint.get_width() // 2, sy + sh - 22))
            return

        y = sy + 45
        for i, item in enumerate(items):
            color = YELLOW if i == self.shop_selected else UI_TEXT
            if i == self.shop_selected:
                pygame.draw.rect(self.screen, (40, 40, 60), (sx + 5, y - 2, sw - 10, 22))

            if sell_mode:
                # Sell price: 50% value, or 40% for barter
                sell_mult = 0.4 if is_barter else 0.5
                price = max(1, int(item.value * sell_mult))
                text = f"{item.name:<25s} {price:>4d} gold"
            else:
                price = item.value if not is_barter else max(1, int(item.value * 0.8))
                text = f"{item.name:<25s} {price:>4d} gold"
            self.screen.blit(self.font_md.render(text, True, color), (sx + 15, y))
            y += 24

        if items and self.shop_selected < len(items):
            item = items[self.shop_selected]
            y += 10
            pygame.draw.line(self.screen, UI_BORDER, (sx + 5, y), (sx + sw - 5, y))
            y += 8
            desc = getattr(item, 'description', '') or ''
            self.screen.blit(self.font_sm.render(desc, True, GRAY), (sx + 15, y))
            y += 18
            if getattr(item, 'damage', 0):
                self.screen.blit(self.font_sm.render(f"Damage: +{item.damage}", True, RED), (sx + 15, y))
            elif getattr(item, 'defense', 0):
                self.screen.blit(self.font_sm.render(f"Defense: +{item.defense}", True, BLUE), (sx + 15, y))
            elif getattr(item, 'heal', 0):
                self.screen.blit(self.font_sm.render(f"Heals: {item.heal} HP", True, GREEN), (sx + 15, y))

        action_label = "Sell" if sell_mode else "Buy"
        hint = self.font_sm.render(f"[Tab] Buy/Sell  [Enter] {action_label}  [Escape] Close", True, (150, 150, 170))
        self.screen.blit(hint, (sx + sw // 2 - hint.get_width() // 2, sy + sh - 22))


    def handle_shop_input(self, key, player: Player) -> Optional[str]:
        if not self.shop_active or not self.shop_npc:
            return None

        is_barter = getattr(self, '_shop_is_barter', False)
        sell_mode = self._shop_sell_mode

        # Determine items based on mode
        if sell_mode:
            items = list(player.inventory)
        else:
            items = self._get_shop_items()

        if key == pygame.K_TAB:
            self._shop_sell_mode = not self._shop_sell_mode
            self.shop_selected = 0
            return None
        elif key == pygame.K_UP:
            self.shop_selected = max(0, self.shop_selected - 1)
        elif key == pygame.K_DOWN:
            self.shop_selected = min(len(items) - 1, self.shop_selected + 1) if items else 0
        elif key == pygame.K_RETURN or key == pygame.K_e:
            if not items or self.shop_selected >= len(items):
                return None

            if sell_mode:
                # Sell mode: remove item from player, add gold
                item = items[self.shop_selected]
                sell_mult = 0.4 if is_barter else 0.5
                price = max(1, int(item.value * sell_mult))
                player.gold += price
                # Give gold to NPC
                self.shop_npc.npc_gold = getattr(self.shop_npc, 'npc_gold', 0) - price
                # Remove from player inventory
                player.inventory.remove(item)
                # Adjust selection
                new_items = list(player.inventory)
                if self.shop_selected >= len(new_items):
                    self.shop_selected = max(0, len(new_items) - 1)
                return f"Sold {item.name} for {price} gold"
            else:
                # Buy mode (original logic)
                item = items[self.shop_selected]
                price = item.value if not is_barter else max(1, int(item.value * 0.8))
                if player.gold >= price:
                    if is_barter:
                        # Barter: take actual item from NPC's inventory
                        if player.add_item(item):
                            player.gold -= price
                            self.shop_npc.npc_gold = getattr(self.shop_npc, 'npc_gold', 0) + price
                            self.shop_npc.npc_inventory.remove(item)
                            # Adjust selection if we removed the last item
                            if self.shop_selected >= len(self.shop_npc.npc_inventory):
                                self.shop_selected = max(0, len(self.shop_npc.npc_inventory) - 1)
                            if not self.shop_npc.npc_inventory:
                                self.shop_active = False
                                return f"Bought {item.name} for {price} gold. Nothing left to trade."
                            return f"Bought {item.name} for {price} gold"
                        else:
                            return "Inventory full!"
                    else:
                        # Shop: create a copy of the item
                        from game.core.items import make_item
                        bought = make_item(item.name)
                        if player.add_item(bought):
                            player.gold -= price
                            return f"Bought {item.name} for {price} gold"
                        else:
                            return "Inventory full!"
                else:
                    return "Not enough gold!"
        elif key == pygame.K_ESCAPE:
            self.shop_active = False
            self._shop_is_barter = False
            self._shop_sell_mode = False
        return None

    # ================================================================
    # GIFT GIVING
    # ================================================================


    def open_gift_panel(self, npc: NPC):
        """Open the gift-giving panel for an NPC."""
        self.gift_active = True
        self.gift_npc = npc
        self.gift_selected = 0


    def draw_gift_panel(self, player: Player):
        """Render the gift selection panel."""
        if not self.gift_active or not self.gift_npc:
            return

        items = list(player.inventory)
        npc = self.gift_npc

        gw, gh = 500, 350
        gx = SCREEN_WIDTH // 2 - gw // 2
        gy = SCREEN_HEIGHT // 2 - gh // 2

        self._draw_panel(gx, gy, gw, gh, f"Give a Gift to {npc.name}")

        if not items:
            no_items = self.font_md.render("You have nothing to give.", True, GRAY)
            self.screen.blit(no_items, (gx + 15, gy + 45))
            hint = self.font_sm.render("[Escape] Close", True, (150, 150, 170))
            self.screen.blit(hint, (gx + gw // 2 - hint.get_width() // 2, gy + gh - 22))
            return

        y = gy + 45
        for i, item in enumerate(items):
            color = YELLOW if i == self.gift_selected else UI_TEXT
            if i == self.gift_selected:
                pygame.draw.rect(self.screen, (40, 40, 60), (gx + 5, y - 2, gw - 10, 22))

            text = f"Give {item.name} to {npc.name}"
            self.screen.blit(self.font_md.render(text, True, color), (gx + 15, y))
            y += 24

        # Selected item description
        if items and self.gift_selected < len(items):
            item = items[self.gift_selected]
            y += 10
            pygame.draw.line(self.screen, UI_BORDER, (gx + 5, y), (gx + gw - 5, y))
            y += 8
            desc = getattr(item, 'description', '') or ''
            self.screen.blit(self.font_sm.render(desc, True, GRAY), (gx + 15, y))
            y += 18
            if getattr(item, 'damage', 0):
                self.screen.blit(self.font_sm.render(f"Damage: +{item.damage}", True, RED), (gx + 15, y))
            elif getattr(item, 'defense', 0):
                self.screen.blit(self.font_sm.render(f"Defense: +{item.defense}", True, BLUE), (gx + 15, y))
            elif getattr(item, 'heal', 0):
                self.screen.blit(self.font_sm.render(f"Heals: {item.heal} HP", True, GREEN), (gx + 15, y))

        hint = self.font_sm.render("[Enter] Give  [Escape] Cancel", True, (150, 150, 170))
        self.screen.blit(hint, (gx + gw // 2 - hint.get_width() // 2, gy + gh - 22))


    def handle_gift_input(self, key, player: Player) -> Optional[Item]:
        """Handle gift selection input. Returns the given item or None."""
        if not self.gift_active or not self.gift_npc:
            return None

        items = list(player.inventory)

        if key == pygame.K_UP:
            self.gift_selected = max(0, self.gift_selected - 1)
        elif key == pygame.K_DOWN:
            self.gift_selected = min(len(items) - 1, self.gift_selected + 1) if items else 0
        elif key == pygame.K_RETURN or key == pygame.K_e:
            if items and self.gift_selected < len(items):
                item = items[self.gift_selected]
                # Remove item from player inventory
                player.inventory.remove(item)
                # Adjust selection
                new_items = list(player.inventory)
                if self.gift_selected >= len(new_items):
                    self.gift_selected = max(0, len(new_items) - 1)
                if not new_items:
                    self.gift_active = False
                    self.gift_npc = None
                return item
        elif key == pygame.K_ESCAPE:
            self.gift_active = False
            self.gift_npc = None
        return None

    # ================================================================
    # INVENTORY (expanded)
    # ================================================================

    # Inventory category definitions
    _INV_CATEGORIES = [
        ("All", None),
        ("Weapons", ITEM_WEAPON),
        ("Armor", ITEM_ARMOR),
        ("Consumables", ITEM_CONSUMABLE),
        ("Materials", ITEM_RESOURCE),
        ("Quest", ITEM_QUEST),
        ("Tools/Other", ITEM_TOOL),
    ]



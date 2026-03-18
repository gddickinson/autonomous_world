"""Entity rendering — NPCs, creatures, player, items."""

import pygame
import random
import math
from game.settings import *
from game.core.player import Player
from game.ui.character_anim import (
    get_anim, update_anim, draw_npc_body, draw_creature_body
)
from game.ui.player_anim import draw_player_body


class RendererEntitiesMixin:

    """Mixin — see parent class for context."""

    def draw_ground_items(self, items: list, camera: Camera):
        """Draw items on the ground."""
        for gx, gy, item in items:
            sx, sy = camera.world_to_screen(gx, gy)
            if -TILE_SIZE < sx < SCREEN_WIDTH + TILE_SIZE and -TILE_SIZE < sy < SCREEN_HEIGHT + TILE_SIZE:
                # Simple colored square for items
                color = {
                    ITEM_WEAPON: YELLOW,
                    ITEM_ARMOR: LIGHT_GRAY,
                    ITEM_CONSUMABLE: GREEN,
                    ITEM_RESOURCE: ORANGE,
                    ITEM_QUEST: (200, 100, 255),
                }.get(item.kind, WHITE)

                isz = max(3, TILE_SIZE // 4)
                pygame.draw.rect(self.screen, color,
                                (int(sx) - isz, int(sy) - isz, isz * 2, isz * 2))
                pygame.draw.rect(self.screen, WHITE,
                                (int(sx) - isz, int(sy) - isz, isz * 2, isz * 2), 1)

    def draw_player(self, player: Player, camera: Camera):
        """Draw the player character with NPC-style body parts."""
        sx, sy = camera.world_to_screen(player.x, player.y)

        # Offset player sprite when on a non-ground floor
        cur_floor = getattr(player, 'current_floor', 0)
        if cur_floor != 0 and getattr(player, '_current_building_rect', None):
            pixels_per_floor = TILE_SIZE // 2
            sy += -cur_floor * pixels_per_floor

        s = max(1, TILE_SIZE // 4)
        player._last_dt = getattr(self, '_last_dt', 0.016)
        draw_player_body(self.screen, player, int(sx), int(sy), s)

        # Spawn swing arc on attack (renderer-specific effect)
        attack_timer = getattr(player, 'attack_timer', 0)
        if attack_timer > PLAYER_ATTACK_COOLDOWN * 0.9:
            fx, fy = player.facing
            self.spawn_swing_arc(player.x, player.y, fx, fy)

    def draw_npcs(self, npcs: list, camera: Camera, player: Player, visible_tiles=None):
        """Draw NPCs (only if in player's field of view)."""
        for npc in npcs:
            # FOV check
            if visible_tiles and (int(npc.x), int(npc.y)) not in visible_tiles:
                continue

            sx, sy = camera.world_to_screen(npc.x, npc.y)
            if not (-TILE_SIZE < sx < SCREEN_WIDTH + TILE_SIZE and
                    -TILE_SIZE < sy < SCREEN_HEIGHT + TILE_SIZE):
                continue

            # Animated body parts
            s = max(1, TILE_SIZE // 4)
            bw, bh = s * 4, s * 5
            update_anim(npc, getattr(self, '_last_dt', 0.016))
            draw_npc_body(self.screen, npc, int(sx), int(sy), s)

            # Consciousness glow
            if npc.consciousness > 0:
                glow_color = CONSCIOUSNESS_COLORS.get(npc.consciousness, (140, 140, 200))
                gr = max(4, s * 3)
                glow_surf = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*glow_color, 60), (gr, gr), gr)
                self.screen.blit(glow_surf, (int(sx) - gr, int(sy) - bh // 2 - gr // 2))

            # Quest marker
            if npc.has_quest_marker and npc.quest and not npc.quest.turned_in:
                marker_color = YELLOW if not npc.quest.completed else GREEN
                qy = int(sy) - bh // 2 - s * 3
                pygame.draw.polygon(self.screen, marker_color, [
                    (int(sx), qy), (int(sx) - s, qy + s * 2), (int(sx) + s, qy + s * 2)])
                pygame.draw.circle(self.screen, marker_color, (int(sx), qy - max(1, s // 2)), max(1, s // 2))

            # Name (when close)
            dist = player.dist_to(npc)
            if dist < 6:
                name_surf = self.font_sm.render(npc.name, True, WHITE)
                self.screen.blit(name_surf,
                                (int(sx) - name_surf.get_width() // 2, int(sy) - bh // 2 - s * 2))

            # Action indicator
            action_icons = {
                "sleeping": ("z z z", (150, 150, 200)),
                "talking": ("...", (200, 200, 100)),
                "chopping": ("*chop*", (180, 140, 80)),
                "mining": ("*mine*", (160, 160, 180)),
                "building": ("*build*", (180, 160, 100)),
                "farming": ("*farm*", (100, 180, 80)),
                "fishing": ("*fish*", (100, 150, 200)),
                "foraging": ("*forage*", (120, 180, 100)),
                "fighting": ("!!!", (220, 60, 60)),
                "fleeing": ("!!!", (220, 160, 40)),
                "smithing": ("*smith*", (200, 140, 60)),
                "guarding": ("*guard*", (140, 160, 200)),
                "hunting": ("*hunt*", (160, 200, 100)),
                "carrying": ("*carry*", (180, 160, 80)),
                "commuting": ("*walk*", (140, 140, 140)),
                "trading": ("*trade*", (200, 180, 60)),
                "performing": ("*play*", (180, 120, 180)),
                "researching": ("*study*", (120, 120, 200)),
                "praying": ("*pray*", (180, 180, 140)),
                "training": ("*train*", (200, 140, 100)),
                "healing": ("*heal*", (100, 200, 140)),
                # Goods transport actions
                "carrying_food": ("*food*", (200, 180, 80)),
                "carrying_ore": ("*ore*", (160, 140, 120)),
                "carrying_wood": ("*wood*", (140, 100, 50)),
                "carrying_goods": ("*cargo*", (180, 160, 100)),
                "loading": ("*load*", (180, 150, 100)),
                "clearing_rubble": ("*clear*", (130, 120, 110)),
                "road_building": ("*road*", (160, 150, 120)),
                "digging": ("*dig*", (140, 120, 80)),
            }
            act = getattr(npc, 'current_action', npc.state)
            if act in action_icons:
                label, color = action_icons[act]
                act_surf = self.font_sm.render(label, True, color)
                self.screen.blit(act_surf, (int(sx) + 10, int(sy) - 24))

            # Cargo indicator — small colored square above head when carrying goods
            _ws = getattr(npc, '_work_state', None)
            if _ws and getattr(_ws, 'carrying', None):
                cargo_item = _ws.carrying.get("item", "")
                cargo_colors = {
                    "food": (200, 180, 80), "ore": (160, 140, 120),
                    "wood": (140, 100, 50), "weapons": (180, 180, 200),
                    "tools": (160, 160, 140), "stone": (140, 140, 140),
                    "clothing": (180, 120, 160), "gold": (220, 200, 60),
                }
                cargo_labels = {
                    "food": "F", "ore": "O", "wood": "W",
                    "weapons": "X", "tools": "T", "stone": "S",
                    "clothing": "C", "gold": "G",
                }
                cc = cargo_colors.get(cargo_item, (180, 160, 100))
                cl = cargo_labels.get(cargo_item, "?")
                # Draw small filled square with letter
                cx_pos, cy_pos = int(sx), int(sy) - bh // 2 - s * 3
                pygame.draw.rect(self.screen, cc,
                                 (cx_pos - 4, cy_pos - 4, 8, 8))
                pygame.draw.rect(self.screen, (40, 40, 40),
                                 (cx_pos - 4, cy_pos - 4, 8, 8), 1)
                cargo_surf = self.font_sm.render(cl, True, (40, 40, 40))
                self.screen.blit(cargo_surf,
                                 (cx_pos - cargo_surf.get_width() // 2,
                                  cy_pos - cargo_surf.get_height() // 2))

            # Speech bubble for NPCs wanting to talk or approaching player
            if getattr(npc, 'wants_to_talk', False) or getattr(npc, 'current_action', '') == 'approaching_player':
                pygame.draw.ellipse(self.screen, WHITE, (int(sx) - 10, int(sy) - 40, 20, 14))
                pygame.draw.ellipse(self.screen, DARK_GRAY, (int(sx) - 10, int(sy) - 40, 20, 14), 1)
                bang = self.font_sm.render("!", True, RED)
                self.screen.blit(bang, (int(sx) - 3, int(sy) - 39))

            # Rich NPCs: gold-tinted name
            npc_gold = getattr(npc, 'npc_gold', 0)
            if npc_gold > 100 and dist < 6:
                # Re-draw name with gold tint (overwrites the white name drawn above)
                name_surf = self.font_sm.render(npc.name, True, (255, 215, 80))
                self.screen.blit(name_surf,
                                (int(sx) - name_surf.get_width() // 2, int(sy) - bh // 2 - s * 2))

            # Party indicator
            if getattr(npc, 'party_id', None):
                party_color = (100, 200, 255) if getattr(npc, 'party_role', '') == 'leader' else (80, 160, 200)
                pygame.draw.circle(self.screen, party_color, (int(sx) + 10, int(sy) - 16), 3)

            # Mood indicator (small colored dot) and emotion icons
            npc_mood = getattr(npc, 'mood', 0)
            if abs(npc_mood) > 0.2 and dist < 6:
                mood_color = (50, 200, 50) if npc_mood > 0 else (200, 80, 50)
                pygame.draw.circle(self.screen, mood_color, (int(sx) - 10, int(sy) - 16), 3)

            # Emotion/interaction icons above head (when close enough to see)
            if dist < 8:
                self._draw_npc_emotion_icon(npc, sx, sy, bh, s)

            # Social trait hint when very close
            if dist < 3:
                traits = getattr(npc, 'social_traits', [])
                if traits:
                    trait_text = self.font_sm.render(", ".join(traits[:2]), True, (140, 140, 160))
                    self.screen.blit(trait_text, (int(sx) - trait_text.get_width() // 2, int(sy) + 18))

            # Need bars (only when close and needs are low)
            if dist < 8:
                self._draw_npc_needs(npc, int(sx), int(sy))

    def draw_creatures(self, creatures: list, camera: Camera, visible_tiles=None):
        """Draw creatures (only if in player's field of view)."""
        for creature in creatures:
            if not creature.alive:
                continue

            # FOV check
            if visible_tiles and (int(creature.x), int(creature.y)) not in visible_tiles:
                continue

            sx, sy = camera.world_to_screen(creature.x, creature.y)
            if not (-TILE_SIZE < sx < SCREEN_WIDTH + TILE_SIZE and
                    -TILE_SIZE < sy < SCREEN_HEIGHT + TILE_SIZE):
                continue

            # Animated creature body
            s = max(1, TILE_SIZE // 4)
            update_anim(creature, getattr(self, '_last_dt', 0.016))
            draw_creature_body(self.screen, creature, int(sx), int(sy), s)

    def _draw_npc_needs(self, npc, sx: int, sy: int):
        """Draw small need indicators above NPC when they're low."""
        needs = getattr(npc, 'needs', None)
        if not needs:
            return
        bar_y = sy + 14
        bar_w = 20
        bar_h = 2
        need_colors = {"hunger": (200, 80, 80), "thirst": (80, 120, 200),
                       "rest": (200, 200, 80), "social": (200, 120, 200)}
        for need_name in ("hunger", "thirst", "rest"):
            val = needs.get(need_name, 100)
            if val < 45:
                bx = sx - bar_w // 2
                pygame.draw.rect(self.screen, (30, 30, 30), (bx, bar_y, bar_w, bar_h))
                fill = max(1, int(bar_w * val / 100))
                pygame.draw.rect(self.screen, need_colors[need_name], (bx, bar_y, fill, bar_h))
                bar_y += 3

    def draw_trade_caravans(self, goods_transport, camera: Camera):
        """Draw trade caravans as cart/wagon sprites on the map."""
        if not goods_transport:
            return
        for caravan in goods_transport.trade_caravans:
            if caravan.destroyed or caravan.phase == "done":
                continue
            sx, sy = camera.world_to_screen(caravan.x, caravan.y)
            if not (-30 < sx < SCREEN_WIDTH + 30 and
                    -30 < sy < SCREEN_HEIGHT + 30):
                continue

            # Draw vehicle body (larger rect for wagon, smaller for cart)
            vcolors = {
                "handcart": ((160, 130, 80), 6),
                "cart": ((140, 110, 70), 8),
                "wagon": ((120, 90, 50), 12),
                "supply_wagon": ((110, 85, 45), 14),
            }
            color, size = vcolors.get(caravan.vehicle_type, ((140, 110, 70), 8))
            hw = size
            hh = size // 2 + 2
            # Vehicle body
            pygame.draw.rect(self.screen, color,
                             (int(sx) - hw, int(sy) - hh, hw * 2, hh * 2))
            pygame.draw.rect(self.screen, (80, 60, 40),
                             (int(sx) - hw, int(sy) - hh, hw * 2, hh * 2), 1)
            # Wheels (small dark circles)
            woff = hw - 2
            for wx in (-woff, woff):
                pygame.draw.circle(self.screen, (60, 50, 40),
                                   (int(sx) + wx, int(sy) + hh), 3)

            # Cargo label
            total = sum(caravan.goods.values())
            if total > 0:
                goods_list = list(caravan.goods.keys())
                lbl = f"{total}x {goods_list[0][:3]}" if goods_list else ""
                lbl_surf = self.font_sm.render(lbl, True, (220, 210, 180))
                self.screen.blit(lbl_surf,
                                 (int(sx) - lbl_surf.get_width() // 2,
                                  int(sy) - hh - 12))

    def draw_transport_ground_items(self, goods_transport, camera: Camera):
        """Draw goods dropped on the ground (from transport system) as small colored diamonds."""
        if not goods_transport:
            return
        ground_colors = {
            "food": (200, 180, 80), "ore": (160, 140, 120),
            "wood": (140, 100, 50), "weapons": (180, 180, 200),
            "tools": (160, 160, 140), "stone": (140, 140, 140),
        }
        for item in goods_transport.ground_items:
            sx, sy = camera.world_to_screen(item.x, item.y)
            if not (-10 < sx < SCREEN_WIDTH + 10 and
                    -10 < sy < SCREEN_HEIGHT + 10):
                continue
            color = ground_colors.get(item.good, (180, 160, 100))
            # Small diamond shape
            pts = [(int(sx), int(sy) - 4), (int(sx) + 4, int(sy)),
                   (int(sx), int(sy) + 4), (int(sx) - 4, int(sy))]
            pygame.draw.polygon(self.screen, color, pts)
            pygame.draw.polygon(self.screen, (60, 50, 40), pts, 1)
            # Quantity label
            lbl = self.font_sm.render(f"{item.quantity}", True, color)
            self.screen.blit(lbl, (int(sx) + 5, int(sy) - 6))



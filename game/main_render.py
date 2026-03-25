"""Main game rendering and update loop."""

import pygame
import random
import math
from game.settings import *


class GameRenderMixin:

    """Mixin — see parent class for context."""

    def _draw_combat_ui(self):  # noqa: C901
        """Draw real-time combat HUD overlay (non-blocking)."""
        if not self.combat.active:
            return

        font_sm = self.renderer.font_sm

        # Combat log panel (bottom-right, compact)
        pw, ph = 260, 140
        px = SCREEN_WIDTH - pw - 10
        py = SCREEN_HEIGHT - ph - 60

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 10, 25, 180))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, (120, 50, 50), (px, py, pw, ph), 1)

        # Target info
        target = self.combat.player_state.target
        y = py + 4
        if target and getattr(target, 'alive', False):
            name = getattr(target, 'name', getattr(target, 'kind', '?'))
            hp = getattr(target, 'hp', 0)
            maxhp = getattr(target, 'max_hp', 1)
            self.screen.blit(font_sm.render(f"Target: {name} HP:{hp}/{maxhp}", True, RED), (px + 5, y))

            # Target HP bar
            y += 14
            bar_w = pw - 10
            pygame.draw.rect(self.screen, DARK_GRAY, (px + 5, y, bar_w, 6))
            hp_w = int(bar_w * hp / max(1, maxhp))
            pygame.draw.rect(self.screen, RED, (px + 5, y, hp_w, 6))
            y += 10

            # Highlight target on map
            tsx, tsy = self.camera.world_to_screen(target.x, target.y)
            pygame.draw.circle(self.screen, RED, (int(tsx), int(tsy)), 12, 2)
        else:
            self.screen.blit(font_sm.render("No target", True, GRAY), (px + 5, y))
            y += 14

        # Combat log (last few entries)
        y += 4
        for msg in self.combat.combat_log[-6:]:
            color = RED if "hit" in msg.lower() or "damage" in msg.lower() else \
                    (150, 150, 150) if "miss" in msg.lower() else GREEN
            text = msg[:32] if len(msg) > 32 else msg
            self.screen.blit(font_sm.render(text, True, color), (px + 5, y))
            y += 12

        # Instructions
        self.screen.blit(font_sm.render("[Space] Attack  [Esc] Disengage", True, (140, 140, 160)),
                        (px + 5, py + ph - 14))
        return

    def _draw_combat_ui_OLD(self):
        """Draw tactical combat overlay."""
        font_md = self.renderer.font_md
        font_sm = self.renderer.font_sm

        # Combat panel (right side)
        pw, ph = 280, SCREEN_HEIGHT - 20
        px = SCREEN_WIDTH - pw - 10
        py = 10
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 10, 25, 220))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, (100, 50, 50), (px, py, pw, ph), 2)

        # Title
        title = font_md.render("TACTICAL COMBAT", True, RED)
        self.screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 5))

        # Turn order
        y = py + 30
        cc = self.combat.current_combatant
        for c in self.combat.turn_order:
            if not c.is_alive:
                continue
            is_current = c is cc
            color = YELLOW if is_current else (WHITE if (c.is_player or c.is_ally) else (200, 100, 100))
            marker = "> " if is_current else "  "
            side = "YOU" if c.is_player else ("ALLY" if c.is_ally else "FOE")
            text = f"{marker}{c.name} [{side}] HP:{c.entity.hp}/{c.entity.max_hp}"
            self.screen.blit(font_sm.render(text, True, color), (px + 5, y))
            y += 16

        # Current turn info
        if cc and (cc.is_player or cc.is_ally):
            y += 10
            pygame.draw.line(self.screen, (80, 80, 100), (px + 5, y), (px + pw - 5, y))
            y += 8
            self.screen.blit(font_md.render(f"{cc.name}'s Turn", True, YELLOW), (px + 10, y))
            y += 22

            # Resources
            res = []
            if cc.has_action:
                res.append("ACTION")
            if cc.has_bonus_action:
                res.append("BONUS")
            self.screen.blit(font_sm.render(f"Available: {', '.join(res) or 'None'}", True, UI_TEXT), (px + 10, y))
            y += 16
            self.screen.blit(font_sm.render(f"Movement: {cc.movement_remaining:.0f} tiles", True, UI_TEXT), (px + 10, y))
            y += 20

            # Actions
            self.screen.blit(font_sm.render("Actions:", True, UI_HIGHLIGHT), (px + 10, y))
            y += 16
            action_keys = [
                ("[1] Attack nearest", "attack"),
                ("[2] Cast spell", "spell"),
                ("[3] Dash", "dash"),
                ("[4] Dodge", "dodge"),
                ("[5] Use item", "item"),
                ("[Enter] End turn", "end"),
                ("[Esc] Flee combat", "flee"),
            ]
            for label, _ in action_keys:
                self.screen.blit(font_sm.render(label, True, (180, 180, 190)), (px + 15, y))
                y += 14

        # Combat log (bottom of panel)
        y = py + ph - 120
        pygame.draw.line(self.screen, (80, 80, 100), (px + 5, y), (px + pw - 5, y))
        y += 5
        self.screen.blit(font_sm.render("Combat Log:", True, GRAY), (px + 10, y))
        y += 14
        for msg in self.combat.combat_log[-6:]:
            color = RED if "damage" in msg.lower() or "hit" in msg.lower() else \
                    GREEN if "heal" in msg.lower() or "victory" in msg.lower() else UI_TEXT
            text = msg[:35] if len(msg) > 35 else msg
            self.screen.blit(font_sm.render(text, True, color), (px + 10, y))
            y += 13

        # Highlight current combatant on map
        if cc:
            sx, sy = self.camera.world_to_screen(cc.entity.x, cc.entity.y)
            pygame.draw.circle(self.screen, YELLOW, (int(sx), int(sy)), 18, 2)

    # Old turn-based combat handler removed - combat is now real-time

    def _update(self, dt: float):
        # Auto-play mode: AI controls the player
        if self.auto_play:
            actions.auto_play_update(self, dt)
        else:
            # Manual player movement
            keys = pygame.key.get_pressed()
            self.player.vx = 0
            self.player.vy = 0
            if not self.ui.any_panel_open:
                if keys[pygame.K_w] or keys[pygame.K_UP]:    self.player.vy = -1
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:  self.player.vy = 1
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.player.vx = -1
                if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.player.vx = 1

                # Speed controls: Shift=run, Ctrl=sneak, default=walk
                if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                    if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                        self.player.current_gait = "sprint"
                    else:
                        self.player.current_gait = "run"
                elif keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                    self.player.current_gait = "sneak"
                elif self.player.vx != 0 or self.player.vy != 0:
                    self.player.current_gait = "jog" if (keys[pygame.K_CAPSLOCK]) else "walk"
                else:
                    self.player.current_gait = "walk"

        # Handle player movement — interior or overworld
        interior_state = getattr(self.player, 'interior_state', None)
        if interior_state and interior_state.is_inside and interior_state.current_interior:
            # Move in interior space
            interior = interior_state.current_interior
            if self.player.vx != 0 or self.player.vy != 0:
                mag = math.sqrt(self.player.vx**2 + self.player.vy**2)
                if mag > 0:
                    nx = self.player.vx / mag
                    ny = self.player.vy / mag
                    self.player.facing = (nx, ny)
                    from game.systems.physical import get_gait_speed
                    speed = get_gait_speed(self.player, self.player.current_gait) * 0.7
                    new_x = interior_state.interior_x + nx * speed * dt
                    new_y = interior_state.interior_y + ny * speed * dt
                    # Check walkability in interior
                    if interior.is_walkable(int(new_x), int(interior_state.interior_y)):
                        interior_state.interior_x = new_x
                    if interior.is_walkable(int(interior_state.interior_x), int(new_y)):
                        interior_state.interior_y = new_y

            # Update interior NPCs — they move around doing activities
            from game.systems.interiors import update_interior_npcs
            tod = getattr(self.time_sys, 'normalized', 0.3)
            update_interior_npcs(interior, dt, tod)
        else:
            if self.auto_play:
                # During autoplay, navigate_toward handles movement directly.
                # Only update cooldowns/energy/regen, not velocity-based movement.
                self.player.vx = 0
                self.player.vy = 0
            self.player.update(dt, self.world)

            # Underground exploration — reveal tiles around player
            if getattr(self.player, 'current_floor', 0) < 0:
                px, py = int(self.player.x), int(self.player.y)
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        self.player._underground_explored.add((px + dx, py + dy))

        # Track which building the player is inside (for roof removal in 2D)
        # Only recalculate when player moves to a new tile position
        px_int, py_int = int(self.player.x), int(self.player.y)
        _last_pos = getattr(self, '_last_building_check_pos', None)
        in_building = False
        if _last_pos == (px_int, py_int):
            # Position unchanged — use cached result
            in_building = getattr(self.player, '_current_building_name', '') != ''
        elif hasattr(self.world, 'plan'):
            self._last_building_check_pos = (px_int, py_int)
            for sp in self.world.plan.settlements:
                # Quick AABB check: skip settlements far from player
                if abs(sp.x - px_int) > sp.radius + 20 or abs(sp.y - py_int) > sp.radius + 20:
                    continue
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    if bx <= px_int < bx + bw and by <= py_int < by + bh:
                        self.player._current_building_name = sp.name
                        self.player._current_building_kind = sp.kind
                        self.player._current_building_rect = (bx, by, bw, bh)
                        in_building = True
                        break
                if in_building:
                    break
        else:
            self._last_building_check_pos = (px_int, py_int)
        if not in_building:
            # Only reset floor if player is on ground level.
            # If underground, keep building tracking so the underground
            # renderer knows which building to show.
            if self.player.current_floor == 0:
                self.player._current_building_name = ""
                self.player._current_building_kind = ""
                self.player._current_building_rect = None
            # If on non-ground floor but outside building bounds,
            # force back to ground (player somehow escaped)
            elif self.player.current_floor != 0:
                self.player.current_floor = 0
                self.player._current_building_name = ""
                self.player._current_building_kind = ""
                self.player._current_building_rect = None

        # Update mount (stamina, hunger, thirst, death check)
        from game.systems.physical import update_mount
        update_mount(self.player, dt, self.world)
        # Check for mount death
        if hasattr(self.player, '_mount_died'):
            self.notifications.add(
                f"Your mount {self.player._mount_died} has died!", 5.0, RED)
            del self.player._mount_died

        # Update party companions
        self.party.update(dt, self.player, self.world)

        # Real-time combat update (runs alongside everything else - no freeze)
        if self.combat.active:
            # Snapshot damage state before update for screen shake / HP bars
            _pre_hp = {}
            if self.combat.player_state.target:
                _t = self.combat.player_state.target
                _pre_hp[id(_t)] = (getattr(_t, 'hp', 0), _t)
            self.combat.update(dt, self.player, self.party.companions,
                              self.world_mgr.creatures, self.world_mgr.npcs, self.world)
            # Detect damage dealt this frame -> screen shake + HP bar
            for eid, (old_hp, ent) in _pre_hp.items():
                new_hp = getattr(ent, 'hp', old_hp)
                dmg = old_hp - new_hp
                if dmg > 0:
                    # Screen shake on big hits
                    if hasattr(self.renderer, 'trigger_screen_shake'):
                        self.renderer.trigger_screen_shake(int(dmg))
                    # Mark entity for HP bar display
                    if hasattr(self.renderer, 'mark_hp_bar_target'):
                        self.renderer.mark_hp_bar_target(ent)
                    # Damage popup
                    if hasattr(self.renderer, 'spawn_damage_popup'):
                        self.renderer.spawn_damage_popup(ent.x, ent.y, int(dmg))
            # Also mark current target for HP bar
            if self.combat.player_state.target and hasattr(self.renderer, 'mark_hp_bar_target'):
                self.renderer.mark_hp_bar_target(self.combat.player_state.target)

            # Handle kills: drops, particles, quests
            for c in self.world_mgr.creatures:
                if not c.alive and self.player.dist_to(c) < 10:
                    if hasattr(c, '_death_handled'):
                        continue
                    c._death_handled = True
                    self.renderer.spawn_hit_particles(c.x, c.y)
                    self.renderer.spawn_xp_particles(c.x, c.y)
                    if hasattr(self.renderer, 'spawn_death_effect'):
                        self.renderer.spawn_death_effect(c.x, c.y)
                    self.quest_sys.on_kill(c.kind)
                    # Multiplayer: broadcast quest kill progress
                    if hasattr(self, '_mp_broadcast_quest_kill'):
                        for q in self.quest_sys.active_quests:
                            if q.target == c.kind and not q.completed:
                                self._mp_broadcast_quest_kill(q, self.player.name)
                                break
                    # Quest trigger: defend quests when creature dies near settlement
                    for s in self.world.structures:
                        if s.kind in ("village", "town", "city", "hamlet", "castle"):
                            if abs(c.x - s.x) < 25 and abs(c.y - s.y) < 25:
                                self.quest_sys.on_defend_success(s.name)
                                break
                    drops = c.get_drops()
                    if drops:
                        self.world_mgr.drop_items(c.x, c.y, drops)

        # Pick up pending spell visuals from player and combat system
        if hasattr(self.renderer, 'spawn_spell_effect'):
            # From magic system (via cast_spell on player)
            pending = getattr(self.player, '_pending_spell_visuals', [])
            for vis in pending:
                self.renderer.spawn_spell_effect(
                    vis["spell_name"], vis["x"], vis["y"],
                    vis.get("target_x"), vis.get("target_y"))
            if pending:
                self.player._pending_spell_visuals = []
            # From tactical combat system
            tc_pending = getattr(self.combat, '_pending_spell_visuals', [])
            for vis in tc_pending:
                self.renderer.spawn_spell_effect(
                    vis["spell_name"], vis["x"], vis["y"],
                    vis.get("target_x"), vis.get("target_y"))
            if tc_pending:
                self.combat._pending_spell_visuals = []

        if not self.player.alive:
            if self.player_mode == "god":
                self.player.alive = True
                self.player.hp = 99999
            elif getattr(self.player, 'ghost', False):
                # Already a ghost, check if at spawn temple to respawn
                sx, sy = self.world.spawn_point
                if self.player.dist_to_pos(sx, sy) < 3:
                    self.player.alive = True
                    self.player.ghost = False
                    self.player.hp = self.player.max_hp
                    self.player.mode = "mortal"
                    self.player_mode = "mortal"
                    self.notifications.add("You have been reborn at the Temple of Awakening!", 5.0, GREEN)
                else:
                    self.player.alive = True  # ghosts are always "alive" for movement
            else:
                # Mortal died -> become ghost
                self.player.alive = True
                self.player.ghost = True
                self.player.mode = "ghost"
                self.player_mode = "ghost"
                self.player.speed = PLAYER_SPEED * 2
                self.notifications.add("You have died and become a ghost...", 5.0, (150, 150, 220))
                self.notifications.add("Return to the Temple of Awakening (world center) to be reborn.", 8.0, (150, 150, 220))
                self.dead = False  # don't show death screen, just become ghost

        self.camera.update(self.player.x, self.player.y)
        self.time_sys.update(dt)
        # Store normalized time on world for renderer shadow calculations
        self.world._time_normalized = getattr(self.time_sys, 'normalized',
                                               self.time_sys.time / DAY_LENGTH)
        self.world_mgr.update(dt, self.player, self.time_sys.time)
        self.simulation.update(dt, self.player)

        # Filtered events - only show what the player can witness nearby
        all_events = self.simulation.get_event_log()
        if all_events:
            # Record notable events in the chronicle
            for msg in all_events:
                classified = classify_event(msg)
                if classified:
                    cat, title, importance = classified
                    self.chronicles.record(
                        self.time_sys.day, cat, title, msg, importance)

            visible = self.simulation.info.filter_events_for_player(
                all_events, self.player, self.world_mgr.npcs, radius=20)
            for msg, color in visible:
                self.notifications.add(msg, 4.0, color)

        # Information spreading (NPCs near player share gossip)
        self.simulation.info.update(dt, self.world_mgr.npcs, self.player,
                                    self.simulation.npc_grid, self.time_sys.day)

        # Exploration
        if self.player.vx != 0 or self.player.vy != 0:
            self.player.gain_skill_xp("navigation", 0.01 * dt)

        # FOV - cached by tile position to avoid recomputing every frame
        _px_fov, _py_fov = int(self.player.x), int(self.player.y)
        _fov_moved = (_px_fov, _py_fov) != getattr(self, '_last_fov_pos', None)

        if _fov_moved:
            self._last_fov_pos = (_px_fov, _py_fov)
            self.world.reveal_around(_px_fov, _py_fov, 8)

        if self.player_mode == "god":
            self.visible_tiles = None  # None = everything visible
        elif _fov_moved:
            if self.player_mode == "ghost":
                self.fov_radius = 20  # ghosts see further
                self.visible_tiles = compute_fov_set(
                    _px_fov, _py_fov, self.fov_radius, self.world)
                # Ghosts also see through walls in a small radius
                for dy in range(-8, 9):
                    for dx in range(-8, 9):
                        if dx*dx + dy*dy <= 64:
                            self.visible_tiles.add((_px_fov + dx, _py_fov + dy))
            else:
                self.visible_tiles = compute_fov_set(
                    _px_fov, _py_fov, self.fov_radius, self.world)

        # Nearby NPC — use spatial grid for efficient lookup
        self.nearby_npc = None
        best_dist = NPC_INTERACTION_RANGE
        _nearby_npcs = self.simulation.npc_grid.get_nearby(
            self.player.x, self.player.y, NPC_INTERACTION_RANGE)
        for npc in _nearby_npcs:
            if not npc.alive:
                continue
            d = self.player.dist_to(npc)
            if d < best_dist:
                best_dist = d
                self.nearby_npc = npc

        # NPC-initiated interaction — use spatial grid
        if not self.ui.any_panel_open:
            for npc in _nearby_npcs:
                if getattr(npc, 'wants_to_talk', False) and npc.alive:
                    if self.player.dist_to(npc) < NPC_CONVERSATION_RANGE + 1:
                        reason = getattr(npc, 'talk_reason', 'wants to speak with you')
                        cls_info = f"{getattr(npc, 'race', '')} {getattr(npc, 'char_class', npc.profession)}"
                        self.notifications.add(f'{npc.name} ({cls_info}): "{reason}"', 6.0, YELLOW)
                        npc.wants_to_talk = False
                        self.nearby_npc = npc
                        break

        # Trespass detection
        trespass_msg = self.building_sys.check_trespass(
            self.player, self.world_mgr.npcs, self.time_sys.time)
        if trespass_msg:
            self.notifications.add(trespass_msg, 4.0, RED)

        # Location banner
        structure = self.world.get_structure_at(self.player.x, self.player.y)
        loc_name = structure.name if structure else ""
        if loc_name and loc_name != self.current_location:
            self.current_location = loc_name
            self.location_banner = loc_name
            self.location_banner_timer = 3.0
            # Quest trigger: on_reach_location for investigate/escort/diplomacy
            self.quest_sys.on_reach_location(loc_name)
        elif not loc_name:
            self.current_location = ""
        if self.location_banner_timer > 0:
            self.location_banner_timer -= dt

        # Examine timer
        if self.examine_timer > 0:
            self.examine_timer -= dt
            if self.examine_timer <= 0:
                self.examine_text = ""

        actions.update_llm(self, dt)
        self.notifications.update(dt)
        self.screenshots.update(dt)

        # Multiplayer network sync
        if self.net_server or self.net_client:
            self._update_multiplayer(dt)

        # Auto-save
        if self.config["auto_save"]:
            self.auto_save_timer += dt
            interval = self.config["auto_save_interval"] * 60  # minutes -> seconds
            if self.auto_save_timer >= interval:
                self.auto_save_timer = 0.0
                self._save_game()

        if self.attack_flash_timer > 0:
            self.attack_flash_timer -= dt

    # ================================================================
    # DRAW
    # ================================================================

    def _draw(self):
        is_3d = self.view_mode == "3d"

        if not is_3d:
            self.screen.fill((10, 10, 20))

        # Check if player is inside a building
        interior_state = getattr(self.player, 'interior_state', None)
        if not is_3d and interior_state and interior_state.is_inside and interior_state.current_interior:
            # INTERIOR VIEW — draw the building interior instead of overworld
            self.renderer.draw_interior(interior_state.current_interior,
                                       self.player, self.camera)
            if interior_state.transitioning:
                interior_state.update_transition(1.0 / FPS)
                alpha = 255 - interior_state.transition_alpha
                if alpha > 0:
                    fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                    fade.fill((0, 0, 0))
                    fade.set_alpha(alpha)
                    self.screen.blit(fade, (0, 0))
        else:
            # OVERWORLD VIEW — use active renderer
            r = self.active_renderer
            dt = self.clock.get_time() / 1000.0

            # Apply screen shake offset to camera for this frame
            _shake_dx, _shake_dy = 0, 0
            if hasattr(r, 'get_screen_shake_offset'):
                _shake_dx, _shake_dy = r.get_screen_shake_offset(dt)
                if _shake_dx or _shake_dy:
                    self.camera.x += _shake_dx
                    self.camera.y += _shake_dy

            r.draw_world(self.world, self.camera, self.visible_tiles,
                         self.player)
            r.draw_building_doors(self.world, self.camera, self.player)
            r.draw_structures(self.world, self.camera)
            # Settlement overlay effects (awnings, walls, tavern glow, farm patterns)
            if hasattr(r, 'draw_settlement_overlays'):
                r.draw_settlement_overlays(self.world, self.camera, self.player)
            if hasattr(r, 'draw_farm_overlays'):
                r.draw_farm_overlays(self.world, self.camera)
            r.draw_ground_items(self.world_mgr.ground_items, self.camera)

            r.draw_creatures(self.world_mgr.creatures, self.camera, self.visible_tiles)
            r.draw_npcs(self.world_mgr.npcs, self.camera, self.player, self.visible_tiles)
            r.draw_player(self.player, self.camera)

            # Enemy health bars (combat polish)
            if hasattr(r, 'draw_enemy_hp_bars'):
                _all_entities = list(self.world_mgr.creatures) + list(self.world_mgr.npcs)
                r.draw_enemy_hp_bars(_all_entities, self.camera, dt)

            # Combat visual effects: damage popups, hit flashes, death effects, HP bars
            if hasattr(r, 'combat_fx'):
                r.combat_fx.update_and_draw(self.screen, self.camera, dt)
                r.combat_fx.draw_hp_bars(self.screen, self.camera, dt)

            # Overheard NPC conversation snippets (floating text)
            if hasattr(self, '_draw_conversation_snippets'):
                self._draw_conversation_snippets(dt)

            # Spell visual effects (combat polish)
            if hasattr(r, 'draw_spell_effects'):
                r.draw_spell_effects(self.camera, dt)

            # Draw remote multiplayer players
            if self.remote_players:
                self._draw_remote_players()

            # Footstep dust when player moves
            if hasattr(r, 'spawn_footstep_dust') and hasattr(r, '_last_player_pos'):
                px, py = self.player.x, self.player.y
                lp = r._last_player_pos
                if lp and (abs(px - lp[0]) > 0.05 or abs(py - lp[1]) > 0.05):
                    r._footstep_timer += self.clock.get_time() / 1000.0
                    if r._footstep_timer >= 0.25:
                        r._footstep_timer = 0.0
                        r.spawn_footstep_dust(px, py)
                r._last_player_pos = (px, py)

            r.draw_world_events(self.simulation.events, self.camera)
            if hasattr(r, 'draw_battle_visuals') and hasattr(self.simulation, 'battle_visuals'):
                r.draw_battle_visuals(self.simulation.battle_visuals, self.camera)
            # Draw goods transport visuals (trade caravans, ground items)
            _gt = getattr(self.simulation, 'goods_transport', None)
            if _gt and hasattr(r, 'draw_trade_caravans'):
                r.draw_trade_caravans(_gt, self.camera)
                r.draw_transport_ground_items(_gt, self.camera)
            # Draw graves and unburied bodies
            if hasattr(r, 'draw_graves') and hasattr(self.simulation, 'burial'):
                r.draw_graves(self.simulation.burial.graves, self.camera)
            r.draw_particles(self.camera, self.clock.get_time() / 1000.0, self.player)
            # Seasonal tile palette update (4 times per year)
            if hasattr(r, 'set_season') and hasattr(self.simulation, 'ecology'):
                r.set_season(self.simulation.ecology.season)
            # Bind vegetation/crop systems for per-tile color overrides
            if hasattr(r, 'set_vegetation_systems') and r._vegetation_sys is None:
                if hasattr(self.simulation, 'vegetation_sys'):
                    r.set_vegetation_systems(
                        self.simulation.vegetation_sys,
                        getattr(self.simulation, 'crop_system', None))
            # Weather visual effects (rain, snow, fog, storm)
            if hasattr(r, 'draw_weather') and hasattr(self.simulation, 'ecology'):
                _weather = self.simulation.ecology.weather
                r.draw_weather(_weather, self.camera, self.clock.get_time() / 1000.0)
            if not is_3d:  # night overlay uses pygame blit in 2D, GL in 3D
                r.draw_lighting(self.time_sys.normalized, self.camera, self.world)

            # Undo screen shake offset so camera is stable for HUD/UI
            if _shake_dx or _shake_dy:
                self.camera.x -= _shake_dx
                self.camera.y -= _shake_dy

            if not is_3d and interior_state and interior_state.transitioning:
                interior_state.update_transition(1.0 / FPS)

        # 3D mode: draw HUD via GL texture overlay
        if is_3d and hasattr(self, 'renderer_3d') and self.renderer_3d:
            # Basic stats HUD
            p = self.player
            lines = [
                f"HP: {int(p.hp)}/{p.max_hp}  Energy: {int(p.energy)}  "
                f"Gold: {p.gold}  Lv.{p.level}",
                f"FPS: {self.clock.get_fps():.0f}  "
                f"Radius: {self.renderer_3d.view_radius}  "
                f"3D View (V:switch  Arrows:camera  [/]:radius)",
            ]
            self.renderer_3d._draw_text_overlay(lines, 5, 5)
            # Time of day
            time_line = [f"Day {self.time_sys.day}  {self.time_sys._astro.get('season', 'Spring').title()}"]
            self.renderer_3d._draw_text_overlay(time_line, 5, SCREEN_HEIGHT - 25)
        elif not is_3d:
            if self.attack_flash_timer > 0:
                flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                flash.fill((255, 255, 255, int(30 * (self.attack_flash_timer / 0.15))))
                self.screen.blit(flash, (0, 0))

            self.ui.draw_hud(self.player, self.time_sys)
            self.active_renderer.draw_minimap(self.world, self.player,
                                              self.world_mgr.npcs, self.world_mgr.creatures,
                                              self.show_minimap)

        # 2D UI elements — skip in 3D mode (they use pygame.draw/blit)
        if not is_3d:
            if self.nearby_npc and not self.ui.any_panel_open:
                self.ui.draw_interaction_prompt(self.nearby_npc)

            if not self.ui.any_panel_open and not self.player.interior_state.is_inside:
                ppx, ppy = int(self.player.x), int(self.player.y)
                near_door = False
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        tx, ty = ppx + dx, ppy + dy
                        if (0 <= tx < self.world.width and 0 <= ty < self.world.height and
                            self.world.tiles[ty][tx] == DOOR):
                            structure = self.world.get_structure_at(float(tx), float(ty))
                            if structure:
                                prompt = self.active_renderer.font_sm.render(
                                    f"[E] Enter {structure.name}", True, (220, 220, 180))
                                bg = pygame.Surface((prompt.get_width() + 10, 20), pygame.SRCALPHA)
                                bg.fill((20, 20, 40, 200))
                                self.screen.blit(bg, (SCREEN_WIDTH // 2 - prompt.get_width() // 2 - 5,
                                                      SCREEN_HEIGHT - 70))
                                self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2,
                                                         SCREEN_HEIGHT - 68))
                                near_door = True
                                break
                    if near_door:
                        break
            if self.world_mgr.ground_items and not self.ui.any_panel_open:
                self.ui.draw_pickup_prompt(self.world_mgr.ground_items,
                                           self.player.x, self.player.y)

            if self.location_banner_timer > 0:
                self.ui.draw_location_banner(self.location_banner, min(1.0, self.location_banner_timer))
            if self.examine_text:
                self.ui.draw_examine(self.examine_text)

            self.ui.draw_notifications(self.notifications.notifications)
            self.ui.draw_dialog()
            self.ui.draw_text_input()
            if self.ui.shop_active:
                self.ui.draw_shop(self.player)
            if self.ui.gift_active:
                self.ui.draw_gift_panel(self.player)
            self.ui.draw_inventory(self.player)
            self.ui.draw_quest_log(self.quest_sys.active_quests)
            self.ui.draw_character_sheet(self.player)
            self.ui.draw_chronicle(self.chronicles)
            self.ui.draw_planet_view(1.0 / FPS, self.time_sys)

            # Quest tracker HUD (only when no panels are open)
            if not self.ui.any_panel_open:
                self.quest_tracker.draw(
                    self.screen, self.quest_sys.active_quests,
                    self.player, self.world)

            if self.ui.show_world_map:
                self.ui.world_map_view.update_scroll(1.0 / FPS)
                self.ui.world_map_view.draw(self.screen, self.world,
                                             self.player, self.world.structures)

            if self.combat.active:
                self._draw_combat_ui()

            # Phase 6: Settlement overview, combat log, fast travel panels
            economy_sys = getattr(self.simulation, 'economy', None)
            self.settlement_panel.draw(
                self.screen, self.world, self.player,
                self.world_mgr.npcs, self.chronicles, economy_sys)
            self.combat_log_panel.draw(self.screen)
            self.fast_travel_ui.draw(self.screen)

            # Pause menu is now handled by MenuSystem (blocking modal)
            # self.ui.draw_pause_menu() is no longer used
            if self.dead:
                self.ui.draw_death_screen()

            # Controls overlay (on top of everything)
            self.controls_overlay.draw(self.screen)

        # Mode indicator
        if self.player_mode == "ghost":
            mode_text = self.renderer.font_md.render("GHOST MODE", True, (150, 150, 220))
            self.screen.blit(mode_text, (SCREEN_WIDTH // 2 - mode_text.get_width() // 2, 48))
            # Distance to temple
            sx, sy = self.world.spawn_point
            dist = self.player.dist_to_pos(sx, sy)
            if dist > 5:
                dist_text = self.renderer.font_sm.render(
                    f"Temple: {dist:.0f} tiles  [E at temple to respawn]", True, (130, 130, 180))
                self.screen.blit(dist_text, (SCREEN_WIDTH // 2 - dist_text.get_width() // 2, 66))
        elif self.player_mode == "god":
            # Draw god mode UI (toolbar, overlay, panels)
            if hasattr(self, 'god_ui') and self.god_ui.active:
                self.god_ui.draw(self.screen)
            else:
                mode_text = self.renderer.font_md.render("GOD MODE", True, (255, 220, 100))
                self.screen.blit(mode_text, (SCREEN_WIDTH // 2 - mode_text.get_width() // 2, 48))
            # Claude hint (always show in god mode)
            if not self.claude_chat.visible:
                claude_hint = self.renderer.font_sm.render(
                    "[F9] Claude AI  [K] API Key  [~] Console  [F6] Tweaker  [F7] Reload", True, (160, 160, 200))
                self.screen.blit(claude_hint,
                                 (SCREEN_WIDTH - claude_hint.get_width() - 10, 50))

        # Auto-play indicator
        if self.auto_play:
            ap_text = self.renderer.font_md.render("AUTO-PLAY [P to disable]", True, YELLOW)
            ap_bg = pygame.Surface((ap_text.get_width() + 16, 24), pygame.SRCALPHA)
            ap_bg.fill((20, 20, 40, 200))
            self.screen.blit(ap_bg, (SCREEN_WIDTH // 2 - ap_text.get_width() // 2 - 8, 48))
            self.screen.blit(ap_text, (SCREEN_WIDTH // 2 - ap_text.get_width() // 2, 50))

        # Status bar
        if self.config["show_fps"]:
            fps = self.renderer.font_sm.render(f"FPS: {self.clock.get_fps():.0f}", True, GRAY)
            self.screen.blit(fps, (SCREEN_WIDTH - 80, SCREEN_HEIGHT - 20))

        llm_stats = self.llm.get_stats()
        llm_color = GREEN if llm_stats["enabled"] else GRAY
        llm_label = f"LLM: {llm_stats['provider']}"
        if llm_stats["enabled"]:
            llm_label += f" [{llm_stats['successful']}/{llm_stats['total_requests']}]"
        llm_text = self.renderer.font_sm.render(llm_label, True, llm_color)
        self.screen.blit(llm_text, (SCREEN_WIDTH - llm_text.get_width() - 10, SCREEN_HEIGHT - 35))

        # Multiplayer status and chat (drawn on top of game, below modals)
        if self.net_server or self.net_client:
            self._draw_multiplayer_status()
            self._draw_chat_log()

        # Claude chat and API key config (drawn on top of everything)
        if self.player_mode == "god":
            self.claude_chat.draw(self.screen)
            self.api_key_config.draw(self.screen)

        pygame.display.flip()




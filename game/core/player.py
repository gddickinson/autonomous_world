"""Player character class."""

import math
from typing import List, Optional
from game.settings import *
from game.core.entity import Entity
from game.core.items import Item, make_item


class Player(Entity):
    """The player character."""
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.max_hp = PLAYER_MAX_HP
        self.hp = PLAYER_MAX_HP
        self.energy = PLAYER_MAX_ENERGY
        self.max_energy = PLAYER_MAX_ENERGY
        self.speed = PLAYER_SPEED
        self.xp = 0
        self.level = 1
        self.xp_to_next = 50
        self.gold = 20
        self.attack_damage = PLAYER_ATTACK_DAMAGE
        self.defense = 0
        self.attack_cooldown = 0.0
        self.attack_timer = 0.0
        self.inventory: List[Item] = [make_item("Wooden Sword"), make_item("Bread"), make_item("Bread"), make_item("Health Potion")]
        self.equipped_weapon: Optional[Item] = self.inventory[0]
        self.equipped_armor: Optional[Item] = None
        self.hotbar: List[Optional[Item]] = [None] * 5
        self.hotbar[0] = self.inventory[0]

        # Stats
        self.kills = 0
        self.quests_completed = 0
        self.steps = 0.0
        self.name = "Player"

        # D&D Character
        self.char_class = "Fighter"  # default, can be changed
        self.race = "Human"
        self.level = 1
        from game.data.dnd import roll_ability_scores, ability_modifier, get_class_hp, CLASSES, get_class_abilities, get_proficiency_bonus
        self.ability_scores = roll_ability_scores(self.race, self.char_class)
        self.proficiency_bonus = get_proficiency_bonus(self.level)
        cls_data = CLASSES.get(self.char_class, {})
        self.is_spellcaster = cls_data.get("spellcaster", False)
        self.known_spells = list(cls_data.get("spell_list", []))[:3]
        self.spell_slots = [0, 0, 0]
        if self.is_spellcaster:
            slot_table = cls_data.get("spell_slots", {})
            for lvl in sorted(slot_table.keys()):
                if lvl <= self.level:
                    self.spell_slots = list(slot_table[lvl])
        self.spell_slots_used = [0, 0, 0]
        self.class_abilities = get_class_abilities(self.char_class, self.level)
        self.armor_class = 10 + ability_modifier(self.ability_scores.get("dexterity", 10))

        # Skills — full 48-skill unified system
        from game.systems.skills import initialize_player_skills
        initialize_player_skills(self)

        # Movement gaits
        self.current_gait = "walk"  # walk, jog, run, sprint, sneak
        self.base_speed = PLAYER_SPEED  # walking speed

        # Interior view state
        from game.systems.interiors import InteriorViewState
        self.interior_state = InteriorViewState()

        # Floor tracking — which floor the player is on within a building
        # 0 = ground floor, +N = upper floors, -N = underground
        self.current_floor = 0
        self._current_building_name = ""
        self._current_building_kind = ""
        self._current_building_rect = None  # (x, y, w, h) or None
        self._underground_explored = set()  # (x, y) tiles explored underground

        # Career advancement (military and political)
        from game.systems.career import CareerSystem
        self.career = CareerSystem()
        self.title = "Outsider"  # updated by career system
        self.faction = ""

        # Faction reputation system (player standing with kingdoms)
        from game.systems.factions import FactionSystem
        self.faction_system = FactionSystem()
        self.current_kingdom = ""  # updated each tick by simulation

        # Body weight (lbs) — derived from race and constitution
        from game.core.npc import _calc_body_weight
        con = self.ability_scores.get("constitution", 10)
        self.body_weight = _calc_body_weight(self.race, con)

        # Abilities unlocked at skill thresholds
        self.ability_cooldowns = {}  # ability_name -> remaining cooldown

        # Passive bonuses from skills
        self.hp_regen_rate = 0.0  # from tracking/survival

        # Body part system (detailed wound tracking)
        from game.systems.body_damage import Body
        self.body = Body("humanoid", scale_hp=self.max_hp)

        # Emotion state (Plutchik's wheel — shared with NPCs and creatures)
        from game.systems.emotions import EmotionState, personality_for_player
        self.emotion_state = EmotionState(personality_for_player())

        # Magic system: mana, spells, effects
        from game.systems.magic import init_mana, auto_learn_spells_for_class
        init_mana(self)
        auto_learn_spells_for_class(self)

    def _check_floor_walkable(self, x: int, y: int, world) -> bool:
        """Check walkability against the current floor's layout.

        Underground levels use world.underground, upper floors use plan data.
        """
        cur_fl = self.current_floor

        if cur_fl < 0 and hasattr(world, 'is_underground_walkable'):
            # Underground: check the underground tile layer
            return world.is_underground_walkable(x, y, cur_fl)

        if cur_fl > 0:
            # Upper floors: check building plan data
            rect = self._current_building_rect
            if not rect:
                return False
            bx, by, bw, bh = rect
            if not (bx <= x < bx + bw and by <= y < by + bh):
                return False

            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        if (bld['x'] == bx and bld['y'] == by and
                                bld['w'] == bw and bld['h'] == bh):
                            floors = bld.get('floors', {})
                            floor_tiles = floors.get(cur_fl)
                            if floor_tiles:
                                lx = x - bx
                                ly = y - by
                                if 0 <= ly < len(floor_tiles) and 0 <= lx < len(floor_tiles[ly]):
                                    tile = floor_tiles[ly][lx]
                                    from game.settings import TERRAIN_WALK_COST
                                    return TERRAIN_WALK_COST.get(tile, 999) < 10
                            return False

        return world.is_walkable(x, y)

    def gain_skill_xp(self, skill: str, amount: float):
        """Gain XP toward a skill. Levels up at thresholds."""
        # Auto-add unknown skills at level 0
        if skill not in self.skills:
            self.skills[skill] = 0
            self.skill_xp[skill] = 0.0
        self.skill_xp[skill] = self.skill_xp.get(skill, 0.0) + amount
        threshold = 5.0 + self.skills[skill] * 3.0
        while self.skill_xp[skill] >= threshold and self.skills[skill] < 10:
            self.skill_xp[skill] -= threshold
            self.skills[skill] += 1
            threshold = 5.0 + self.skills[skill] * 3.0
            # Unlock passive bonuses
            if skill == "tracking" and self.skills[skill] >= 5:
                self.hp_regen_rate = 0.5
            if skill == "swordsmanship" and self.skills[skill] >= 3:
                self.attack_damage += 1

    def get_abilities(self) -> list:
        """Return list of (name, description, ready, key) for available abilities."""
        abilities = []
        sk = self.skills
        cd = self.ability_cooldowns

        # Combat abilities
        if sk.get("swordsmanship", 0) >= 3:
            abilities.append(("Power Strike", "Deal 3x damage on next hit",
                            cd.get("power_strike", 0) <= 0, "F1"))
        if sk.get("swordsmanship", 0) >= 6:
            abilities.append(("Whirlwind", "Hit all enemies nearby",
                            cd.get("whirlwind", 0) <= 0, "F2"))
        if sk.get("archery", 0) >= 3:
            abilities.append(("Aimed Shot", "Next arrow deals 2x damage",
                            cd.get("aimed_shot", 0) <= 0, "F3"))
        if sk.get("archery", 0) >= 6:
            abilities.append(("Volley", "Fire arrows at all nearby enemies",
                            cd.get("volley", 0) <= 0, "F4"))
        if sk.get("shield_work", 0) >= 3:
            abilities.append(("Shield Bash", "Stun an enemy briefly",
                            cd.get("shield_bash", 0) <= 0, "F5"))
        if sk.get("unarmed", 0) >= 3:
            abilities.append(("Stunning Blow", "Chance to stun on unarmed hit",
                            cd.get("stunning_blow", 0) <= 0, "F6"))

        # Stealth abilities
        if sk.get("stealth", 0) >= 3:
            abilities.append(("Shadowstep", "Brief invisibility",
                            cd.get("shadowstep", 0) <= 0, "F7"))
        if sk.get("lockpicking", 0) >= 3:
            abilities.append(("Expert Pick", "+5 bonus to lockpicking",
                            cd.get("expert_pick", 0) <= 0, "F8"))

        # Social abilities
        if sk.get("persuasion", 0) >= 3:
            abilities.append(("Charm", "Boost relationship with nearby NPC",
                            cd.get("charm", 0) <= 0, "F9"))
        if sk.get("intimidation", 0) >= 3:
            abilities.append(("Threaten", "Chance to make enemies flee",
                            cd.get("threaten", 0) <= 0, "F10"))
        if sk.get("performance", 0) >= 3:
            abilities.append(("Inspire", "Boost morale of nearby allies",
                            cd.get("inspire", 0) <= 0, "F11"))

        # Knowledge abilities
        if sk.get("medicine", 0) >= 3:
            abilities.append(("First Aid", "Heal self without potion",
                            cd.get("first_aid", 0) <= 0, "F12"))
        if sk.get("nature_lore", 0) >= 3:
            abilities.append(("Keen Eye", "Reveal nearby items and resources",
                            cd.get("keen_eye", 0) <= 0, "-"))

        # Survival abilities
        if sk.get("navigation", 0) >= 3:
            abilities.append(("Scout", "Reveal large area on map",
                            cd.get("scout", 0) <= 0, "-"))
        if sk.get("tracking", 0) >= 3:
            abilities.append(("Hunter's Mark", "Highlight creatures on minimap",
                            cd.get("hunters_mark", 0) <= 0, "-"))
        if sk.get("tracking", 0) >= 5:
            abilities.append(("Tough", "Passive: slowly regenerate HP", True, "-"))

        # Magic abilities
        if sk.get("spellcraft", 0) >= 3:
            abilities.append(("Cantrip", "Cast a free minor spell",
                            cd.get("cantrip", 0) <= 0, "-"))
        if sk.get("warding", 0) >= 3:
            abilities.append(("Shield Ward", "Temporary damage resistance",
                            cd.get("shield_ward", 0) <= 0, "-"))

        return abilities

    def get_attack_damage(self) -> int:
        base = self.attack_damage
        if self.equipped_weapon:
            base += self.equipped_weapon.damage
        return base + self.level * 2

    def get_defense(self) -> int:
        base = self.defense
        if self.equipped_armor:
            base += self.equipped_armor.defense
        return base

    def gain_xp(self, amount: int):
        self.xp += amount
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            # Recalculate D&D stats on level up
            from game.data.dnd import get_class_hp, ability_modifier, get_class_abilities, get_proficiency_bonus, CLASSES
            con_mod = ability_modifier(self.ability_scores.get("constitution", 10))
            self.max_hp = get_class_hp(self.char_class, self.level, con_mod)
            self.proficiency_bonus = get_proficiency_bonus(self.level)
            self.class_abilities = get_class_abilities(self.char_class, self.level)
            cls_data = CLASSES.get(self.char_class, {})
            if cls_data.get("spellcaster"):
                slot_table = cls_data.get("spell_slots", {})
                for lvl in sorted(slot_table.keys()):
                    if lvl <= self.level:
                        self.spell_slots = list(slot_table[lvl])
                max_spells = 3 + self.level
                self.known_spells = list(cls_data.get("spell_list", []))[:max_spells]
            self.xp_to_next = int(self.xp_to_next * 1.5)
            self.max_hp += 10
            self.hp = self.max_hp
            self.attack_damage += 2
            # Recalculate magic on level up
            from game.systems.magic import on_level_up, auto_learn_spells_for_class
            on_level_up(self)
            auto_learn_spells_for_class(self)

    def add_item(self, item: Item) -> bool:
        """Add item to inventory. Returns True if successful."""
        if len(self.inventory) >= 20 and not item.stackable:
            return False
        if item.stackable:
            for inv_item in self.inventory:
                if inv_item.name == item.name:
                    inv_item.count += item.count
                    return True
        if len(self.inventory) >= 20:
            return False
        self.inventory.append(item)
        return True

    def remove_item(self, item_name: str, count: int = 1) -> bool:
        """Remove item(s) from inventory."""
        for i, inv_item in enumerate(self.inventory):
            if inv_item.name == item_name:
                if inv_item.stackable and inv_item.count > count:
                    inv_item.count -= count
                    return True
                elif inv_item.stackable and inv_item.count <= count:
                    self.inventory.pop(i)
                    return True
                else:
                    self.inventory.pop(i)
                    return True
        return False

    def count_item(self, item_name: str) -> int:
        for item in self.inventory:
            if item.name == item_name:
                return item.count if item.stackable else 1
        return 0

    def use_item(self, item: Item) -> str:
        """Use a consumable item. Returns result message."""
        if item.kind in (ITEM_CONSUMABLE, ITEM_FOOD, ITEM_DRINK):
            if item.heal > 0:
                old_hp = self.hp
                self.heal(item.heal)
                healed = self.hp - old_hp
                self.remove_item(item.name, 1)
                return f"Used {item.name}. Restored {healed} HP."
            else:
                self.remove_item(item.name, 1)
                return f"Consumed {item.name}."
        elif item.kind == ITEM_WEAPON:
            self.equipped_weapon = item
            return f"Equipped {item.name}."
        elif item.kind == ITEM_ARMOR:
            self.equipped_armor = item
            return f"Equipped {item.name}."
        return ""

    def update(self, dt: float, world):
        """Update player state."""
        if self.attack_timer > 0:
            self.attack_timer -= dt

        # Ability cooldowns
        for k in list(self.ability_cooldowns):
            self.ability_cooldowns[k] -= dt
            if self.ability_cooldowns[k] <= 0:
                del self.ability_cooldowns[k]

        # HP regen from survival skill
        if self.hp_regen_rate > 0 and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + self.hp_regen_rate * dt)

        # Magic system: mana regen, cooldowns, spell effects
        from game.systems.magic import update_magic
        update_magic(self, dt, world)

        # Energy regen
        if self.energy < self.max_energy:
            self.energy = min(self.max_energy, self.energy + dt * 3)

        # Move (with gait-based speed)
        if self.vx != 0 or self.vy != 0:
            # Normalize diagonal movement
            mag = math.sqrt(self.vx * self.vx + self.vy * self.vy)
            if mag > 0:
                nx = self.vx / mag
                ny = self.vy / mag
                self.facing = (nx, ny)

                # Apply gait speed
                from game.systems.physical import get_gait_speed, apply_gait_energy_cost
                actual_speed = get_gait_speed(self, self.current_gait)
                # Drain energy for non-walking gaits
                if not apply_gait_energy_cost(self, self.current_gait, dt):
                    # Out of energy — force walk
                    self.current_gait = "walk"
                    actual_speed = self.speed

                move_x = nx * actual_speed * dt
                move_y = ny * actual_speed * dt

                is_ghost = getattr(self, 'ghost', False)
                is_god = getattr(self, 'god', False)

                # Ghosts and gods pass through walls
                if is_ghost or is_god:
                    self.x += move_x
                    self.y += move_y
                    self.steps += abs(move_x) + abs(move_y)
                    # Clamp to world bounds
                    self.x = max(1, min(world.width - 2, self.x))
                    self.y = max(1, min(world.height - 2, self.y))
                else:
                    # Check collision — use floor layout if on non-ground floor
                    def _check_walkable(cx, cy):
                        cur_fl = getattr(self, 'current_floor', 0)
                        if cur_fl != 0 and getattr(self, '_current_building_rect', None):
                            # Check against the current floor's tile layout
                            return self._check_floor_walkable(cx, cy, world)
                        return world.is_walkable(cx, cy)

                    new_x = self.x + move_x
                    if _check_walkable(int(new_x + 0.3 * (1 if move_x > 0 else -1)), int(self.y)):
                        self.x = new_x
                        self.steps += abs(move_x)

                    new_y = self.y + move_y
                    if _check_walkable(int(self.x), int(new_y + 0.3 * (1 if move_y > 0 else -1))):
                        self.y = new_y
                        self.steps += abs(move_y)
                    self.steps += abs(move_y)

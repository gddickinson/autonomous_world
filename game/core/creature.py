"""Creature class for hostile entities."""

import math
import random
from typing import List, Optional, Tuple
from game.settings import *
from game.core.entity import Entity
from game.core.items import Item, make_item


class Creature(Entity):
    """A hostile creature in the wild, using D&D monster stats."""
    def __init__(self, x: float, y: float, kind: str):
        super().__init__(x, y)
        self.kind = kind

        # Try D&D monster data first, fall back to old CREATURE_TYPES
        from game.data.dnd import MONSTERS
        if kind in MONSTERS:
            stats = MONSTERS[kind]
            self.max_hp = stats["hp"]
            self.hp = stats["hp"]
            self.damage = stats["damage"]
            self.speed = stats.get("speed", 1.8)
            self.xp_value = stats["xp"]
            self.color = stats["color"]
            self.armor_class = stats.get("ac", 10)
            self.monster_type = stats.get("type", "beast")
            self.cr = stats.get("cr", 0.25)
            self.passive = stats.get("passive", False)
        elif kind in CREATURE_TYPES:
            stats = CREATURE_TYPES[kind]
            self.max_hp = stats["hp"]
            self.hp = stats["hp"]
            self.damage = stats["damage"]
            self.speed = stats["speed"]
            self.xp_value = stats["xp"]
            self.color = stats["color"]
            self.armor_class = 10
            self.monster_type = "beast"
            self.cr = 0.25
            self.passive = False
        else:
            # Fallback
            self.max_hp = 20
            self.hp = 20
            self.damage = 5
            self.speed = 1.8
            self.xp_value = 10
            self.color = (120, 120, 120)
            self.armor_class = 10
            self.monster_type = "beast"
            self.cr = 0.25
            self.passive = False

        # AI
        self.state = "idle"  # idle, wandering, chasing, attacking, fleeing
        self.target: Optional[Entity] = None
        self.home_x = x
        self.home_y = y
        self.state_timer = random.uniform(1.0, 5.0)
        self.attack_timer = 0.0
        self.leash_range = 15.0  # Max distance from home before returning
        self.aggro_range = CREATURE_CHASE_RANGE

        # Domestication / mount state
        from game.systems.domestication import DomesticationState, CREATURE_SIZE
        self.domestication = DomesticationState()
        self.creature_size = CREATURE_SIZE.get(kind, "medium")

        # Capture state
        from game.systems.capture import CaptiveState
        self.captive_state = CaptiveState()
        # Horses and similar animals in stables start domesticated
        if kind in ("horse", "war_horse", "donkey", "mule", "camel"):
            self.domestication.status = "domesticated"
            self.domestication.trust = 80
            self.domestication.training_level = 5

        # Soul system
        self.soul_id = None  # set by SoulSystem.on_birth, or None for untracked

        # Emotion state (initialized lazily by EmotionSystem, or eagerly below)
        from game.systems.emotions import personality_for_creature
        from game.systems.emotions import EmotionState
        self.emotion_state = EmotionState(
            personality_for_creature(kind, self.monster_type))

        # Body part system (detailed wound tracking)
        from game.systems.body_damage import Body
        if self.monster_type in ("humanoid", "undead", "fiend"):
            self.body = Body("humanoid", scale_hp=self.max_hp)
        else:
            self.body = Body("quadruped", scale_hp=self.max_hp)

        # Drops
        self.drops = self._generate_drops(kind)

        # Respawn
        self.respawn_timer = 0.0
        self.respawn_time = 60.0

    def _generate_drops(self, kind: str) -> List[Tuple[str, float]]:
        """Generate possible drops from D&D monster data or fallback."""
        from game.data.dnd import MONSTERS
        if kind in MONSTERS:
            return MONSTERS[kind].get("drops", [])
        fallback = {
            "wolf": [("Wolf Pelt", 0.6), ("Bread", 0.2)],
            "bear": [("Cooked Meat", 0.5), ("Wolf Pelt", 0.3), ("Gold Nugget", 0.1)],
            "bandit": [("Gold Nugget", 0.4), ("Iron Sword", 0.1), ("Health Potion", 0.3)],
            "skeleton": [("Ancient Relic", 0.1), ("Iron Ore", 0.3), ("Health Potion", 0.2)],
            "spider": [("Herbs", 0.4)],
            "boar": [("Cooked Meat", 0.5), ("Bread", 0.2)],
        }
        return fallback.get(kind, [])

    def get_drops(self) -> List[Item]:
        """Roll for drops when killed."""
        result = []
        for item_name, prob in self.drops:
            if random.random() < prob:
                result.append(make_item(item_name))
        # Always drop a small amount of gold equivalent
        return result

    def update(self, dt: float, world, player, creatures: list):
        """Update creature AI."""
        if not self.alive:
            return

        self.attack_timer = max(0, self.attack_timer - dt)
        self.state_timer -= dt

        dist_to_player = self.dist_to(player)
        dist_from_home = self.dist_to_pos(self.home_x, self.home_y)

        # Passive animals flee from player instead of attacking
        is_passive = getattr(self, 'passive', False)

        if is_passive:
            # Passive: flee when player gets close, otherwise wander peacefully
            if dist_to_player < 5.0 and player.alive:
                # Flee away from player
                self.state = "fleeing"
                self.state_timer = 3.0
                if dist_to_player > 0.1:
                    flee_x = self.x + (self.x - player.x) * 2
                    flee_y = self.y + (self.y - player.y) * 2
                    self._move_toward(flee_x, flee_y, dt, world)
                return
            elif self.state_timer <= 0:
                # Peaceful wandering
                self.state = "wandering"
                self.state_timer = random.uniform(4.0, 12.0)
                angle = random.uniform(0, 2 * 3.14159)
                r = random.uniform(2, 6)
                tx = self.home_x + math.cos(angle) * r
                ty = self.home_y + math.sin(angle) * r
                self._move_toward(tx, ty, dt, world)
            elif self.state == "wandering":
                # Continue gentle wandering
                angle = random.uniform(0, 2 * 3.14159)
                self._move_toward(self.x + math.cos(angle) * 0.5,
                                 self.y + math.sin(angle) * 0.5, dt, world)
            return

        # Emotion-driven behavior modifiers
        es = getattr(self, 'emotion_state', None)
        _fear = es.primary.get("fear", 0.0) if es else 0.0
        _anger = es.primary.get("anger", 0.0) if es else 0.0

        # Fearful creatures flee instead of fighting (if fear > anger)
        if _fear > 0.5 and _fear > _anger and self.state not in ("fleeing",):
            self.state = "fleeing"
            self.state_timer = max(3.0, _fear * 5.0)

        # Angry creatures have extended aggro range
        _effective_aggro = self.aggro_range
        if _anger > 0.4:
            _effective_aggro = self.aggro_range * (1.0 + _anger * 0.5)

        # Hostile state machine
        if self.state == "idle":
            if dist_to_player < _effective_aggro and player.alive:
                self.state = "chasing"
                self.target = player
            elif self.state_timer <= 0:
                self.state = "wandering"
                self.state_timer = random.uniform(3.0, 8.0)

        elif self.state == "wandering":
            if dist_to_player < _effective_aggro and player.alive:
                self.state = "chasing"
                self.target = player
            elif self.state_timer <= 0:
                self.state = "idle"
                self.state_timer = random.uniform(2.0, 5.0)
            else:
                # Wander around home
                if self.target is None or random.random() < 0.02:
                    angle = random.uniform(0, 2 * math.pi)
                    r = random.uniform(1, 5)
                    tx = self.home_x + math.cos(angle) * r
                    ty = self.home_y + math.sin(angle) * r
                    self._move_toward(tx, ty, dt, world)
                else:
                    self._move_toward(self.home_x, self.home_y, dt, world)

        elif self.state == "chasing":
            if not player.alive or dist_to_player > _effective_aggro * 2:
                self.state = "idle"
                self.target = None
                self.state_timer = 2.0
            elif dist_from_home > self.leash_range:
                # Return home
                self.state = "wandering"
                self.target = None
                self.state_timer = 3.0
            elif dist_to_player < CREATURE_ATTACK_RANGE:
                self.state = "attacking"
            else:
                self._move_toward(player.x, player.y, dt, world)

        elif self.state == "attacking":
            if not player.alive:
                self.state = "idle"
                self.state_timer = 2.0
            elif dist_to_player > CREATURE_ATTACK_RANGE * 1.5:
                self.state = "chasing"
            elif self.attack_timer <= 0:
                # Attack!
                pack_bonus = getattr(self, 'pack_bonus', 0)
                raw_damage = max(1, self.damage + pack_bonus)
                # Use body damage system if player has a body
                if getattr(player, 'body', None) is not None:
                    from game.systems.body_damage import BodyDamageSystem
                    _bds = BodyDamageSystem()
                    # Infer damage type from creature kind
                    _kind = self.kind.lower()
                    if any(k in _kind for k in ("skeleton", "golem", "ogre")):
                        _dmg_type = "blunt"
                    elif any(k in _kind for k in ("wolf", "bear", "spider", "drake")):
                        _dmg_type = "slash"
                    elif any(k in _kind for k in ("dragon",)) and "fire" in _kind:
                        _dmg_type = "fire"
                    else:
                        _dmg_type = "slash"
                    actual_damage = _bds.apply_damage(player, raw_damage,
                                                      damage_type=_dmg_type)
                else:
                    actual_damage = max(1, raw_damage - player.get_defense())
                    player.take_damage(actual_damage)
                self.attack_timer = CREATURE_ATTACK_COOLDOWN
                self.facing = (
                    (player.x - self.x) / max(0.1, dist_to_player),
                    (player.y - self.y) / max(0.1, dist_to_player)
                )

        # HP-based fleeing (injuries trigger fear emotion too)
        if self.hp < self.max_hp * 0.2 and self.state != "fleeing":
            self.state = "fleeing"
            self.state_timer = 5.0
            if es:
                from game.systems.emotions import trigger_emotion
                trigger_emotion(self, "injured", intensity=0.8)

        if self.state == "fleeing":
            if self.state_timer <= 0:
                self.state = "wandering"
                self.state_timer = 5.0
            else:
                # Flee away from player
                if dist_to_player > 0.1:
                    flee_x = self.x + (self.x - player.x)
                    flee_y = self.y + (self.y - player.y)
                    self._move_toward(flee_x, flee_y, dt, world)

    def _move_toward(self, tx: float, ty: float, dt: float, world):
        """Move toward a target position with wall-sliding and gait-based speed."""
        from game.systems.navigation import wall_slide

        # Choose speed based on state
        move_speed = self.speed  # base walk speed
        if self.state == "chasing":
            move_speed = self.speed * 1.5  # trot/chase
        elif self.state == "fleeing":
            move_speed = self.speed * 2.0  # gallop/flee
        elif self.state == "wandering":
            move_speed = self.speed * 0.8  # leisurely

        # Apply body damage speed penalty (leg injuries)
        _body = getattr(self, 'body', None)
        if _body is not None:
            _body_mods = _body.get_activity_modifiers()
            _body_spd = _body_mods.get("speed", 1.0)
            if _body_spd < 1.0:
                move_speed *= _body_spd

        new_x, new_y = wall_slide(self, tx, ty, world, move_speed, dt)
        if new_x != self.x or new_y != self.y:
            dx = new_x - self.x
            dy = new_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0.01:
                self.facing = (dx / dist, dy / dist)
            self.x = new_x
            self.y = new_y

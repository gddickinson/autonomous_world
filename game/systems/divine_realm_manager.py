"""Divine Realm Manager — handles transitions between god world and mortal world.

Manages the divine realm state, viewing pool, portal gate, god NPCs,
and entity capture/return between realms.
"""

from typing import Optional, List, Dict, Tuple


class DivineRealmManager:
    """Manages the divine realm and transitions to/from the mortal world."""

    def __init__(self, game):
        self.game = game
        self.realm_data: Optional[Dict] = None
        self.in_divine_realm = False
        self.mortal_position: Optional[Tuple[float, float]] = None
        self.captured_entities: List[Dict] = []  # {name, kind, stats}
        self.viewing_pool_active = False
        self._initialized = False

    def initialize(self):
        """Generate the divine realm on first use."""
        if self._initialized:
            return
        from game.world.divine_realm import generate_divine_realm
        seed = getattr(self.game, 'seed', 42)
        if hasattr(self.game, 'world') and hasattr(self.game.world, 'seed'):
            seed = self.game.world.seed
        self.realm_data = generate_divine_realm(seed)
        self._initialized = True

    def enter_divine_realm(self):
        """Teleport the player to the divine realm."""
        if not self._initialized:
            self.initialize()
        player = self.game.player
        # Save mortal world position and camera bounds
        self.mortal_position = (player.x, player.y)
        camera = getattr(self.game, 'camera', None)
        if camera:
            self._saved_camera_bounds = (camera.world_w, camera.world_h)
            # Constrain camera to divine realm size
            realm_size = self.realm_data["size"]
            camera.world_w = realm_size
            camera.world_h = realm_size
        # Move player to divine realm center (near viewing pool)
        pool = self.realm_data["pool_pos"]
        player.x = float(pool[0])
        player.y = float(pool[1] + 20)  # south of pool
        self.in_divine_realm = True
        # Center camera on player
        if camera:
            from game.settings import TILE_SIZE
            camera.x = player.x * TILE_SIZE - 640
            camera.y = player.y * TILE_SIZE - 400
        # Notify
        if hasattr(self.game, 'notifications'):
            self.game.notifications.add(
                "You ascend to the Divine Realm", 3.0, (255, 220, 100))

    def exit_to_mortal_world(self, target_x: float = None,
                              target_y: float = None):
        """Return to the mortal world."""
        player = self.game.player
        if target_x is not None and target_y is not None:
            player.x = target_x
            player.y = target_y
        elif self.mortal_position:
            player.x, player.y = self.mortal_position
        self.in_divine_realm = False
        self.viewing_pool_active = False
        # Restore camera bounds
        camera = getattr(self.game, 'camera', None)
        if camera and hasattr(self, '_saved_camera_bounds'):
            camera.world_w, camera.world_h = self._saved_camera_bounds
            from game.settings import TILE_SIZE
            camera.x = player.x * TILE_SIZE - 640
            camera.y = player.y * TILE_SIZE - 400
        if hasattr(self.game, 'notifications'):
            self.game.notifications.add(
                "You descend to the mortal world", 3.0, (180, 200, 255))

    def toggle_viewing_pool(self):
        """Toggle the viewing pool (world observation mode)."""
        if not self.in_divine_realm:
            return
        player = self.game.player
        pool = self.realm_data["pool_pos"]
        dist = ((player.x - pool[0]) ** 2 + (player.y - pool[1]) ** 2) ** 0.5
        if dist > 20:
            if hasattr(self.game, 'notifications'):
                self.game.notifications.add(
                    "Move closer to the Viewing Pool", 2.0, (200, 200, 200))
            return
        self.viewing_pool_active = not self.viewing_pool_active
        if self.viewing_pool_active and hasattr(self.game, 'notifications'):
            self.game.notifications.add(
                "The Viewing Pool shimmers... The mortal world appears",
                3.0, (100, 200, 255))

    def check_portal_interaction(self) -> bool:
        """Check if player is near the portal gate."""
        if not self.in_divine_realm or not self.realm_data:
            return False
        player = self.game.player
        portal = self.realm_data["portal_pos"]
        dist = ((player.x - portal[0]) ** 2 +
                (player.y - portal[1]) ** 2) ** 0.5
        return dist < 8

    def capture_entity(self, entity) -> bool:
        """Bring an entity from the mortal world to the divine realm."""
        if len(self.captured_entities) >= 20:
            return False
        info = {
            "name": getattr(entity, 'name', 'Unknown'),
            "kind": type(entity).__name__,
            "hp": getattr(entity, 'hp', 0),
            "max_hp": getattr(entity, 'max_hp', 0),
            "level": getattr(entity, 'level', 1),
            "profession": getattr(entity, 'profession', ''),
        }
        self.captured_entities.append(info)
        return True

    def get_nearby_god_npc(self, player_x: float, player_y: float
                           ) -> Optional[Dict]:
        """Check if player is near a god NPC in the temple."""
        if not self.realm_data:
            return None
        for god in self.realm_data["god_spawns"]:
            dist = ((player_x - god["x"]) ** 2 +
                    (player_y - god["y"]) ** 2) ** 0.5
            if dist < 3:
                return god
        return None

    def get_god_dialog(self, god: Dict) -> str:
        """Get dialog text for a god NPC."""
        dialogs = {
            "Tharion": "I am Tharion, god of war and honor! The battlefield is sacred. Point me at a kingdom and watch their armies clash! The brave deserve glory.",
            "Sylvana": "The forests and beasts are my children. I see every tree felled, every creature hunted. Tread carefully in my domain, or face nature's wrath.",
            "Verithos": "Knowledge is the true power. The mortals below stumble in ignorance. Perhaps a prophecy would guide them... or mislead them. All truths have a price.",
            "Morwen": "Death comes for all mortals eventually. I merely keep the ledger. The souls you see below... each one is counted. Fair, but merciless.",
            "Auriel": "Every trade is sacred, every deal a prayer. The markets below flow with gold — or should. Shall I bless a kingdom's coffers?",
            "Lyria": "Love binds all things. I see the bonds between mortals — the friendships, the romances, the hatreds. Shall I mend a broken heart, or break one?",
            "Xaotl": "ORDER is BORING! Let me shake things up down there. A plague here, a festival there, maybe turn a river backwards? The mortals need some CHAOS!",
        }
        return dialogs.get(god["name"],
                          f"I am {god['name']}, god of {god['domain']}.")

    def get_realm_tiles(self) -> Optional[List[List[int]]]:
        """Get the divine realm tile map (for rendering)."""
        if not self.realm_data:
            return None
        return self.realm_data["tiles"]

    def is_near_structure(self, player_x: float, player_y: float,
                          kind: str) -> bool:
        """Check if player is near a specific structure in the realm."""
        if not self.realm_data:
            return False
        for s in self.realm_data["structures"]:
            if s["kind"] == kind:
                cx = s["x"] + s["w"] / 2
                cy = s["y"] + s["h"] / 2
                dist = ((player_x - cx) ** 2 + (player_y - cy) ** 2) ** 0.5
                if dist < max(s["w"], s["h"]):
                    return True
        return False

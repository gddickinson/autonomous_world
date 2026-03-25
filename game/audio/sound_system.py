"""
SoundManager — procedural audio playback for the game.
Uses pre-generated sounds from sound_generators.py (no external audio files).
"""

import math
import random

import pygame

from game.audio.sound_generators import SOUND_GENERATORS, SAMPLE_RATE


class SoundManager:
    """Pre-generates and manages all game sounds.

    Sounds are cached as pygame.Sound objects at init time.
    Supports positional audio, master volume, and mute toggle.
    Separate toggles for sound effects and music (F8/F9).
    """

    def __init__(self):
        self._enabled = True
        self._master_volume = 0.5
        self._muted = False
        self.sounds_enabled = True   # SFX toggle (F8)
        self.music_enabled = True    # Music toggle (F9)
        self._sounds: dict[str, pygame.mixer.Sound] = {}

        # Ambient state
        self._ambient_timer = 0.0
        self._ambient_interval = 3.0  # seconds between ambient sounds
        self._current_biome = "grass"
        self._time_of_day = 0.3  # 0=midnight, 0.5=noon

        # Try to init mixer if not already done
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16,
                                  channels=2, buffer=512)
            pygame.mixer.set_num_channels(16)
            self._generate_all()
        except Exception as e:
            print(f"[AUDIO] Failed to initialize: {e}")
            self._enabled = False

    def _generate_all(self):
        """Pre-generate all sound effects from the registry."""
        for name, gen_fn in SOUND_GENERATORS.items():
            try:
                self._sounds[name] = gen_fn()
            except Exception as e:
                print(f"[AUDIO] Failed to generate '{name}': {e}")

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self, sound_name: str, volume: float = 1.0):
        """Play a named sound effect."""
        if not self._enabled or self._muted or not self.sounds_enabled:
            return
        snd = self._sounds.get(sound_name)
        if snd is None:
            return
        effective = self._master_volume * volume
        snd.set_volume(max(0.0, min(1.0, effective)))
        snd.play()

    def play_at(self, sound_name: str, x: float, y: float,
                listener_x: float, listener_y: float,
                max_dist: float = 25.0):
        """Play a sound with distance-based volume falloff."""
        if not self._enabled or self._muted or not self.sounds_enabled:
            return
        dx = x - listener_x
        dy = y - listener_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > max_dist:
            return
        vol = max(0.0, 1.0 - dist / max_dist)
        self.play(sound_name, volume=vol)

    # ------------------------------------------------------------------
    # Volume / mute
    # ------------------------------------------------------------------

    def set_master_volume(self, vol: float):
        """Set master volume (0.0 to 1.0)."""
        self._master_volume = max(0.0, min(1.0, vol))

    def mute(self):
        self._muted = True

    def unmute(self):
        self._muted = False

    def toggle_mute(self) -> bool:
        """Toggle mute, return new muted state."""
        self._muted = not self._muted
        if self._muted:
            pygame.mixer.stop()
        return self._muted

    def toggle_sounds(self) -> bool:
        """Toggle sound effects on/off. Returns new state."""
        self.sounds_enabled = not self.sounds_enabled
        return self.sounds_enabled

    def toggle_music(self) -> bool:
        """Toggle music on/off. Returns new state."""
        self.music_enabled = not self.music_enabled
        return self.music_enabled

    # ------------------------------------------------------------------
    # Ambient system
    # ------------------------------------------------------------------

    def update_ambient(self, dt: float, tile_type: int,
                       time_normalized: float,
                       player_x: float, player_y: float,
                       world=None):
        """Update ambient sound layer. Call every frame."""
        if not self._enabled or self._muted or not self.sounds_enabled:
            return

        self._time_of_day = time_normalized
        self._update_biome(tile_type, player_x, player_y, world)

        self._ambient_timer += dt
        if self._ambient_timer < self._ambient_interval:
            return
        self._ambient_timer = 0.0
        self._ambient_interval = random.uniform(2.0, 5.0)

        is_night = (time_normalized < 0.2 or time_normalized > 0.8)

        if is_night:
            self.play("cricket", volume=0.4)
        elif self._current_biome == "forest":
            self.play("bird_chirp", volume=0.5)
        elif self._current_biome == "village":
            if random.random() < 0.5:
                self.play("hammer_clink", volume=0.3)
        elif self._current_biome == "water":
            self.play("water_wave", volume=0.3)
        elif self._current_biome == "grass":
            if random.random() < 0.3:
                self.play("bird_chirp", volume=0.3)

    def _update_biome(self, tile_type: int, px: float, py: float,
                      world=None):
        """Determine current biome category from tile and surroundings.

        Settlement proximity check is throttled — only recalculated when
        the player moves to a new tile position.
        """
        from game.settings import (
            FOREST, DENSE_FOREST, WATER, SHALLOW_WATER,
            FLOOR, BUILT_FLOOR, COBBLESTONE,
        )
        if tile_type in (WATER, SHALLOW_WATER):
            self._current_biome = "water"
        elif tile_type in (FOREST, DENSE_FOREST):
            self._current_biome = "forest"
        elif tile_type in (FLOOR, BUILT_FLOOR, COBBLESTONE):
            self._current_biome = "village"
        else:
            # Throttle settlement proximity check to once per tile change
            ipx, ipy = int(px), int(py)
            last = getattr(self, '_last_biome_pos', None)
            if last == (ipx, ipy):
                return  # keep current biome, position unchanged
            self._last_biome_pos = (ipx, ipy)

            if world and hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    if (abs(sp.x - ipx) <= sp.radius
                            and abs(sp.y - ipy) <= sp.radius):
                        self._current_biome = "village"
                        return
            self._current_biome = "grass"

    # ------------------------------------------------------------------
    # Convenience: combat sounds
    # ------------------------------------------------------------------

    _COMBAT_SOUND_MAP = {
        "melee": "sword_hit",
        "ranged": "arrow_fire",
        "spell": "spell_cast",
        "fireball": "fireball_impact",
        "lightning": "lightning",
        "ice": "ice_shatter",
        "fire": "fireball_impact",
    }

    def play_combat_hit(self, attack_type: str = "melee",
                        x: float = 0, y: float = 0,
                        listener_x: float = 0, listener_y: float = 0):
        """Play appropriate combat sound based on attack type."""
        snd_name = self._COMBAT_SOUND_MAP.get(attack_type, "sword_hit")
        if x != 0 or y != 0:
            self.play_at(snd_name, x, y, listener_x, listener_y)
        else:
            self.play(snd_name)

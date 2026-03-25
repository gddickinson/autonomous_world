"""
Procedural background music system — generates and crossfades music loops
based on game state, biome, and location. No external audio files.
"""

import math
import numpy as np
import pygame

from game.audio.sound_generators import SAMPLE_RATE, make_sound

# ── Note frequencies (Hz) ────────────────────────────────────────────────
_NOTES = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
    "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99,
}

# ── Chord definitions (as note name lists) ───────────────────────────────
_CHORDS = {
    "C":  ["C4", "E4", "G4"],
    "Am": ["A3", "C4", "E4"],
    "F":  ["F3", "A3", "C4"],
    "G":  ["G3", "B3", "D4"],
    "Dm": ["D3", "F3", "A3"],
}

# ── Music states ─────────────────────────────────────────────────────────
STATE_PEACEFUL = "peaceful"
STATE_TENSION = "tension"
STATE_COMBAT = "combat"
STATE_TAVERN = "tavern"
STATE_TEMPLE = "temple"


def _sine_tone(freq, duration_s, volume=0.15):
    """Generate a sine wave tone as float array."""
    n = int(SAMPLE_RATE * duration_s)
    t = np.linspace(0, duration_s, n, endpoint=False)
    return np.sin(2 * np.pi * freq * t) * volume


def _chord_arp(chord_names, bpm, duration_s, volume=0.12):
    """Arpeggiate chord notes at given BPM, returning float samples."""
    note_dur = 60.0 / bpm
    samples = np.zeros(int(SAMPLE_RATE * duration_s))
    pos = 0
    idx = 0
    freqs = [_NOTES[n] for n in chord_names]
    while pos < len(samples):
        freq = freqs[idx % len(freqs)]
        n_samp = min(int(SAMPLE_RATE * note_dur), len(samples) - pos)
        t = np.linspace(0, n_samp / SAMPLE_RATE, n_samp, endpoint=False)
        tone = np.sin(2 * np.pi * freq * t) * volume
        # Fade in/out to avoid clicks
        fade = min(200, n_samp // 4)
        if fade > 0:
            tone[:fade] *= np.linspace(0, 1, fade)
            tone[-fade:] *= np.linspace(1, 0, fade)
        samples[pos:pos + n_samp] += tone
        pos += n_samp
        idx += 1
    return samples


def _noise_drum(duration_s=0.04, volume=0.3):
    """Short noise burst for percussion."""
    n = int(SAMPLE_RATE * duration_s)
    noise = np.random.uniform(-1, 1, n) * volume
    fade = n // 2
    if fade > 0:
        noise[-fade:] *= np.linspace(1, 0, fade)
    return noise


def _add_echo(samples, delay_s=0.3, decay=0.4):
    """Add a simple echo/delay effect."""
    delay_n = int(SAMPLE_RATE * delay_s)
    out = np.zeros(len(samples) + delay_n)
    out[:len(samples)] += samples
    out[delay_n:delay_n + len(samples)] += samples * decay
    return out[:len(samples)]


def _add_vibrato(samples, rate=5.0, depth=0.003):
    """Add vibrato by modulating playback position."""
    n = len(samples)
    t = np.arange(n) / SAMPLE_RATE
    mod = depth * SAMPLE_RATE * np.sin(2 * np.pi * rate * t)
    indices = np.arange(n) + mod
    indices = np.clip(indices, 0, n - 1).astype(int)
    return samples[indices]


# ── Loop generators ──────────────────────────────────────────────────────

def _gen_peaceful(duration_s=6.0):
    """Slow arpeggiated C-Am-F-G progression, sine waves, 60 BPM."""
    progression = ["C", "Am", "F", "G"]
    chord_dur = duration_s / len(progression)
    parts = []
    for chord_name in progression:
        notes = _CHORDS[chord_name]
        part = _chord_arp(notes, bpm=60, duration_s=chord_dur, volume=0.10)
        parts.append(part)
    return np.concatenate(parts)


def _gen_tension(duration_s=6.0):
    """Minor key drones with dissonant overtones."""
    samples = np.zeros(int(SAMPLE_RATE * duration_s))
    # Am drone - low octave
    t = np.linspace(0, duration_s, len(samples), endpoint=False)
    samples += np.sin(2 * np.pi * _NOTES["A3"] * 0.5 * t) * 0.08
    # Dm drone layered
    samples += np.sin(2 * np.pi * _NOTES["D3"] * 0.5 * t) * 0.06
    # Dissonant overtone (slightly detuned)
    samples += np.sin(2 * np.pi * (_NOTES["A3"] * 0.502) * t) * 0.04
    # Slow pulsing volume
    pulse = 0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * t)
    samples *= pulse
    # Fade edges
    fade = min(2000, len(samples) // 4)
    samples[:fade] *= np.linspace(0, 1, fade)
    samples[-fade:] *= np.linspace(1, 0, fade)
    return samples


def _gen_combat(duration_s=4.0):
    """Fast percussion + power chords at 120 BPM."""
    n_total = int(SAMPLE_RATE * duration_s)
    samples = np.zeros(n_total)
    beat_dur = 60.0 / 120.0  # 0.5 seconds per beat
    t_full = np.linspace(0, duration_s, n_total, endpoint=False)

    # Power chord drone (root + fifth)
    root_freq = _NOTES["A3"] * 0.5  # Low A
    fifth_freq = root_freq * 1.5
    samples += np.sin(2 * np.pi * root_freq * t_full) * 0.08
    samples += np.sin(2 * np.pi * fifth_freq * t_full) * 0.06
    # Square wave edge for aggression
    samples += 0.04 * np.sign(np.sin(2 * np.pi * root_freq * t_full))

    # Drum hits on beats
    pos = 0
    beat_idx = 0
    while pos < n_total:
        drum = _noise_drum(duration_s=0.04, volume=0.20)
        end = min(pos + len(drum), n_total)
        samples[pos:end] += drum[:end - pos]
        # Off-beat hi-hat (higher, shorter)
        offbeat_pos = pos + int(SAMPLE_RATE * beat_dur / 2)
        if offbeat_pos < n_total:
            hat = _noise_drum(duration_s=0.015, volume=0.10)
            hat_end = min(offbeat_pos + len(hat), n_total)
            samples[offbeat_pos:hat_end] += hat[:hat_end - offbeat_pos]
        pos += int(SAMPLE_RATE * beat_dur)
        beat_idx += 1

    fade = min(1000, n_total // 8)
    samples[:fade] *= np.linspace(0, 1, fade)
    samples[-fade:] *= np.linspace(1, 0, fade)
    return samples


def _gen_tavern(duration_s=4.0):
    """Jig-like fast tempo, bouncy major key at 140 BPM."""
    progression = ["C", "G", "Am", "F"]
    chord_dur = duration_s / len(progression)
    parts = []
    for chord_name in progression:
        notes = _CHORDS[chord_name]
        part = _chord_arp(notes, bpm=140, duration_s=chord_dur, volume=0.10)
        # Add rhythmic bounce (accent every other note)
        beat_n = int(SAMPLE_RATE * (60.0 / 140.0))
        for i in range(0, len(part), beat_n * 2):
            end = min(i + beat_n, len(part))
            part[i:end] *= 1.3
        parts.append(part)
    return np.concatenate(parts)


def _gen_temple(duration_s=6.0):
    """Slow choral chords with organ-like harmonics."""
    n = int(SAMPLE_RATE * duration_s)
    samples = np.zeros(n)
    t = np.linspace(0, duration_s, n, endpoint=False)
    # Sustained organ chord: C major with multiple harmonics
    for note in ["C3", "E3", "G3", "C4"]:
        freq = _NOTES[note]
        samples += np.sin(2 * np.pi * freq * t) * 0.06
        samples += np.sin(2 * np.pi * freq * 2 * t) * 0.03  # 2nd harmonic
        samples += np.sin(2 * np.pi * freq * 3 * t) * 0.015  # 3rd harmonic
    # Slow swell
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)
    samples *= swell
    fade = min(3000, n // 4)
    samples[:fade] *= np.linspace(0, 1, fade)
    samples[-fade:] *= np.linspace(1, 0, fade)
    return samples


# ── Biome modifiers ──────────────────────────────────────────────────────

def _mod_forest(samples):
    """Add flute-like high tones and bird chirp accents."""
    n = len(samples)
    t = np.linspace(0, n / SAMPLE_RATE, n, endpoint=False)
    # Flute: high sine with gentle vibrato
    flute_freq = _NOTES["E5"]
    vibrato = flute_freq + 8 * np.sin(2 * np.pi * 5 * t)
    phase = 2 * np.pi * np.cumsum(vibrato) / SAMPLE_RATE
    flute = np.sin(phase) * 0.03
    # Intermittent: only play during parts of the loop
    mask = (np.sin(2 * np.pi * 0.5 * t) > 0.3).astype(float)
    flute *= mask
    # Bird chirp accent at ~2s and ~4s
    for offset_s in [2.0, 4.0]:
        chirp_pos = int(SAMPLE_RATE * offset_s)
        chirp_n = min(int(SAMPLE_RATE * 0.06), n - chirp_pos)
        if chirp_n > 0:
            ct = np.linspace(0, chirp_n / SAMPLE_RATE, chirp_n, endpoint=False)
            chirp = np.sin(2 * np.pi * (2200 + 400 * np.sin(2 * np.pi * 30 * ct)) * ct) * 0.04
            chirp *= np.linspace(1, 0, chirp_n)
            flute[chirp_pos:chirp_pos + chirp_n] += chirp
    return samples + flute


def _mod_mountain(samples):
    """Deep resonant bass with echo-like delayed notes."""
    n = len(samples)
    t = np.linspace(0, n / SAMPLE_RATE, n, endpoint=False)
    bass = np.sin(2 * np.pi * 65 * t) * 0.05  # Deep C2
    bass = _add_echo(bass, delay_s=0.4, decay=0.5)
    return samples + bass


def _mod_desert(samples):
    """Sparse notes with wide spacing and vibrato on sustained tones."""
    n = len(samples)
    # Reduce existing volume (sparse feel)
    out = samples * 0.6
    # Add a few sustained vibrato notes
    note_dur_s = 1.5
    note_n = int(SAMPLE_RATE * note_dur_s)
    for i, note in enumerate(["A3", "D4", "A3"]):
        start = int(SAMPLE_RATE * (i * 2.0))
        if start + note_n > n:
            break
        tone = _sine_tone(_NOTES[note], note_dur_s, volume=0.07)
        tone = _add_vibrato(tone, rate=4.0, depth=0.004)
        fade_n = min(500, note_n // 3)
        tone[:fade_n] *= np.linspace(0, 1, fade_n)
        tone[-fade_n:] *= np.linspace(1, 0, fade_n)
        out[start:start + note_n] += tone
    return out


def _mod_ocean(samples):
    """Wave-like volume oscillation with gentle pitch drift."""
    n = len(samples)
    t = np.linspace(0, n / SAMPLE_RATE, n, endpoint=False)
    # Wave volume oscillation
    wave_env = 0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t)
    out = samples * wave_env
    # Gentle rising/falling pitch tone
    freq = 180 + 40 * np.sin(2 * np.pi * 0.2 * t)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave_tone = np.sin(phase) * 0.04
    return out + wave_tone


_BIOME_MODIFIERS = {
    "forest": _mod_forest,
    "mountain": _mod_mountain,
    "desert": _mod_desert,
    "ocean": _mod_ocean,
    "coast": _mod_ocean,
}

# ── State generators map ─────────────────────────────────────────────────
_STATE_GENERATORS = {
    STATE_PEACEFUL: _gen_peaceful,
    STATE_TENSION: _gen_tension,
    STATE_COMBAT: _gen_combat,
    STATE_TAVERN: _gen_tavern,
    STATE_TEMPLE: _gen_temple,
}

# Crossfade duration in seconds
_CROSSFADE_S = 2.0
# Channels: 0 = current layer, 1 = crossfade-out layer
_CH_CURRENT = 14
_CH_FADE = 15


class MusicSystem:
    """Procedural music that adapts to game state, biome, and location.

    Call update(game_state) each frame. game_state is a dict with keys:
        "in_combat": bool
        "hostiles_nearby": bool
        "biome": str  (forest, mountain, desert, ocean, grass, ...)
        "in_tavern": bool
        "in_temple": bool
        "master_volume": float  (0.0-1.0)
        "muted": bool
    """

    def __init__(self):
        self._enabled = True
        self._current_state = None
        self._current_biome = None
        self._volume = 0.5
        self._muted = False
        self._loops: dict[str, pygame.mixer.Sound] = {}
        self._crossfade_timer = 0.0
        self._crossfading = False
        self._fade_out_vol = 0.0

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16,
                                  channels=2, buffer=512)
            # Ensure enough channels
            cur = pygame.mixer.get_num_channels()
            if cur < 16:
                pygame.mixer.set_num_channels(16)
        except Exception as e:
            print(f"[MUSIC] Failed to initialize mixer: {e}")
            self._enabled = False

    def _get_loop(self, state: str, biome: str = "") -> pygame.mixer.Sound:
        """Get or generate a cached music loop."""
        key = f"{state}_{biome}" if biome and state == STATE_PEACEFUL else state
        if key in self._loops:
            return self._loops[key]

        gen = _STATE_GENERATORS.get(state)
        if gen is None:
            gen = _STATE_GENERATORS[STATE_PEACEFUL]

        samples = gen()

        # Apply biome modifier for peaceful state
        if state == STATE_PEACEFUL and biome in _BIOME_MODIFIERS:
            samples = _BIOME_MODIFIERS[biome](samples)

        # Clip and convert
        samples = np.clip(samples, -1.0, 1.0)
        snd = make_sound(samples)
        self._loops[key] = snd
        return snd

    def _determine_state(self, game_state: dict) -> tuple:
        """Determine music state and biome from game_state dict."""
        if game_state.get("in_combat", False):
            return STATE_COMBAT, ""
        if game_state.get("in_tavern", False):
            return STATE_TAVERN, ""
        if game_state.get("in_temple", False):
            return STATE_TEMPLE, ""
        if game_state.get("hostiles_nearby", False):
            return STATE_TENSION, ""
        biome = game_state.get("biome", "grass")
        return STATE_PEACEFUL, biome

    def update(self, game_state: dict):
        """Called each frame. Checks state and triggers crossfade if needed."""
        if not self._enabled:
            return

        vol = game_state.get("master_volume", 0.5)
        muted = game_state.get("muted", False)
        music_off = game_state.get("music_disabled", False)
        self._volume = max(0.0, min(1.0, vol * 0.4))  # music quieter than SFX
        self._muted = muted or music_off

        # If music is disabled, silence current playback
        if music_off:
            try:
                pygame.mixer.Channel(_CH_CURRENT).set_volume(0)
                pygame.mixer.Channel(_CH_FADE).set_volume(0)
            except Exception:
                pass
            return

        new_state, new_biome = self._determine_state(game_state)

        # Handle crossfade timing
        if self._crossfading:
            dt = game_state.get("dt", 1.0 / 60.0)
            self._crossfade_timer += dt
            progress = min(1.0, self._crossfade_timer / _CROSSFADE_S)

            ch_cur = pygame.mixer.Channel(_CH_CURRENT)
            ch_fade = pygame.mixer.Channel(_CH_FADE)

            eff_vol = 0.0 if self._muted else self._volume
            ch_cur.set_volume(eff_vol * progress)
            ch_fade.set_volume(eff_vol * (1.0 - progress))

            if progress >= 1.0:
                ch_fade.stop()
                self._crossfading = False
            return

        if new_state == self._current_state and new_biome == self._current_biome:
            # No change — just update volume
            if self._muted:
                pygame.mixer.Channel(_CH_CURRENT).set_volume(0)
            else:
                pygame.mixer.Channel(_CH_CURRENT).set_volume(self._volume)
            return

        # State changed — initiate crossfade
        self._start_crossfade(new_state, new_biome)

    def _start_crossfade(self, new_state: str, new_biome: str):
        """Begin crossfading from current to new music state."""
        try:
            ch_cur = pygame.mixer.Channel(_CH_CURRENT)
            ch_fade = pygame.mixer.Channel(_CH_FADE)
        except Exception:
            return

        # Move current sound to fade channel
        if self._current_state is not None:
            old_snd = self._get_loop(self._current_state, self._current_biome or "")
            ch_fade.play(old_snd, loops=-1)
            eff_vol = 0.0 if self._muted else self._volume
            ch_fade.set_volume(eff_vol)

        # Start new sound on current channel at zero volume
        new_snd = self._get_loop(new_state, new_biome)
        ch_cur.play(new_snd, loops=-1)
        ch_cur.set_volume(0)

        self._current_state = new_state
        self._current_biome = new_biome
        self._crossfade_timer = 0.0
        self._crossfading = True

    def stop(self):
        """Stop all music."""
        try:
            pygame.mixer.Channel(_CH_CURRENT).stop()
            pygame.mixer.Channel(_CH_FADE).stop()
        except Exception:
            pass
        self._current_state = None
        self._current_biome = None
        self._crossfading = False

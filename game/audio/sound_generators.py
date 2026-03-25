"""
Procedural sound effect generators using numpy waveforms.
Each function returns a pygame.mixer.Sound created from synthesized samples.
"""

import numpy as np
import pygame

SAMPLE_RATE = 22050


# ---------------------------------------------------------------------------
# Waveform helpers
# ---------------------------------------------------------------------------

def make_sound(samples_mono: np.ndarray) -> pygame.mixer.Sound:
    """Convert a mono float64 array (range -1..1) into a stereo pygame Sound."""
    clipped = np.clip(samples_mono, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    stereo = np.column_stack([pcm, pcm])
    return pygame.sndarray.make_sound(stereo)


def generate_tone(frequency: float, duration_ms: float,
                  volume: float = 0.3, wave: str = "sine") -> pygame.mixer.Sound:
    """Generate a simple tone."""
    n = max(1, int(SAMPLE_RATE * duration_ms / 1000))
    t = np.linspace(0, duration_ms / 1000, n, endpoint=False)
    if wave == "sine":
        samples = np.sin(2 * np.pi * frequency * t)
    elif wave == "square":
        samples = np.sign(np.sin(2 * np.pi * frequency * t))
    elif wave == "triangle":
        samples = 2 * np.abs(2 * (frequency * t % 1) - 1) - 1
    elif wave == "noise":
        samples = np.random.uniform(-1, 1, n)
    else:
        samples = np.sin(2 * np.pi * frequency * t)
    return make_sound(samples * volume)


def sweep(f_start: float, f_end: float, duration_ms: float,
          volume: float = 0.3, wave: str = "sine") -> np.ndarray:
    """Frequency sweep (linear) returning raw float samples."""
    n = max(1, int(SAMPLE_RATE * duration_ms / 1000))
    t = np.linspace(0, duration_ms / 1000, n, endpoint=False)
    freq = np.linspace(f_start, f_end, n)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    if wave == "sine":
        return np.sin(phase) * volume
    elif wave == "noise":
        env = np.linspace(1.0, 0.2, n)
        return np.random.uniform(-1, 1, n) * volume * env
    return np.sin(phase) * volume


def fade_env(n: int, fade_in: int = 0, fade_out: int = 0) -> np.ndarray:
    """Create an amplitude envelope with optional fade-in/out (in samples)."""
    env = np.ones(n)
    if 0 < fade_in < n:
        env[:fade_in] = np.linspace(0, 1, fade_in)
    if 0 < fade_out < n:
        env[-fade_out:] = np.linspace(1, 0, fade_out)
    return env


def concat(*arrays: np.ndarray) -> np.ndarray:
    """Concatenate sample arrays."""
    return np.concatenate(arrays)


# ---------------------------------------------------------------------------
# Sound effect generators
# ---------------------------------------------------------------------------

def gen_sword_hit() -> pygame.mixer.Sound:
    """Short noise burst + low tone."""
    noise = np.random.uniform(-1, 1, int(SAMPLE_RATE * 0.05)) * 0.4
    noise *= fade_env(len(noise), fade_out=int(SAMPLE_RATE * 0.02))
    n2 = int(SAMPLE_RATE * 0.03)
    t2 = np.linspace(0, 0.03, n2, endpoint=False)
    low = np.sin(2 * np.pi * 100 * t2) * 0.3
    low *= fade_env(n2, fade_out=n2 // 2)
    return make_sound(concat(noise, low))


def gen_arrow_fire() -> pygame.mixer.Sound:
    """Rising pitch swoosh 400->800Hz, 100ms."""
    samples = sweep(400, 800, 100, volume=0.25)
    samples *= fade_env(len(samples), fade_in=10, fade_out=len(samples) // 3)
    return make_sound(samples)


def gen_spell_cast() -> pygame.mixer.Sound:
    """Warbling tone 300-600Hz, 200ms with vibrato."""
    n = int(SAMPLE_RATE * 0.2)
    t = np.linspace(0, 0.2, n, endpoint=False)
    vibrato = 300 + 150 * np.sin(2 * np.pi * 8 * t)
    phase = 2 * np.pi * np.cumsum(vibrato) / SAMPLE_RATE
    samples = np.sin(phase) * 0.25
    samples *= fade_env(n, fade_in=n // 8, fade_out=n // 3)
    return make_sound(samples)


def gen_fireball_impact() -> pygame.mixer.Sound:
    """Low boom 60Hz 150ms + noise."""
    n1 = int(SAMPLE_RATE * 0.15)
    t1 = np.linspace(0, 0.15, n1, endpoint=False)
    boom = np.sin(2 * np.pi * 60 * t1) * 0.4
    boom *= fade_env(n1, fade_out=n1 // 2)
    noise = np.random.uniform(-1, 1, int(SAMPLE_RATE * 0.08)) * 0.25
    noise *= fade_env(len(noise), fade_out=len(noise) // 2)
    return make_sound(concat(boom, noise))


def gen_lightning() -> pygame.mixer.Sound:
    """Sharp crack (noise 20ms) + rumble (80Hz, 300ms)."""
    crack = np.random.uniform(-1, 1, int(SAMPLE_RATE * 0.02)) * 0.5
    n2 = int(SAMPLE_RATE * 0.3)
    t2 = np.linspace(0, 0.3, n2, endpoint=False)
    rumble = np.sin(2 * np.pi * 80 * t2) * 0.3
    rumble *= fade_env(n2, fade_in=10, fade_out=n2 // 2)
    return make_sound(concat(crack, rumble))


def gen_ice_shatter() -> pygame.mixer.Sound:
    """High freq noise burst 100ms + falling pitch."""
    noise = np.random.uniform(-1, 1, int(SAMPLE_RATE * 0.1)) * 0.35
    noise *= fade_env(len(noise), fade_out=len(noise) // 2)
    fall = sweep(1200, 400, 120, volume=0.2)
    fall *= fade_env(len(fall), fade_out=len(fall) // 2)
    return make_sound(concat(noise, fall))


def gen_footstep_stone() -> pygame.mixer.Sound:
    """Very short click (5ms noise)."""
    n = max(1, int(SAMPLE_RATE * 0.005))
    click = np.random.uniform(-1, 1, n) * 0.15
    click *= fade_env(n, fade_out=n // 2)
    return make_sound(click)


def gen_footstep_grass() -> pygame.mixer.Sound:
    """Soft short noise (15ms, low volume)."""
    n = int(SAMPLE_RATE * 0.015)
    noise = np.random.uniform(-1, 1, n) * 0.08
    noise *= fade_env(n, fade_out=n // 2)
    return make_sound(noise)


def gen_menu_click() -> pygame.mixer.Sound:
    """Short high ping 800Hz, 30ms."""
    n = int(SAMPLE_RATE * 0.03)
    t = np.linspace(0, 0.03, n, endpoint=False)
    ping = np.sin(2 * np.pi * 800 * t) * 0.25
    ping *= fade_env(n, fade_out=n // 2)
    return make_sound(ping)


def gen_quest_complete() -> pygame.mixer.Sound:
    """Rising chime: C-E-G arpeggio, 100ms each."""
    notes = [261.63, 329.63, 392.0]  # C4, E4, G4
    parts = []
    for freq in notes:
        n = int(SAMPLE_RATE * 0.1)
        t = np.linspace(0, 0.1, n, endpoint=False)
        tone = np.sin(2 * np.pi * freq * t) * 0.3
        tone *= fade_env(n, fade_in=n // 10, fade_out=n // 3)
        parts.append(tone)
    return make_sound(concat(*parts))


def gen_npc_greeting() -> pygame.mixer.Sound:
    """Short hum 200Hz, 50ms."""
    n = int(SAMPLE_RATE * 0.05)
    t = np.linspace(0, 0.05, n, endpoint=False)
    hum = np.sin(2 * np.pi * 200 * t) * 0.2
    hum *= fade_env(n, fade_out=n // 2)
    return make_sound(hum)


def gen_death_sound() -> pygame.mixer.Sound:
    """Falling pitch 400->100Hz, 300ms."""
    samples = sweep(400, 100, 300, volume=0.35)
    samples *= fade_env(len(samples), fade_out=len(samples) // 2)
    return make_sound(samples)


def gen_level_up() -> pygame.mixer.Sound:
    """Ascending arpeggio C-E-G-C, 80ms each, bright."""
    notes = [261.63, 329.63, 392.0, 523.25]  # C4 E4 G4 C5
    parts = []
    for freq in notes:
        n = int(SAMPLE_RATE * 0.08)
        t = np.linspace(0, 0.08, n, endpoint=False)
        tone = (np.sin(2 * np.pi * freq * t) * 0.25 +
                np.sin(2 * np.pi * freq * 2 * t) * 0.1)
        tone *= fade_env(n, fade_in=n // 10, fade_out=n // 3)
        parts.append(tone)
    return make_sound(concat(*parts))


def gen_gold_pickup() -> pygame.mixer.Sound:
    """High ting 1200Hz, 40ms."""
    n = int(SAMPLE_RATE * 0.04)
    t = np.linspace(0, 0.04, n, endpoint=False)
    ting = np.sin(2 * np.pi * 1200 * t) * 0.25
    ting *= fade_env(n, fade_out=n // 2)
    return make_sound(ting)


def gen_damage_taken() -> pygame.mixer.Sound:
    """Low thud 100Hz, 60ms."""
    n = int(SAMPLE_RATE * 0.06)
    t = np.linspace(0, 0.06, n, endpoint=False)
    thud = np.sin(2 * np.pi * 100 * t) * 0.35
    thud *= fade_env(n, fade_out=n // 2)
    return make_sound(thud)


def gen_shield_block() -> pygame.mixer.Sound:
    """Metallic clang: 400Hz + 800Hz, 50ms."""
    n = int(SAMPLE_RATE * 0.05)
    t = np.linspace(0, 0.05, n, endpoint=False)
    clang = (np.sin(2 * np.pi * 400 * t) * 0.2 +
             np.sin(2 * np.pi * 800 * t) * 0.15 +
             np.sin(2 * np.pi * 1200 * t) * 0.05)
    clang *= fade_env(n, fade_out=n // 2)
    return make_sound(clang)


def gen_dodge() -> pygame.mixer.Sound:
    """Quick swoosh: rising noise 30ms."""
    samples = sweep(200, 600, 30, volume=0.2, wave="noise")
    return make_sound(samples)


# ---------------------------------------------------------------------------
# Ambient generators
# ---------------------------------------------------------------------------

def gen_bird_chirp() -> pygame.mixer.Sound:
    """Single bird chirp — high tone warble."""
    n = int(SAMPLE_RATE * 0.08)
    t = np.linspace(0, 0.08, n, endpoint=False)
    freq = 2000 + 500 * np.sin(2 * np.pi * 25 * t)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    chirp = np.sin(phase) * 0.12
    chirp *= fade_env(n, fade_in=n // 6, fade_out=n // 3)
    return make_sound(chirp)


def gen_hammer_clink() -> pygame.mixer.Sound:
    """Metallic clink for village ambient."""
    n = int(SAMPLE_RATE * 0.03)
    t = np.linspace(0, 0.03, n, endpoint=False)
    clink = (np.sin(2 * np.pi * 600 * t) * 0.1 +
             np.sin(2 * np.pi * 1100 * t) * 0.06)
    clink *= fade_env(n, fade_out=n // 2)
    return make_sound(clink)


def gen_cricket() -> pygame.mixer.Sound:
    """High frequency soft tone for night ambient."""
    n = int(SAMPLE_RATE * 0.06)
    t = np.linspace(0, 0.06, n, endpoint=False)
    env = (np.sin(2 * np.pi * 40 * t) > 0).astype(float) * 0.5 + 0.5
    cricket = np.sin(2 * np.pi * 4500 * t) * 0.06 * env
    cricket *= fade_env(n, fade_in=n // 8, fade_out=n // 4)
    return make_sound(cricket)


def gen_water_wave() -> pygame.mixer.Sound:
    """Gentle wave-like filtered noise, 500ms loop."""
    n = int(SAMPLE_RATE * 0.5)
    noise = np.random.uniform(-1, 1, n)
    kernel_size = 30
    kernel = np.ones(kernel_size) / kernel_size
    filtered = np.convolve(noise, kernel, mode='same') * 0.1
    filtered *= fade_env(n, fade_in=n // 4, fade_out=n // 4)
    return make_sound(filtered)


# ---------------------------------------------------------------------------
# Registry: name -> generator function
# ---------------------------------------------------------------------------

SOUND_GENERATORS = {
    "sword_hit": gen_sword_hit,
    "arrow_fire": gen_arrow_fire,
    "spell_cast": gen_spell_cast,
    "fireball_impact": gen_fireball_impact,
    "lightning": gen_lightning,
    "ice_shatter": gen_ice_shatter,
    # footstep sounds removed (no longer used)
    "menu_click": gen_menu_click,
    "quest_complete": gen_quest_complete,
    "npc_greeting": gen_npc_greeting,
    "death_sound": gen_death_sound,
    "level_up": gen_level_up,
    "gold_pickup": gen_gold_pickup,
    "damage_taken": gen_damage_taken,
    "shield_block": gen_shield_block,
    "dodge": gen_dodge,
    "bird_chirp": gen_bird_chirp,
    "hammer_clink": gen_hammer_clink,
    "cricket": gen_cricket,
    "water_wave": gen_water_wave,
}

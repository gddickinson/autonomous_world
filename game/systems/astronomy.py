"""
Planetary astronomy — connects globe position to day/night cycles and seasons.

Edras has:
- An axial tilt of 23.5 degrees (similar to Earth)
- A year of 364 days (52 weeks of 7 days, exactly 4 seasons of 91 days)
- Two moons: Lunara (28-day cycle) and Thal (47-day cycle)

For a given latitude and day-of-year, this module calculates:
- Sunrise/sunset times (day length varies by season and latitude)
- Season (based on hemisphere and day-of-year)
- Solar elevation (affects temperature and crop growth)
- Moon phases
- Whether a Conjunction is near (both moons full simultaneously)

Aethermoor is centered at ~45°N latitude, so it experiences:
- Summer: ~16 hours of daylight, short warm nights
- Winter: ~8 hours of daylight, long cold nights
- Equinoxes: ~12 hours each
"""

import math
from typing import Tuple


# ================================================================
# PLANETARY CONSTANTS
# ================================================================

AXIAL_TILT = 23.5          # degrees
YEAR_LENGTH = 364          # game days per year
SEASON_LENGTH = 91         # days per season (364/4)
LUNARA_CYCLE = 28          # days for silver moon cycle
THAL_CYCLE = 47            # days for copper moon cycle
CONJUNCTION_INTERVAL = 1316  # LCM(28,47) — both moons align every ~3.6 years

# Solstice/equinox day numbers (northern hemisphere)
SPRING_EQUINOX = 0         # Day 0 = start of spring
SUMMER_SOLSTICE = 91       # Longest day
AUTUMN_EQUINOX = 182       # Equal day/night
WINTER_SOLSTICE = 273      # Shortest day

# Reference latitude for Aethermoor
AETHERMOOR_LATITUDE = 45.0  # degrees north


# ================================================================
# DAY LENGTH CALCULATION
# ================================================================

def calc_solar_declination(day_of_year: int) -> float:
    """Calculate the sun's declination angle in degrees for a given day of year.
    This determines how high the sun gets and how long the day is.
    """
    # Sinusoidal model: max at summer solstice, min at winter solstice
    angle = 2 * math.pi * (day_of_year - SUMMER_SOLSTICE) / YEAR_LENGTH
    return AXIAL_TILT * math.cos(angle)


def calc_day_length(latitude: float, day_of_year: int) -> float:
    """Calculate hours of daylight for a given latitude and day of year.
    Returns hours (0-24). Handles polar day/night at extreme latitudes.
    """
    declination = calc_solar_declination(day_of_year)
    lat_rad = math.radians(latitude)
    dec_rad = math.radians(declination)

    # Hour angle at sunrise/sunset
    cos_hour_angle = -math.tan(lat_rad) * math.tan(dec_rad)

    # Polar day (sun never sets)
    if cos_hour_angle < -1.0:
        return 24.0
    # Polar night (sun never rises)
    if cos_hour_angle > 1.0:
        return 0.0

    hour_angle = math.acos(cos_hour_angle)
    return (2.0 * hour_angle / math.pi) * 12.0


def calc_sunrise_sunset(latitude: float, day_of_year: int) -> Tuple[float, float]:
    """Calculate sunrise and sunset as normalized day fractions (0.0-1.0).
    Returns (sunrise, sunset) where 0.0 = midnight, 0.5 = noon.
    """
    day_hours = calc_day_length(latitude, day_of_year)

    if day_hours >= 24.0:
        return (0.0, 1.0)  # polar day
    if day_hours <= 0.0:
        return (0.5, 0.5)  # polar night

    # Center daylight around noon (0.5)
    half_day = day_hours / 48.0  # half of day fraction
    sunrise = 0.5 - half_day
    sunset = 0.5 + half_day
    return (sunrise, sunset)


def calc_dawn_dusk(latitude: float, day_of_year: int) -> Tuple[float, float, float, float]:
    """Calculate dawn, sunrise, sunset, dusk as normalized day fractions.
    Twilight is ~1 hour (1/24 of a day = 0.042 normalized).
    Returns (dawn_start, day_start, dusk_start, night_start).
    """
    sunrise, sunset = calc_sunrise_sunset(latitude, day_of_year)
    twilight = 1.0 / 24.0  # 1 hour of twilight

    dawn_start = max(0.0, sunrise - twilight / 2)
    day_start = sunrise
    dusk_start = sunset
    night_start = min(1.0, sunset + twilight / 2)

    return (dawn_start, day_start, dusk_start, night_start)


# ================================================================
# SEASON CALCULATION
# ================================================================

def calc_season(latitude: float, day_of_year: int) -> str:
    """Calculate the current season based on hemisphere and day of year."""
    # Northern hemisphere seasons
    if day_of_year < SUMMER_SOLSTICE:
        nh_season = "spring"
    elif day_of_year < AUTUMN_EQUINOX:
        nh_season = "summer"
    elif day_of_year < WINTER_SOLSTICE:
        nh_season = "autumn"
    else:
        nh_season = "winter"

    # Southern hemisphere: flip seasons
    if latitude < 0:
        flip = {"spring": "autumn", "summer": "winter",
                "autumn": "spring", "winter": "summer"}
        return flip[nh_season]

    return nh_season


def calc_solar_intensity(latitude: float, day_of_year: int) -> float:
    """Calculate relative solar intensity (0.0-1.0) affecting temperature and crops.
    Higher at low latitudes and summer, lower at high latitudes and winter.
    """
    declination = calc_solar_declination(day_of_year)
    # Max solar elevation at noon
    max_elevation = 90 - abs(latitude - declination)
    # Normalize to 0-1 range
    return max(0.0, min(1.0, max_elevation / 90.0))


# ================================================================
# MOON PHASES
# ================================================================

def calc_moon_phase(day: int, cycle: int) -> float:
    """Calculate moon phase as 0.0-1.0 (0.0 = new moon, 0.5 = full moon)."""
    return (day % cycle) / cycle


def calc_lunara_phase(day: int) -> Tuple[float, str]:
    """Calculate Lunara (silver moon) phase. Returns (phase_float, phase_name)."""
    phase = calc_moon_phase(day, LUNARA_CYCLE)
    return (phase, _phase_name(phase))


def calc_thal_phase(day: int) -> Tuple[float, str]:
    """Calculate Thal (copper moon) phase. Returns (phase_float, phase_name)."""
    phase = calc_moon_phase(day, THAL_CYCLE)
    return (phase, _phase_name(phase))


def _phase_name(phase: float) -> str:
    """Convert phase fraction to human-readable name."""
    if phase < 0.06 or phase > 0.94:
        return "new"
    elif phase < 0.19:
        return "waxing crescent"
    elif phase < 0.31:
        return "first quarter"
    elif phase < 0.44:
        return "waxing gibbous"
    elif phase < 0.56:
        return "full"
    elif phase < 0.69:
        return "waning gibbous"
    elif phase < 0.81:
        return "last quarter"
    else:
        return "waning crescent"


def is_conjunction_near(day: int, threshold: int = 3) -> bool:
    """Check if both moons are near full simultaneously (Conjunction)."""
    lunara = calc_moon_phase(day, LUNARA_CYCLE)
    thal = calc_moon_phase(day, THAL_CYCLE)
    # Both near full (0.5 ± tolerance)
    lunara_full = abs(lunara - 0.5) < 0.1
    thal_full = abs(thal - 0.5) < 0.1
    return lunara_full and thal_full


# ================================================================
# CONVENIENCE: all astronomical data for a given position and day
# ================================================================

def get_astronomy(latitude: float, day: int) -> dict:
    """Get all astronomical data for a given latitude and game day.

    Args:
        latitude: degrees (-90 to +90)
        day: game day number (1-based)

    Returns dict with:
        day_of_year, season, day_length_hours, sunrise, sunset,
        dawn_start, day_start, dusk_start, night_start,
        solar_intensity, lunara_phase, thal_phase, conjunction_near
    """
    day_of_year = (day - 1) % YEAR_LENGTH

    dawn, day_start, dusk, night = calc_dawn_dusk(latitude, day_of_year)
    lunara_val, lunara_name = calc_lunara_phase(day)
    thal_val, thal_name = calc_thal_phase(day)

    return {
        "day_of_year": day_of_year,
        "year": (day - 1) // YEAR_LENGTH + 1,
        "season": calc_season(latitude, day_of_year),
        "day_length_hours": calc_day_length(latitude, day_of_year),
        "sunrise": calc_sunrise_sunset(latitude, day_of_year)[0],
        "sunset": calc_sunrise_sunset(latitude, day_of_year)[1],
        "dawn_start": dawn,
        "day_start": day_start,
        "dusk_start": dusk,
        "night_start": night,
        "solar_intensity": calc_solar_intensity(latitude, day_of_year),
        "lunara_phase": lunara_val,
        "lunara_name": lunara_name,
        "thal_phase": thal_val,
        "thal_name": thal_name,
        "conjunction_near": is_conjunction_near(day),
    }

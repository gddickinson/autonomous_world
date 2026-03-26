"""God Disguise System — gods can take any form.

When a god chooses a disguise, their sprite, name, race, and class
appear as the chosen identity to all NPCs and in the renderer.
The god retains all divine powers regardless of form.
"""

from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class Disguise:
    """A god's chosen form."""
    name: str
    race: str
    char_class: str
    form_type: str  # "humanoid", "creature", "npc", "invisible"
    # Visual overrides
    body_color: tuple = (180, 160, 130)  # skin/body tint
    clothing_color: tuple = (100, 80, 60)  # torso/clothing
    hair_color: tuple = (80, 60, 40)
    size_scale: float = 1.0  # 0.5 = halfling-sized, 2.0 = giant
    # Creature form
    creature_kind: str = ""  # e.g. "wolf", "eagle", "bear"
    # Special
    glow: bool = False  # divine glow visible
    invisible: bool = False


# Pre-built disguise templates
DISGUISE_TEMPLATES: Dict[str, Disguise] = {
    "wandering_merchant": Disguise(
        name="Mysterious Stranger", race="Human", char_class="Rogue",
        form_type="humanoid", body_color=(170, 140, 110),
        clothing_color=(80, 70, 50), hair_color=(60, 50, 30)),
    "old_hermit": Disguise(
        name="Old Hermit", race="Human", char_class="Wizard",
        form_type="humanoid", body_color=(190, 170, 150),
        clothing_color=(100, 90, 80), hair_color=(200, 200, 200),
        size_scale=0.9),
    "noble_knight": Disguise(
        name="Knight Errant", race="Human", char_class="Fighter",
        form_type="humanoid", body_color=(160, 140, 120),
        clothing_color=(140, 140, 150), hair_color=(40, 30, 20),
        size_scale=1.1),
    "elven_sage": Disguise(
        name="Elven Sage", race="Elf", char_class="Wizard",
        form_type="humanoid", body_color=(210, 200, 180),
        clothing_color=(60, 80, 120), hair_color=(220, 210, 180)),
    "dwarven_smith": Disguise(
        name="Dwarven Smith", race="Dwarf", char_class="Commoner",
        form_type="humanoid", body_color=(180, 150, 120),
        clothing_color=(100, 70, 40), hair_color=(140, 80, 30),
        size_scale=0.8),
    "orc_warlord": Disguise(
        name="Orc Warlord", race="Half-Orc", char_class="Fighter",
        form_type="humanoid", body_color=(120, 150, 100),
        clothing_color=(80, 60, 40), hair_color=(30, 30, 30),
        size_scale=1.2),
    "beggar": Disguise(
        name="Beggar", race="Human", char_class="Commoner",
        form_type="humanoid", body_color=(160, 140, 120),
        clothing_color=(90, 80, 70), hair_color=(100, 90, 80),
        size_scale=0.9),
    "child": Disguise(
        name="Lost Child", race="Human", char_class="Commoner",
        form_type="humanoid", body_color=(200, 180, 160),
        clothing_color=(120, 100, 140), hair_color=(140, 100, 60),
        size_scale=0.6),
    "wolf": Disguise(
        name="Wolf", race="Beast", char_class="Creature",
        form_type="creature", creature_kind="wolf",
        body_color=(130, 120, 100), size_scale=0.8),
    "eagle": Disguise(
        name="Eagle", race="Beast", char_class="Creature",
        form_type="creature", creature_kind="eagle",
        body_color=(100, 80, 50), size_scale=0.6),
    "bear": Disguise(
        name="Bear", race="Beast", char_class="Creature",
        form_type="creature", creature_kind="bear",
        body_color=(120, 90, 60), size_scale=1.5),
    "dragon": Disguise(
        name="Dragon", race="Dragon", char_class="Creature",
        form_type="creature", creature_kind="dragon",
        body_color=(180, 50, 30), size_scale=2.0, glow=True),
    "invisible": Disguise(
        name="", race="", char_class="",
        form_type="invisible", invisible=True),
    "true_form": Disguise(
        name="", race="God", char_class="God",
        form_type="humanoid", body_color=(255, 230, 150),
        clothing_color=(200, 180, 100), hair_color=(255, 240, 180),
        size_scale=1.3, glow=True),
}


class GodDisguiseManager:
    """Manages a god player's current disguise/form."""

    def __init__(self, player):
        self.player = player
        self.current_disguise: Optional[Disguise] = None
        self._true_name = player.name
        self._true_race = getattr(player, 'race', 'Human')
        self._true_class = getattr(player, 'char_class', 'God')

    def set_disguise(self, template_name: str) -> bool:
        """Apply a disguise template. Returns True on success."""
        template = DISGUISE_TEMPLATES.get(template_name)
        if not template:
            return False
        self.current_disguise = Disguise(
            name=template.name or self._true_name,
            race=template.race,
            char_class=template.char_class,
            form_type=template.form_type,
            body_color=template.body_color,
            clothing_color=template.clothing_color,
            hair_color=template.hair_color,
            size_scale=template.size_scale,
            creature_kind=template.creature_kind,
            glow=template.glow,
            invisible=template.invisible,
        )
        # Apply visual identity to player
        self.player.name = self.current_disguise.name
        self.player.race = self.current_disguise.race
        self.player.char_class = self.current_disguise.char_class
        # Store overrides for the renderer
        self.player._disguise = self.current_disguise
        return True

    def set_custom_disguise(self, name: str, race: str, char_class: str,
                            body_color: tuple = None) -> bool:
        """Create a custom disguise with specific identity."""
        self.current_disguise = Disguise(
            name=name, race=race, char_class=char_class,
            form_type="humanoid",
            body_color=body_color or (170, 150, 130),
            clothing_color=(100, 80, 60),
            hair_color=(80, 60, 40),
        )
        self.player.name = name
        self.player.race = race
        self.player.char_class = char_class
        self.player._disguise = self.current_disguise
        return True

    def reveal_true_form(self):
        """Drop all disguises and reveal the god."""
        self.current_disguise = DISGUISE_TEMPLATES["true_form"]
        self.player.name = self._true_name
        self.player.race = self._true_race
        self.player.char_class = self._true_class
        self.player._disguise = self.current_disguise

    def remove_disguise(self):
        """Return to default god appearance (no special disguise)."""
        self.current_disguise = None
        self.player.name = self._true_name
        self.player.race = self._true_race
        self.player.char_class = self._true_class
        self.player._disguise = None

    @property
    def is_disguised(self) -> bool:
        return self.current_disguise is not None

    @property
    def is_invisible(self) -> bool:
        return self.current_disguise and self.current_disguise.invisible

    @property
    def is_creature_form(self) -> bool:
        return (self.current_disguise and
                self.current_disguise.form_type == "creature")

    def get_template_names(self) -> List[str]:
        """Return all available disguise template names."""
        return list(DISGUISE_TEMPLATES.keys())

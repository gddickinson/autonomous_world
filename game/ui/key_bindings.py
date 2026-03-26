"""Shared key binding data for all help/controls overlays.

This is the single source of truth for key bindings displayed in the
controls overlay and context-aware help screen. Each entry is:
    (context_tag, category_name, [(key_label, action_description), ...])

Context tags control which bindings appear in the context-aware help screen.
The full controls overlay shows all bindings regardless of context.
"""

# Context tags:
#   "universal"  - always shown
#   "movement"   - shown when player can move
#   "mortal"     - mortal mode actions
#   "combat"     - combat abilities
#   "spellcaster"- spellcaster keys
#   "god"        - god mode keys
#   "god_panel"  - god panel open
#   "god_events" - divine event menu
#   "god_kingdom"- kingdom commands menu
#   "god_spawn"  - spawn menu
#   "god_divine_realm" - in divine realm
#   "inventory"  - inventory panel open
#   "character"  - character sheet open
#   "quest_log"  - quest log open
#   "chronicle"  - chronicle open
#   "dialog"     - dialog active
#   "shop"       - shop active
#   "world_map"  - world map open
#   "planet_view"- planet view open
#   "crafting"   - crafting menu open
#   "skill_tree" - skill tree open
#   "fast_travel"- fast travel UI active
#   "quest_board"- quest board open
#   "dead"       - player is dead
#   "panels"     - UI panel toggles
#   "camera_3d"  - 3D camera controls
#   "system"     - system keys
#   "npc_nearby" - NPC is nearby
#   "tavern"     - near a tavern
#   "building"   - inside a building

KEY_BINDINGS = [
    # -- Universal --
    ("universal", "System", [
        ("Esc", "Close panel / pause"),
        ("F12", "Screenshot"),
        ("?", "Controls overlay"),
        ("Shift+H", "Context help"),
    ]),

    # -- Movement --
    ("movement", "Movement", [
        ("W/A/S/D", "Move character"),
        ("Arrow Keys", "Move / scroll camera"),
        ("Shift+Move", "Run"),
        ("Ctrl+Move", "Sneak"),
        ("Shift+Ctrl", "Sprint"),
    ]),

    # -- Mortal actions --
    ("mortal", "Actions", [
        ("E", "Interact / talk / enter"),
        ("Space", "Attack"),
        ("T", "Free-text talk (LLM)"),
        ("X", "Examine"),
        ("G", "Drop item"),
        ("R", "Recruit companion"),
        ("Tab", "Cycle nearby NPC"),
    ]),

    ("panels", "Panels", [
        ("I", "Inventory"),
        ("C", "Character sheet"),
        ("Q", "Quest log"),
        ("H", "Chronicle"),
        ("B", "Settlement info"),
        ("L", "Combat log"),
        ("U", "Crafting menu"),
        ("O", "Skill tree"),
        ("M", "Planet view"),
        ("F", "World map"),
        ("N", "Minimap"),
        ("Y", "Fast travel"),
    ]),

    ("mortal", "View & System", [
        ("V", "Cycle view mode"),
        ("Z", "Interior zoom"),
        ("P", "Auto-play"),
        ("` (Backtick)", "LLM console"),
        ("Shift+R", "Relationships"),
        ("Shift+J", "Road builder"),
        ("J", "Highlight objects"),
        ("K", "Highlight picker"),
    ]),

    # -- Combat --
    ("combat", "Combat Abilities", [
        ("Space", "Basic attack"),
        ("F1", "Power Strike"),
        ("F2", "Whirlwind"),
        ("F3", "Keen Eye"),
        ("F4", "Charm"),
        ("F5", "Scout"),
    ]),

    # -- Spellcaster --
    ("spellcaster", "Spellcasting", [
        ("1-9", "Cast spell (hotbar)"),
        ("Shift+S", "Spell list"),
        (", / [", "Prev hotbar page"),
        (". / ]", "Next hotbar page"),
    ]),

    # -- NPC nearby --
    ("npc_nearby", "NPC Interaction", [
        ("E", "Talk to NPC"),
        ("T", "Free-text chat"),
        ("Tab", "Cycle NPC target"),
    ]),

    # -- Building --
    ("building", "Building", [
        ("E", "Use object / stairs"),
        ("Shift+E", "Go further up/down"),
        ("Z", "Toggle interior zoom"),
    ]),

    # -- Tavern --
    ("tavern", "Tavern", [
        ("E", "Interact (bed, bar, etc.)"),
    ]),

    # -- Dialog --
    ("dialog", "Dialog", [
        ("Up/Down", "Navigate options"),
        ("E / Enter", "Select option"),
        ("T", "Free-text input"),
        ("Esc", "Close dialog"),
    ]),

    # -- Inventory --
    ("inventory", "Inventory", [
        ("I / Esc", "Close inventory"),
        ("Tab", "Switch tab"),
        ("Up/Down", "Navigate items"),
        ("E / Enter", "Use / equip"),
        ("X / G", "Drop item"),
    ]),

    # -- Character --
    ("character", "Character Sheet", [
        ("C / Esc", "Close"),
    ]),

    # -- Quest log --
    ("quest_log", "Quest Log", [
        ("Q / Esc", "Close"),
    ]),

    # -- Chronicle --
    ("chronicle", "Chronicle", [
        ("H / Esc", "Close"),
        ("Up/Down", "Scroll"),
        ("PgUp/PgDn", "Fast scroll"),
        ("Home/End", "Jump to top/bottom"),
    ]),

    # -- World map --
    ("world_map", "World Map", [
        ("F / M / Esc", "Close map"),
        ("WASD/Arrows", "Pan"),
        ("+/-", "Zoom"),
        ("Home", "Center on player"),
        ("T", "Toggle labels"),
    ]),

    # -- Planet view --
    ("planet_view", "Planet View", [
        ("Left/Right", "Rotate"),
        ("Up/Down", "Tilt"),
        ("+/-", "Zoom"),
        ("A", "Toggle atmosphere"),
        ("Tab", "Cycle display"),
    ]),

    # -- Crafting --
    ("crafting", "Crafting", [
        ("Esc", "Close"),
        ("Left/Right", "Switch category"),
        ("Up/Down", "Navigate recipes"),
        ("E / Enter", "Craft item"),
    ]),

    # -- Skill tree --
    ("skill_tree", "Skill Tree", [
        ("Esc", "Close"),
        ("Left/Right", "Switch category"),
        ("Up/Down", "Navigate skills"),
        ("E / Enter", "Unlock skill"),
    ]),

    # -- Fast travel --
    ("fast_travel", "Fast Travel", [
        ("Esc", "Cancel"),
        ("Up/Down", "Navigate"),
        ("E / Enter", "Confirm"),
    ]),

    # -- Quest board --
    ("quest_board", "Quest Board", [
        ("Up/Down", "Navigate"),
        ("E / Enter", "Accept quest"),
        ("Esc / Q", "Close"),
    ]),

    # -- Shop --
    ("shop", "Shop", [
        ("Tab", "Switch buy/sell"),
        ("Up/Down", "Navigate"),
        ("E / Enter", "Buy / sell"),
        ("Esc", "Close"),
    ]),

    # -- Dead --
    ("dead", "You Died", [
        ("R", "Respawn"),
    ]),

    # -- 3D camera --
    ("camera_3d", "3D Camera", [
        ("Arrows", "Rotate camera"),
        ("+/-", "Zoom"),
        ("[ / ]", "View radius"),
    ]),

    # -- God mode --
    ("god", "God Mode", [
        ("Tab", "Divine Dashboard"),
        ("G", "Divine event menu"),
        ("K", "Kingdom commands"),
        ("Shift+N", "Spawn menu"),
        ("D", "Disguise / shapeshift"),
        ("P", "Pause / resume time"),
        ("[ / ]", "Time speed"),
        (". (Period)", "Step one tick"),
        ("F5 / Home", "Toggle divine realm"),
        ("F10", "Claude chat"),
        ("Shift+K", "API key config"),
        ("` (Backtick)", "Python console"),
        ("F11", "God panel"),
    ]),

    ("god_panel", "God Panel Tools", [
        ("1-5", "Select tool"),
        ("6", "Transmute tool"),
        ("7", "Settle tool"),
        ("F1-F5", "Switch tab"),
        ("F6", "Parameter tweaker"),
        ("F7", "Hot reload modules"),
    ]),

    ("god_divine_realm", "Divine Realm", [
        ("V", "Viewing pool"),
        ("Home/F5", "Exit to mortal world"),
    ]),

    ("god_events", "Event Menu (G)", [
        ("1", "Drought"),
        ("2", "Plague"),
        ("3", "Festival"),
        ("4", "Monster wave"),
        ("5", "Gold rain"),
        ("6", "Famine"),
        ("7", "Inspiration"),
        ("8", "Earthquake"),
        ("Esc", "Close"),
    ]),

    ("god_kingdom", "Kingdom Menu (K)", [
        ("1", "Declare war"),
        ("2", "Declare peace"),
        ("3", "Recruit army"),
        ("4", "Fortify"),
        ("5", "Boost economy"),
        ("6", "Change government"),
        ("Esc", "Close"),
    ]),

    ("god_spawn", "Spawn Menu (Shift+N)", [
        ("1", "Spawn creature"),
        ("2", "Spawn NPC"),
        ("Esc", "Close"),
    ]),

    ("system", "System", [
        ("F8", "Mute sound"),
        ("F9", "Mute music"),
    ]),
]


def get_bindings_for_context(context_tags):
    """Return list of [category, bindings] for the given set of context tags."""
    result = []
    seen_cats = set()
    for tag, category, bindings in KEY_BINDINGS:
        if tag in context_tags:
            if category in seen_cats:
                for existing in result:
                    if existing[0] == category:
                        existing[1].extend(bindings)
                        break
            else:
                result.append([category, list(bindings)])
                seen_cats.add(category)
    return result

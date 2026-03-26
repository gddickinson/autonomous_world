# Controls Reference

All key bindings for the game, organized by context.
Keys are listed by the context in which they are active.

---

## Universal (Always Available)

| Key | Action |
|-----|--------|
| F12 | Take screenshot |
| Esc | Close current panel / pause menu |

---

## Movement (Continuous / Held Keys)

Active when no panel is open and not in a text input.

| Key | Action |
|-----|--------|
| W / Up Arrow | Move up |
| A / Left Arrow | Move left |
| S / Down Arrow | Move down |
| D / Right Arrow | Move right (mortal only; D is Disguise in god mode) |
| Shift + Move | Run |
| Ctrl + Move | Sneak |
| Shift + Ctrl + Move | Sprint |
| Caps Lock + Move | Jog |

---

## Mortal Mode - Actions (KEYDOWN)

These fire on key press when no UI panel is blocking input.

| Key | Action |
|-----|--------|
| E | Interact / talk / pick up / enter building |
| Space | Attack / swing weapon |
| T | Free-text talk to NPC (LLM) |
| X | Examine nearby object or entity |
| G | Drop selected inventory item |
| R | Recruit companion |
| Tab | Cycle nearby NPC target |
| Shift+R | Relationship panel |
| Shift+J | Road building mode |

---

## UI Panels (Mortal Mode)

Toggle panels on/off. When a panel is open, its own keys take priority.

| Key | Action |
|-----|--------|
| I | Inventory |
| C | Character sheet |
| Q | Quest log |
| H | Chronicle / history log |
| B | Settlement info panel |
| L | Combat log |
| U | Crafting menu |
| O | Skill tree |
| M | Planet / globe view |
| F | World map |
| N | Toggle minimap |
| Y | Fast travel |

---

## Combat Abilities (Mortal Mode)

| Key | Action |
|-----|--------|
| Space | Basic attack |
| F1 | Power Strike ability |
| F2 | Whirlwind ability |
| F3 | Keen Eye ability |
| F4 | Charm ability |
| F5 | Scout ability |

---

## Spellcasting (Mortal Mode - Spellcasters Only)

| Key | Action |
|-----|--------|
| 1-9 | Cast spell from hotbar slot |
| Shift+S | Toggle full spell list |
| , / [ | Previous hotbar page |
| . / ] | Next hotbar page |
| Up/Down | Scroll spell list (when list is open) |

---

## Camera & View (Mortal Mode)

| Key | Action |
|-----|--------|
| V | Cycle view mode (2D / 3D) |
| Z | Interior zoom toggle |
| P | Toggle auto-play |

---

## 3D Camera Controls

Active only in 3D view mode.

| Key | Action |
|-----|--------|
| Left/Right Arrow | Rotate camera azimuth |
| Up/Down Arrow | Rotate camera elevation |
| = / + | Zoom in |
| - | Zoom out |
| [ | Decrease view radius |
| ] | Increase view radius |

---

## System Keys

| Key | Action |
|-----|--------|
| ? (Shift+/) | Controls overlay / help screen |
| Shift+H | Context-aware help screen |
| ` (Backtick) | LLM console (mortal) / Python console (god) |
| F6 | Cycle overlay mode (mortal) |
| F7 | Skip tutorial step (mortal) |
| F8 | Toggle sound mute |
| F9 | Toggle music mute |
| F12 | Screenshot |

---

## Inventory Panel (When Open)

| Key | Action |
|-----|--------|
| I / Esc | Close inventory |
| Tab | Switch inventory tab |
| Up/Down | Navigate items |
| E / Enter | Use / equip selected item |
| X / G | Drop selected item |

---

## Character Sheet (When Open)

| Key | Action |
|-----|--------|
| C / Esc | Close character sheet |

---

## Quest Log (When Open)

| Key | Action |
|-----|--------|
| Q / Esc | Close quest log |

---

## Chronicle Panel (When Open)

| Key | Action |
|-----|--------|
| H / Esc | Close chronicle |
| Up/Down | Scroll entries |
| Page Up/Down | Fast scroll |
| Home/End | Jump to top/bottom |

---

## Dialog (When Talking to NPC)

| Key | Action |
|-----|--------|
| Up/Down | Navigate dialog options |
| E / Enter | Select dialog option |
| T | Free-text input mode |
| Esc | Close dialog |

---

## Shop (When Open)

| Key | Action |
|-----|--------|
| Tab | Switch buy/sell tab |
| Up/Down | Navigate items |
| E / Enter | Buy/sell selected item |
| Esc | Close shop |

---

## World Map (When Open)

| Key | Action |
|-----|--------|
| F / M / Esc | Close world map |
| WASD / Arrows | Pan map |
| = / + | Zoom in |
| - | Zoom out |
| Home | Center on player |
| T | Toggle settlement labels |
| Y / Enter | Confirm fast travel |
| N / Esc | Cancel fast travel prompt |

---

## Planet View (When Open)

| Key | Action |
|-----|--------|
| Left/Right | Rotate globe |
| Up/Down | Tilt globe |
| = / + | Zoom in |
| - | Zoom out |
| A | Toggle atmosphere |
| Tab | Cycle display mode |

---

## Crafting Menu (When Open)

| Key | Action |
|-----|--------|
| Esc | Close crafting |
| Left/Right | Switch category |
| Up/Down / W/S | Navigate recipes |
| E / Enter | Craft selected item |

---

## Skill Tree (When Open)

| Key | Action |
|-----|--------|
| Esc | Close skill tree |
| Left/Right | Switch category |
| Up/Down / W/S | Navigate skills |
| E / Enter | Unlock selected skill |

---

## Fast Travel (When Open)

| Key | Action |
|-----|--------|
| Esc | Cancel fast travel |
| W / Up | Previous destination |
| S / Down | Next destination |
| E / Enter | Confirm travel |

---

## Quest Board (When Open)

| Key | Action |
|-----|--------|
| W / Up | Previous quest |
| S / Down | Next quest |
| E / Enter | Accept quest |
| Esc / Q | Close board |

---

## Board Selection Menu

| Key | Action |
|-----|--------|
| 1 | Quest board |
| 2 | Message board |
| Esc / Q | Close menu |

---

## Death Screen

| Key | Action |
|-----|--------|
| R | Respawn |

---

## Object Highlighting

| Key | Action |
|-----|--------|
| J | Toggle object highlighting / cycle category |
| K | Toggle highlight color picker |

---

## God Mode - Divine Commands

Active only in god mode. These override mortal-mode bindings for the same keys.

| Key | Action |
|-----|--------|
| Tab | Toggle Divine Dashboard |
| G | Open divine event menu (target nearest settlement) |
| K | Open kingdom commands menu |
| Shift+N | Open spawn menu |
| D | Disguise / shapeshift menu |
| P | Pause / resume time |
| [ | Decrease time speed |
| ] | Increase time speed |
| . (Period) | Step one tick (when paused) |
| Shift+K | API key configuration |
| F10 | Claude chat |
| F5 / Home | Toggle divine realm |
| V | Viewing pool (in divine realm) |

---

## God Mode - God Panel (F11)

| Key | Action |
|-----|--------|
| F11 | Toggle god panel |
| Esc | Close god panel |
| F1 | Settlement tab |
| F2 | NPC tab |
| F3 | Economy tab |
| F4 | World tab |
| F5 | Timeline tab |
| 1 | Inspect tool |
| 2 | Paint tool |
| 3 | Spawn tool |
| 4 | Build tool |
| 5 | Edit tool |
| Up/Down | Scroll panel content |

---

## God Mode - God Tools (Extended)

| Key | Action |
|-----|--------|
| 6 | Transmute tool |
| 7 | Settle tool |
| ` (Backtick) | Python console |
| F6 | Parameter tweaker |
| F7 | Hot reload all modules |

---

## God Mode - Divine Event Menu (G)

Active after pressing G in god mode.

| Key | Action |
|-----|--------|
| 1 | Trigger drought |
| 2 | Trigger plague |
| 3 | Trigger festival |
| 4 | Trigger monster wave |
| 5 | Trigger gold rain |
| 6 | Trigger famine |
| 7 | Trigger inspiration |
| 8 | Trigger earthquake |
| Esc | Close menu |

---

## God Mode - Kingdom Commands (K)

Active after pressing K in god mode (requires kingdom selected in dashboard).

| Key | Action |
|-----|--------|
| 1 | Declare war (opens target selection) |
| 2 | Declare peace |
| 3 | Recruit army |
| 4 | Fortify settlements |
| 5 | Boost economy |
| 6 | Change government (opens gov selection) |
| Esc | Close menu |

---

## God Mode - Spawn Menu (Shift+N)

| Key | Action |
|-----|--------|
| 1 | Spawn creature |
| 2 | Spawn NPC |
| 3 | Build (use terrain painter) |
| 4 | Create settlement (use console) |
| Esc | Close menu |

---

## God Dashboard (When Open)

| Key | Action |
|-----|--------|
| Tab / Esc | Close dashboard |
| Up/Down | Scroll content |
| Page Up/Down | Fast scroll |

---

## LLM Console (Backtick)

| Key | Action |
|-----|--------|
| ` (Backtick) | Close console |
| Esc | Close console |
| Enter | Send message |
| Up/Down | Scroll history |
| Backspace | Delete character |
| Left/Right | Move cursor |
| Home/End | Jump to start/end |
| Ctrl+V | Paste |

---

## Python Console (God Mode - Backtick)

| Key | Action |
|-----|--------|
| ` (Backtick) | Close console |
| Enter | Execute command |
| Up/Down | Command history |
| Backspace | Delete character |
| Delete | Delete forward |
| Left/Right | Move cursor |
| Home/End | Jump to start/end |
| Ctrl+L | Clear output |
| Page Up/Down | Scroll output |

---

## Claude Chat (God Mode - F10)

| Key | Action |
|-----|--------|
| Esc | Close chat |
| K | Toggle keyboard shortcut (when empty input) |
| Enter | Send message |
| Backspace | Delete character |
| Ctrl+L / Cmd+L | Clear chat |
| Page Up/Down | Scroll messages |

---

## God Tweaker (God Mode - F6)

| Key | Action |
|-----|--------|
| Tab | Close tweaker |
| Up/Down | Navigate parameters |
| Left/Right | Adjust selected parameter |

---

## God Live Console

| Key | Action |
|-----|--------|
| Enter / Esc | Close results |
| Backspace | Delete character |
| K | Toggle console (when empty input) |
| N | Toggle console |

---

## Startup Menu

| Key | Action |
|-----|--------|
| Up/Down | Navigate options |
| Enter / Space | Select option |
| Esc | Quit |

---

## Character Creation

| Key | Action |
|-----|--------|
| Up/Down | Navigate options |
| Left/Right | Adjust values |
| Tab | Next section |
| Enter / Space | Confirm selection |
| R | Re-roll stats |
| Esc | Back / cancel |

---

## Tutorial Island

Tutorial checks for specific keys to advance:

| Key | Action |
|-----|--------|
| I | Open inventory (tutorial step) |
| Space | Attack (tutorial step) |
| E | Interact (tutorial step) |
| F | Open map (tutorial step) |
| U | Open crafting (tutorial step) |
| F7 | Skip current tutorial step |

---

## Relationship Panel (Shift+R)

| Key | Action |
|-----|--------|
| W / Up | Scroll up |
| S / Down | Scroll down |
| Esc / Shift+R | Close panel |

---

## Notes on Key Priority

The key handling follows this priority order (highest first):

1. **Claude Chat** (when visible) - consumes all keys
2. **LLM Console** (when visible) - consumes all keys
3. **Python Console** (god mode, when visible) - consumes all keys
4. **Backtick** - toggles console
5. **F10 / Shift+K** - god mode Claude chat / API config
6. **Text Input** (dialog free-text) - consumes all keys
7. **F12** - screenshot (always available)
8. **_handle_keydown** dispatches to:
   - Active modal panels (board menu, quest board, dialog, etc.)
   - Panel-specific handlers (inventory, character, quest log, etc.)
   - Controls overlay (? key)
   - 3D camera controls
   - Divine commands (god mode)
   - God UI panel + spell bar
   - Highlight system (J/K)
   - Shift+R (relationship panel)
   - Action map (all remaining game keys)

---

## Conflict Resolution Notes

- **S key**: Changed spell list toggle from `S` to `Shift+S` to avoid
  conflicting with movement (S = move down).
- **D key**: Movement right is disabled in god mode (D = Disguise).
  Use Right Arrow for movement in god mode.
- **G key**: In god mode, G = divine events. In mortal mode, G = drop item.
- **P key**: In god mode, P = pause time. In mortal mode, P = auto-play.
- **F1-F5**: In god mode with panel, they switch tabs. In mortal mode,
  they trigger combat abilities.
- **F5/Home**: In god mode, toggles divine realm. In mortal mode, F5 = Scout.
- **F6**: In god mode, toggles parameter tweaker. In mortal mode, cycles overlay.
- **F7**: In god mode, hot reloads modules. In mortal mode, skips tutorial.
- **[ ] . keys**: In god mode, control time speed. Overrides spell bar hotbar paging
  for god-mode spellcasters (use comma/period variants instead).
- **Tab**: In god mode, opens dashboard. In mortal mode, cycles NPC target.
- **1-5**: In god mode with panel open, switch tools. Otherwise, cast spells.

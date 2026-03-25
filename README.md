# Autonomous World

A living medieval open-world RPG built with Pygame, combining Baldur's Gate-style D&D mechanics with Sims-style social simulation. Every NPC has real jobs, emotions, memories, relationships, and goals. Gods watch from above, souls persist across lifetimes, and the world evolves whether you're watching or not.

## Quick Start

```bash
pip install pygame-ce numpy
python play.py
```

## Controls

| Key | Action |
|-----|--------|
| WASD | Move |
| E | Interact / Talk (NPCs and intelligent monsters) |
| Space | Melee attack (nearest hostile in facing direction) |
| Left-click | Target entity (set as combat target / cast spell at) |
| Right-click | Cancel targeting / deselect target |
| 1-9 | Cast spell (enters targeting mode, click to aim) |
| S | Toggle spell list overlay |
| I | Inventory |
| C | Character sheet |
| Q | Quest log |
| F | World map |
| M | Minimap |
| R | Recruit NPC to party |
| Tab | Cycle nearby NPCs |
| T | Free-text chat (in dialog) |
| H | Historical chronicles |
| V | Toggle view mode (Strategy → Adventure → 3D) |
| F6 | Toggle entity overlays (All → Minimal → Off) |
| F12 | Screenshot |
| Escape | Pause menu / cancel targeting |

## Core Systems

### Living NPCs (574+ per world)
- **48 professions** — Merchant, Baker, Blacksmith, Healer, Farmer, Guard, Innkeeper, Alchemist, plus all D&D classes (Fighter, Wizard, Cleric, Rogue, Ranger, Paladin, Bard, Monk, Warlock, Sorcerer, Druid, Barbarian)
- **Plutchik emotions** — 8 primary emotions (joy, trust, fear, surprise, sadness, disgust, anger, anticipation) with secondary combinations. Emotions affect dialog, work output, and social behavior
- **Big Five personality** — Openness, conscientiousness, extraversion, agreeableness, neuroticism shape NPC decision-making
- **Dynamic relationships** — Trust (-100 to +100) evolves through interactions. NPCs form friendships, rivalries, romantic bonds, and grudges
- **Needs system** — Hunger, thirst, rest, social. NPCs eat, drink, sleep, and seek company autonomously
- **Memory** — NPCs remember conversations, gifts, insults, and events. Past interactions change future dialog

### Deep Conversations
- **Relationship-aware** — Hostile NPCs greet with "What do YOU want?" while friends say "My friend! Always good to see you"
- **Emotion-aware** — Sad NPCs talk about their troubles, angry NPCs are short-tempered, joyful NPCs are generous
- **Body language** — "[They smile warmly]", "[Their jaw tightens]", "[They avoid your gaze]" based on emotional state
- **Memory-driven** — NPCs remember past conversations: "Back for more trading?", "Any progress on that task?"
- **Needs-driven** — Hungry NPCs mention food, lonely NPCs are grateful for company
- **Free-text chat** — Type anything to NPCs; LLM generates contextual responses, or scripted fallback without LLM
- **Gift giving** — Give items to NPCs to improve relationships. Food to hungry NPCs gives extra bonuses
- **Class-specific dialog** — Wizards discuss magic, Bards perform songs, Rogues offer shady deals, Clerics heal

### Trading & Economy
- **Shops** — Merchants, blacksmiths, healers, bakers, innkeepers, alchemists, armourers sell profession-specific goods
- **Barter** — Trade with any NPC who has inventory (503+ NPCs). Items sold at 80% value
- **Buy and sell** — Tab to switch between buying and selling in the shop UI
- **NPC-to-NPC trade** — NPCs buy food when hungry, healing items when hurt, weapons when needed
- **Trade caravans** — Merchants travel between settlements carrying goods

### Quest System
- **8 quest types** — Kill, fetch, deliver, investigate, escort, diplomacy, defend, bounty hunt
- **All completable** — Quest progress tracked through kills, item collection, location visits, NPC interactions, and settlement defense
- **Accept or reject** — Refusing a king's quest angers the court and alerts guards. Refusing a friend hurts their feelings
- **Failure consequences** — Abandoned quests cost gold and reputation. Failed defense quests damage settlement morale. Failed escorts kill the escorted NPC
- **Quest chains** — Multi-part storylines with escalating rewards
- **Player-assigned tasks** — Ask NPCs to hunt creatures, gather supplies, scout areas, guard locations, or deliver items. They work autonomously and report back when done

### NPC Social Life
NPCs have the same rich interactions with each other as with the player:
- **Gossip networks** — Information spreads through NPC conversations
- **Skill teaching** — Experienced NPCs teach skills to friends
- **Emotional support** — Friends comfort each other when sad
- **Danger warnings** — NPCs warn friends about threats
- **Food sharing** — Friends share food with hungry companions
- **16 social interaction types** — Chat, gossip, argue, flirt, comfort, spar, study, pray, trade, challenge, intimidate, betray, and more
- **Marriage and children** — NPCs marry, have children with Darwinian trait inheritance

### Combat (D&D-based)
- **Ability scores** — STR, DEX, CON, INT, WIS, CHA with D&D modifiers
- **102 spells** across 8 schools, spell levels 1-9
- **Body part damage** — 6 body parts, 8 damage types, wound tracking
- **Equipment** — Weapons, armor, potions with durability
- **Tactical combat** — Real-time with target selection and party management
- **Siege warfare** — Lanchester combat model, siege engines (battering ram, catapult, trebuchet, siege tower), multi-army battles
- **16 military unit types** — Infantry, archers, cavalry, siege engineers with rock-paper-scissors matchups
- **5 formations** — Shield wall, wedge, skirmish line, siege formation, defensive circle

### Intelligent Monster Societies
- **Monster governance** — Orcs, goblins, kobolds, gnolls, bandits, undead each have governance models
- **Monster dialog** — Orcs demand tribute, goblins offer trades, bandits toll roads, gnolls threaten
- **Creature approach** — Intelligent monsters will approach and initiate conversation
- **Monster settlements** — Orc strongholds, goblin warrens, kobold mines, undead crypts with populations

### World
- **10,000 x 10,000 tile world** (chunked) with procedural terrain
- **Settlements** — Hamlets, villages, towns, cities, castles with buildings and interiors
- **Climate model** — Pressure systems, temperature gradients, precipitation, seasons
- **Weather effects** — Rain, snow, storms, fog, heat waves affect activities and emotions
- **Day/night cycle** — NPCs follow schedules, darkness affects visibility
- **Ecology** — Wildlife, domesticated animals, natural resources

### Soul & Religion
- **500 tracked souls** — Persist across lifetimes with echo memories
- **Ghost state** — Souls can linger as ghosts before reincarnation
- **7 gods** — Tharion (war), Sylvana (nature), Verithos (knowledge), Morwen (death), Auriel (commerce), Lyria (love), Xaotl (chaos)
- **Prayer system** — Pray to gods for miracles and blessings
- **Heresy** — Faith erosion, religious conversion, cult founding, schism
- **Undead** — 7 types that feed on souls, necromancers, consecrated zones

### Health & Disease
- **13 diseases** — Plague, fever, infections with contagious spread
- **Seasonal illness** — Weather-driven sickness patterns
- **Medicine** — Healers, herbs, potions, treatment mechanics
- **Mental health** — Depression, anxiety, PTSD, mania, paranoia, addiction, grief, burnout

### AI Systems
- **AI Storyteller** — 4 personalities (balanced/aggressive/peaceful/chaotic) manage dramatic tension
- **LLM integration** — Optional Claude/GPT for dynamic NPC dialog
- **God mode** — Floating panel with parameter tweaker, live Python console, hot reload

### Multiplayer
- **TCP networking** — Server/client architecture for 2 players
- **AI co-player** — Claude-driven companion that plays alongside you

## Architecture

```
game/
  main.py              — Game loop orchestrator
  core/
    player.py          — Player entity
    npc.py             — NPC entity (945+ lines)
    dialog_trees.py    — Rich dialog system (1600+ lines)
    items.py           — Item definitions
    creature.py        — Monsters and wildlife
  systems/
    simulation.py      — SimulationManager (52 subsystems)
    quests.py          — Quest generation, tracking, consequences
    emotions.py        — Plutchik emotion system
    social.py          — NPC relationships and social interactions
    social_dynamics.py — Love, contempt, joy spreading, grief
    combat.py          — D&D combat mechanics
    magic.py           — 102 spells, enchanting, alchemy
    climate.py         — Weather and climate model
    health.py          — Disease, infection, medicine
    souls.py           — Soul persistence and reincarnation
    pantheon.py        — God AI and prayer system
    children.py        — Reproduction and inheritance
    ...                — 40+ more subsystem files
  ui/
    renderer.py        — Strategy view (16px) with particles
    renderer_adventure.py — Adventure view (32px, 2.5D)
    renderer_3d.py     — 3D OpenGL view
    character_anim.py  — Procedural NPC body parts and animation
    player_anim.py     — Player rendering (mortal/ghost/god)
    creatures/         — Per-type creature sprite templates (13 templates, 70 types)
    poses.py           — Entity pose system (7 action poses)
    mount_render.py    — Mounted entity rendering
    object_sprites.py  — Siege engines, vehicles, fortifications
    panels.py          — Dialog, shop, inventory, quest UI
    god_mode.py        — Developer tools
  world/
    world.py           — Chunked world generation
    chunk_generator.py — Procedural terrain
    settlements.py     — Settlement planning
  ai/
    llm.py             — LLM integration
    prompts.py         — NPC voice and context building
```

## God Mode

Start in god mode for development/testing:
- Invulnerable with fast movement
- Live Python console (~) for executing code against game state
- Parameter tweaker for adjusting settings in real-time
- Hot reload for modifying game modules without restart

## Visual Test Viewers

The `viewers/` directory contains standalone test viewers for inspecting all visual elements:

| Viewer | Command | What it shows |
|--------|---------|---------------|
| NPC Characters | `python viewers/test_character_anim.py` | All NPC classes/races in all view scales |
| Creatures (2D) | `python viewers/test_creature_viewer.py` | All 65+ creature types with animation |
| Creatures (3D) | `python viewers/test_creature_3d_viewer.py` | 3D creature templates |
| Player | `python viewers/test_player_viewer.py` | Mortal/ghost/god modes |
| Poses (2D) | `python viewers/test_poses_viewer.py` | All 14 action poses |
| Poses (3D) | `python viewers/test_poses_3d_viewer.py` | 3D poses |
| Creature Poses | `python viewers/test_creature_poses_viewer.py` | Sleeping/resting/combat poses |
| Mounts (2D) | `python viewers/test_mount_viewer.py` | Rider/mount combinations |
| Mounts (3D) | `python viewers/test_mount_3d_viewer.py` | 3D mounted riders |
| Buildings (2.5D) | `python viewers/test_building_25d_viewer.py` | All 63 blueprints with roofs |
| Buildings (3D) | `python viewers/test_building_3d_viewer.py` | OpenGL building viewer |
| Terrain | `python viewers/test_terrain_viewer.py` | All 70 terrain types |
| World Objects | `python viewers/test_objects_viewer.py` | Siege engines, vehicles, walls |
| World Objects (3D) | `python viewers/test_objects_3d_viewer.py` | 3D siege engines and vehicles |

## Screenshots

Press F12 in-game, or use the headless screenshot system:

```python
from game.ui.screenshot import HeadlessGame
hg = HeadlessGame(seed=42)
hg.capture("gameplay")
hg.capture("world_map", zoom=2.0)
hg.capture("character_sheet")
```

## License

Personal project. Not yet licensed for distribution.

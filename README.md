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
| E | Interact / Talk |
| Space | Attack |
| I | Inventory |
| C | Character sheet |
| Q | Quest log |
| F | World map |
| M | Minimap |
| R | Recruit NPC to party |
| Tab | Cycle nearby NPCs |
| T | Free-text chat (in dialog) |
| H | Historical chronicles |
| V | Planet view |
| ~ | Python console (god mode) |
| F12 | Screenshot |
| Escape | Pause menu |

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
- **Siege warfare** — Lanchester combat model, siege engines, multi-army battles

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
    renderer.py        — Tile-based rendering with particles
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

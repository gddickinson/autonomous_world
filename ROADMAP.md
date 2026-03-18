# Autonomous World — Development Roadmap

## Project Status (March 2026)

**Codebase:** 177 Python files, ~210,000 lines of code
**Engine:** Pygame-CE with headless testing, video recording, screenshot system
**World:** 10,000 x 10,000 chunked tile map (numpy int8, LRU cache)
**NPCs:** 574+ with 48 professions, needs, emotions, memories, relationships, souls
**Creatures:** 44 types with style-specific AI (pack, ambush, brute, flyer, ranged)
**Settlements:** 233 across 6 kingdoms with professions, economies, governance
**Combat:** Unified D20 system with body damage, formations, terrain, siege engines

### Systems Verified Working (20/20 tests pass)
| System | Status | Details |
|--------|--------|---------|
| World Generation | Working | 10K×10K chunked, history sim, 6 kingdoms, 233 settlements |
| NPC Simulation | Working | Needs, decisions, jobs, social interactions |
| Dialog System | Working | Relationship/emotion/memory-aware, 20+ dialog nodes per NPC |
| Quest System | Working | 8 quest types, all completable, consequences for failure |
| Combat (NPC) | Working | D20 rolls, body damage, flanking, kiting, morale, flee |
| Combat (Creature) | Working | 44 attack styles, special abilities, pack/ambush/brute/flyer |
| Allegiance | Working | Faction/party/species-aware friend-or-foe for all entities |
| Colosseum | Working | Arena battles, terrain, formations, siege, video recording |
| Emotions | Working | Plutchik wheel, 8 primary + 8 secondary emotions |
| Body Damage | Working | 6 body parts, 8 damage types, wounds, bleeding, infection |
| Trade/Economy | Working | Shops, barter, buy/sell, NPC-NPC trade |
| Weather/Climate | Working | Pressure systems, seasons, affects activities |
| Warfare | Working | MilitaryUnits, formations, matchup bonuses, commanders |
| Souls | Working | 276 tracked souls, reincarnation, ghost state |
| Social | Working | 16 interaction types, gossip, teaching, emotional support |
| Professions | Working | 48 civilian + D&D classes, profession-specific shops |
| Player Tasks | Working | Assign NPCs to hunt/gather/scout/guard/deliver |
| Hot Reload | Working | Reload game modules without restart |
| Screenshots | Working | 4 views captured (gameplay, character, inventory, quest) |
| Video Recording | Working | MP4 via ffmpeg, battle recordings with HUD overlay |

---

## Phase 1: Graphics & Animation (HIGHEST PRIORITY)

The gameplay is deep but visuals are colored rectangles. This is the #1 improvement needed.

### 1.1 Procedural Character Animation
- [ ] Body part rendering (head, torso, arms, legs as assembled shapes)
- [ ] Walk cycle (IK-based leg stepping, arm swing, head bob)
- [ ] Combat animations (weapon swing arcs, ranged projectile trails)
- [ ] Idle animations (breathing, head turns, gesture when talking)
- [ ] Death animation (collapse, body parts scatter based on fatal wound)
- [ ] Equipment visibility (weapon at hand, armor tint, shield on arm)
- [ ] Size variation (tiny goblins, huge ogres, massive dragons)

### 1.2 Combat Visuals
- [ ] Weapon swing arc particles during attacks
- [ ] Arrow/bolt flight paths for ranged (archer NPCs AND creature ranged)
- [ ] Spell bolt visuals (dragon breath cone, lich necro bolt, spider web)
- [ ] Hit particles by damage type (red=slash, grey=blunt, green=poison, blue=frost)
- [ ] Health bars over ALL combatants during battles
- [ ] Formation markers on ground (shield wall line, wedge shape)
- [ ] Morale color indicator (green→yellow→red as morale drops)
- [ ] Fleeing NPCs have panic visual (arms up, faster animation)

### 1.3 World Visuals
- [ ] Building construction scaffolding animation
- [ ] Water animation (flowing rivers, ripple effects)
- [ ] Fire/torch dynamic lighting
- [ ] Terrain edge blending between biomes

---

## Phase 2: Sound & Audio

Currently completely silent. Adding audio would transform immersion.

### 2.1 Sound Effects
- [ ] Combat sounds (sword clash, arrow thud, spell impact, creature roar)
- [ ] Footstep sounds (stone, grass, wood, sand)
- [ ] Ambient soundscapes (forest birds, village bustle, wind, rain)
- [ ] UI sounds (menu click, quest complete chime, notification)
- [ ] NPC voice barks (greeting, pain, death, combat cry)

### 2.2 Music
- [ ] Dynamic music layers (peaceful → tension → combat)
- [ ] Biome themes (forest, mountain, desert, ocean)
- [ ] Settlement music (tavern jig, temple chant)

---

## Phase 3: Combat & Warfare Depth

### 3.1 Individual Combat
- [ ] Ranged projectile physics (flight time, can miss moving targets)
- [ ] Shield blocking (active defense with durability cost)
- [ ] Dodge/roll for light armor
- [ ] Surrender mechanic (enemies yield, take prisoner)
- [ ] Mounted combat (lance charge, mounted archery)
- [ ] Environmental hazards (push into fire, off ledge)

### 3.2 Large-Scale Warfare
- [ ] Siege gameplay (player directs operations, deploys engines, breaches walls)
- [ ] Supply line mechanics (armies need food, can be cut off)
- [ ] War diplomacy (declarations, peace treaties, casus belli)
- [ ] Mercenary companies (hire/dismiss armed groups)
- [ ] Fortification building during gameplay

### 3.3 Colosseum Expansion
- [ ] Betting system (NPCs and player bet on fighters)
- [ ] Tournament brackets with elimination rounds
- [ ] Crowd reactions (cheering/booing particles)
- [ ] Champion rankings and titles
- [ ] Player enters as combatant
- [ ] 2-player colosseum (PvP or co-op vs monsters)

---

## Phase 4: Quest & Narrative

### 4.1 Quest Improvements
- [ ] Multi-stage quests with branching outcomes
- [ ] Tavern quest boards (community bounties)
- [ ] Investigation quests (gather clues, interview NPCs, deduce)
- [ ] Timed delivery quests
- [ ] Reputation-gated quests
- [ ] Quest rewards: land grants, titles, unique artifacts

### 4.2 Emergent Stories
- [ ] NPC personal storylines (help them over multiple conversations)
- [ ] Dynamic events (coups, elopements, artifact discoveries)
- [ ] Faction questlines (rise through kingdom ranks)
- [ ] Main questline tied to world history

### 4.3 Conversation Depth
- [ ] Persuasion/intimidation/deception skill checks
- [ ] Group conversations (multiple NPCs at once)
- [ ] Overhear NPC-NPC conversations
- [ ] Letter/message system between NPCs and player

---

## Phase 5: World & Exploration

### 5.1 Biome Variety
- [ ] Distinct biome regions (desert, tundra, tropical, volcanic)
- [ ] Biome-specific creatures, resources, building styles
- [ ] Underground cavern/dungeon biome
- [ ] Ocean with islands

### 5.2 Dungeons
- [ ] Procedural multi-level dungeons
- [ ] Scaled loot tables
- [ ] Boss monsters at depths
- [ ] Puzzle rooms (levers, keys, pressure plates)
- [ ] Treasure maps

### 5.3 Travel
- [ ] Rideable mounts
- [ ] Boats for river/coast
- [ ] Fast travel via roads (with travel time)
- [ ] Player-built roads

---

## Phase 6: Player Experience

### 6.1 Tutorial & Onboarding
- [ ] Interactive tutorial on test island
- [ ] Contextual help tooltips
- [ ] Controls overlay (? key)
- [ ] Difficulty settings

### 6.2 UI Improvements
- [ ] Quest tracker HUD with compass
- [ ] Crafting UI with recipe browser
- [ ] Relationship overview panel
- [ ] Settlement overview (population, economy, morale at glance)
- [ ] Combat log (scrollable, filterable)

### 6.3 Player Progression
- [ ] Skill tree with specialization
- [ ] House/property ownership
- [ ] Pet/companion taming
- [ ] Crafting mastery
- [ ] Reputation titles

---

## Phase 7: Multiplayer & Distribution

### 7.1 Multiplayer
- [ ] Shared world (see other player)
- [ ] Co-op quests
- [ ] PvP colosseum
- [ ] Player-to-player trade

### 7.2 Distribution
- [ ] Standalone build (PyInstaller)
- [ ] Cross-platform testing
- [ ] Steam/Itch.io page

---

## Technical Debt

### Code Quality
- [x] Split simulation.py (3,967 → 1,057 + 9 modules)
- [x] Split dialog_trees.py (1,715 → 912 + helpers)
- [x] Split main.py with mixins (dialog results, multiplayer, render)
- [ ] Split renderer.py (4,661 lines)
- [ ] Split magic.py (2,351 lines)
- [ ] Add unit tests for core systems
- [ ] Type hints on public APIs

### Performance
- [x] O(n²) → spatial grid (social, combat)
- [x] sqrt → squared distance
- [ ] Chunk preloading
- [ ] Render batching
- [ ] Entity distance culling

---

## Top 5 Improvements That Would Most Impact the Game

1. **Character animation** — Even simple stick-figure animation would transform combat from "rectangles bumping" to "watching a fight"
2. **Sound effects** — Combat is silent. Hit sounds + ambient audio = immersion
3. **Tutorial quest** — New players are lost. 10-minute guided intro on test island
4. **Ranged projectile visuals** — Can't see arrows/spells being fired
5. **Settlement overview UI** — Can't easily see settlement state at a glance

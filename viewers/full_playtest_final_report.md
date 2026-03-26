# Full Playtest Report -- Autonomous World

**Date:** 2026-03-23
**Tester:** Claude (automated headless playtest)
**Script:** `viewers/full_playtest.py`
**Screenshots:** `viewers/full_playtest_output/` (27 screenshots)

---

## Session Results Summary

### Session 1: The Fighter Explorer (Seed 42, Mortal Mode)

**What happened:**
- Player spawned at Temple of Awakening (1000, 1000) as Human Fighter, Level 1
- HP 100/100, Gold 20, equipped with Wooden Sword
- Nearest settlement "Hearthstone" (village) was only 25 tiles away -- very close
- Two named NPCs visible at spawn: "Vera" and "Magnus"
- Walking toward Hearthstone revealed multiple creatures (chickens, guard NPC)
- Session crashed when trying to sort creatures (Creature class has no `__lt__` -- minor bug)
- No starting quest ("Find Civilization") was assigned -- quest log shows 0/5

**Visual observations:**
- Spawn area looks great: Temple of Awakening has a clear circular footprint with walls, doors, windows, and a grey floor interior
- FOV circle renders correctly in mortal mode -- dark beyond vision radius
- Settlement labels ("Brighthollow", "Hearthstone") render cleanly in white/yellow text
- NPC names and action labels visible (e.g., "*guard*")
- HUD bottom-left shows HP bar (red), Energy bar (blue), Level 1, Gold 20
- Top bar shows Day 1 (Spring), 07:11 with keyboard hints
- Farmland tiles (tan/brown patches) visible around settlements
- Creatures visible as small colored sprites near the settlement

**Character sheet panel:** Excellent. Shows ability scores (STR 12, DEX 17, CON 16, INT 11, WIS 11, CHA 15), combat stats (HP 100, AC 13, Attack 11, Prof +2), class abilities (Second Wind, Fighting Style), skills with level bars (Swordsmanship Lv.3, Hunting Lv.2, etc.), kill/quest/distance counters.

**Inventory panel:** Clean and functional. Shows equipped weapon (Wooden Sword 100%), 4 items, category tabs (Weapons, Armor, Consumables, Materials, Quest, Tools/Other), item tooltip with rarity/description/heal value, keyboard shortcuts at bottom.

**Issues found:**
1. `Creature` class lacks `__lt__` -- cannot sort tuples containing creatures
2. No starting quest assigned in mortal mode -- quest log empty
3. XP stayed at 0 after 500 ticks (no passive XP gain, which is expected but means progression requires active combat)

---

### Session 2: The Town Life Observer (Seed 42)

**What happened:**
- Observed Copperdale (town) at (907, 770)
- Before advancing: 13 NPCs nearby, all with action `''` (empty -- not yet initialized)
- After 2000 ticks: NPC actions diversified dramatically: fishing (1), carrying (2), going_to_storage (3), commuting (2), carrying_food (1), guarding (1), farming (2), trading (1)
- 10 out of 13 NPCs physically moved during the simulation
- Player took 3 HP of damage from something (HP 100 -> 97), suggesting a creature attack
- Tavern name banner "The Rooster's Crow (Oaks-Copp)" appeared at top of screen

**Kingdom economy results (2000 ticks):**
- 21 kingdoms tracked (5 feudal castles, 6 tribal orc camps, 4 tyrannical undead crypts, 4 autocratic kobold mines, 1 anarchist bandit camp)
- Treasury changes were realistic: most feudal kingdoms lost small amounts (army upkeep), smaller factions gained slightly
- Dragon's Gate recruited +1 soldier (5->6), Ironthrone +2 (5->7)
- Several minor factions started recruiting: Warbringer's Seat (0->1), Fleshripper Caves (0->2)
- All morale stayed at 50 (no events dramatic enough to shift it)

**Visual observations:**
- Town buildings visible with distinct roofs (brown), walls (grey), doors (small yellow squares)
- Cobblestone roads (light grey tiles, terrain ID 65) visible running through town
- Farmland patches (terrain ID 11) surround the settlement
- NPC sprites visible with name labels
- FOV circle constrains view nicely in mortal mode
- Before/after screenshots show NPC positions changed -- simulation is alive

**Issues found:**
1. Initial NPC actions are all empty string `''` -- they need a tick or two to initialize
2. Time only advanced to 09:51 after 2000 ticks at 30fps -- less than 3 in-game hours
3. Season stayed at spring (Day 1) -- would need far more ticks for seasonal change
4. No trade caravans spawned during the observation period

---

### Session 3: The Dungeon Delver (Seed 42)

**What happened:**
- Found "Buried Sanctum" (ruins) at (669, 96)
- No STAIRS_DOWN tiles found in the overworld within 500-tile search radius
- Dungeon generation works: created 60x60 dungeon with 15 rooms, 24 monsters, 3 loot chests
- Monster types: ghouls (HP 35, DMG 12), zombies (HP 25, DMG 6), skeletons (HP 20, DMG 8)
- Loot includes gold, health potions, and an enchanted_sword
- Creatures actually spawn near ruins: kobold, zombie, ghoul, viper, hawk within 30 tiles

**Visual observations:**
- Ruins area renders on sandy/desert terrain with some scattered sand tiles
- The Buried Sanctum structure is small -- floor tiles with walls and doors
- Surrounding terrain is realistic desert/coastal biome (sand, some grass, water nearby)
- Creatures not very visible at this zoom level (small colored dots)

**Issues found:**
1. DungeonRoom has no `.x` attribute -- it uses a different field name (likely `.rect` or similar)
2. Dungeon interiors are generated but there is no way to enter them from the overworld (no STAIRS_DOWN placed)
3. The dungeon system is data-only right now -- no visual rendering of dungeon interiors during gameplay

---

### Session 4: The Night Explorer (Seed 42)

**What happened:**
- Day/night cycle tested at 8 time points
- Darkness values: dawn (0.20) = 1.0 (dark), morning (0.30) = 0.0, midday-evening all = 0.0, night (0.80) = 1.0
- The transition from light to dark is binary -- jumps straight from 0.0 to 1.0
- No gradual dawn/dusk transition visible

**Visual observations:**
- **Midday (12:00):** Full bright, all terrain colors vivid. Greens, browns, greys all clearly distinct. Settlement structures sharp.
- **Dawn (04:48):** Dark overlay applied. Buildings and terrain visible but heavily dimmed with a blue-black tint. NPC names still readable.
- **Night (19:12):** Same as dawn -- full dark overlay. No difference between dawn and night visually.
- **Dusk (16:47):** Looks identical to midday -- no amber/orange tint, no gradual transition
- **Water rendering:** Beautiful! Deep water is rich blue, shallow water is lighter blue-grey. Sand beaches visible along shore. Multiple water shades create natural-looking coastline. The lake/pond near spawn has smooth terrain transitions.
- **Water at night:** Night overlay dims the water nicely but no wave animation visible in static screenshot.

**Issues found:**
1. Day/night transition is binary (0.0 or 1.0) with no gradual ramp -- the astronomy system calculates continuous values but the darkness property jumps
2. Dawn and night look identical (same darkness overlay) -- no orange dawn tint, no amber dusk
3. Dusk/evening (0.70-0.75) shows 0.0 darkness -- it should be transitioning
4. The astronomy system's dawn/dusk window is very narrow -- the darkness property snaps at exactly the boundary values

---

### Session 5: Kingdom Watcher (Seed 42, 5000 ticks)

**What happened:**
- 21 kingdoms tracked across 5000 ticks (~2.8 in-game hours)
- NPCs: 657 alive -> 550 alive (**107 NPCs became inactive/dormant**, 36 confirmed dead)
- Creatures: 6769 -> 5258 (1511 creatures removed, likely from combat or despawn)
- Dead NPC causes all listed as "unknown"
- Kingdom diversity: feudalism, tribal, tyranny, autocracy, anarchy styles

**Kingdom economy changes (5000 ticks):**
- Feudal kingdoms lost treasury (army upkeep): Northwatch 241->198, Ironthrone 287->240
- Sunspear Castle grew its army (5->7) while spending treasury
- Several minor factions gained army: Bonecleaver (0->1), Thunderfang (0->2), Gemclaw (0->2)
- One faction (Fleshripper Caves) had NO CHANGE at all
- No war declarations, no settlements changing hands
- No trade caravans completed (0 completed trades)
- No construction projects completed

**NPC activity distribution after 5000 ticks:**
- 372 NPCs idle/empty action (67% of living NPCs)
- 37 guarding, 31 going_to_storage, 29 commuting
- 14 cleaning, 8 carrying_food, 8 carrying, 7 farming
- Various specialist jobs: innkeeping, fishing, tanning, masonry, performing, hunting, healing
- 1 NPC crafting_pottery, 1 road_building, 1 negotiating -- rare activities do occur

**Issues found:**
1. 67% of NPCs have empty action -- too many idle NPCs
2. Death cause always "unknown" -- no tracking of what killed NPCs
3. No trade caravans spawned in ~3 in-game hours
4. No construction completed
5. No war/diplomacy events despite having 21 kingdoms with armies
6. Treasury values are floating-point with many decimals (display should round)

---

## Comprehensive Analysis

### What Works Well

1. **World generation is excellent.** Terrain diversity with grass, forest, sand, water, mountains, roads, farmland. Settlements have proper buildings with walls, doors, windows, floors. Different biome transitions look natural.

2. **Settlement architecture is impressive.** Buildings have distinct roofs, walls, doors, windows. Roads connect settlements. Farmland surrounds villages. Taverns have names like "The Rooster's Crow."

3. **Character system is deep.** D&D-style ability scores, class abilities (Second Wind, Fighting Style), skill system with 6+ skills at varying levels, proficiency bonus, armor class calculation, spellcaster detection. All renders cleanly on the character sheet.

4. **Inventory system is polished.** Category tabs, equipped weapon display with durability percentage, item tooltips with rarity color coding, heal/damage values, keyboard shortcut bar at bottom.

5. **NPC simulation is alive.** NPCs have diverse activities (farming, fishing, guarding, carrying, trading, innkeeping, tanning, masonry, performing). They physically move around settlements. The work system assigns meaningful jobs.

6. **Kingdom/governance system has depth.** 21 kingdoms with different governance styles (feudalism, tribal, tyranny, autocracy, anarchy). Treasuries fluctuate with income and expenses. Armies grow through recruitment. Each kingdom has ruler, settlements, laws, morale.

7. **Creature ecology works.** Appropriate creatures spawn near settlements and in the wild. Ruins have undead (zombies, ghouls, kobolds). Combat stats are balanced with D&D-style values.

8. **Dungeon generation is functional.** BSP-based layouts with typed rooms (treasure, monster lair, library, boss), appropriate monster spawns, and loot tables including named items like "enchanted_sword."

9. **Water rendering looks good.** Multiple water shades (deep blue, shallow light blue), natural shoreline transitions, sand beaches. The lake near spawn is visually appealing.

10. **FOV system works correctly.** Mortal mode shows a circular vision area with darkness beyond. Explored areas remain on the map. The effect creates a genuine sense of exploration.

### What's Still Broken or Missing

1. **Day/night transition is binary.** Jumps from full-bright (0.0) to full-dark (1.0) with no gradient. The astronomy system has the data for gradual transitions, but the darkness property snaps at boundaries. No dawn orange, no dusk amber.

2. **No starting quest.** The "Find Civilization" quest that should guide new players to the nearest settlement is not assigned at game start. The quest log starts empty.

3. **67% of NPCs are idle.** After 5000 ticks, most NPCs still have empty action strings. The work system assigns activities to only ~33% of the population.

4. **Trade caravans don't spawn.** Zero completed trades after 5000 ticks. The trade system exists but doesn't activate in this timeframe.

5. **No war/diplomacy events.** Despite 21 kingdoms, some with armies, no wars were declared and no settlements changed hands. The governance events need more aggressive triggers.

6. **Dungeon interiors unreachable.** The dungeon generation system creates layouts with rooms, monsters, and loot, but no STAIRS_DOWN tiles are placed in the overworld. Players cannot actually enter dungeons.

7. **Death cause tracking missing.** Dead NPCs all show "cause=unknown." The death system doesn't record what killed them.

8. **Creature class lacks comparison operator.** `Creature.__lt__` is not defined, causing crashes when sorting lists containing creatures.

9. **DungeonRoom attribute mismatch.** The `DungeonRoom` class doesn't have an `.x` attribute -- the report code expected a different interface.

10. **Treasury displays floating-point noise.** Values like `175.6830000000082` should be rounded for display.

### Visual Quality Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Terrain rendering | 8/10 | Diverse biomes, natural transitions, good color palette |
| Settlement rendering | 8/10 | Buildings with distinct features, roads, farmland |
| NPC rendering | 7/10 | Named sprites with action labels; small at strategy zoom |
| Water rendering | 8/10 | Multiple shades, natural shorelines, looks like real water |
| Day/night cycle | 3/10 | Binary dark/light, no gradual transitions, no color tints |
| UI panels | 9/10 | Character sheet, inventory, quest log all polished |
| HUD | 8/10 | HP/Energy bars, level, gold, time, keyboard hints |
| FOV/exploration | 8/10 | Smooth circular vision, explored tile persistence |
| Creature visibility | 5/10 | Small colored dots, hard to identify at strategy zoom |
| Overall atmosphere | 7/10 | Feels like a living world when NPCs are active |

### Gameplay Feel Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| First minutes experience | 6/10 | No quest guidance, but spawn area is interesting |
| Exploration motivation | 7/10 | FOV + nearby settlements create curiosity |
| Combat readiness | 5/10 | Creatures nearby but no combat tutorial/feedback visible |
| NPC interaction | 7/10 | Dialog system exists, NPCs have professions/classes |
| Progression sense | 4/10 | No XP gain from ticks alone, no quests assigned |
| World aliveness | 7/10 | NPCs farm, guard, trade; kingdoms have economies |
| Dungeon accessibility | 2/10 | Dungeons exist in data but cannot be entered |
| Long-term engagement | 5/10 | Economy/kingdom simulation runs but lacks visible drama |

### Top 10 Remaining Improvements

1. **Fix day/night gradient.** Add gradual dawn (orange tint) and dusk (amber tint) transitions instead of binary dark/light. The astronomy system already has sunrise/sunset times -- use them for a smooth ramp.

2. **Add starting quest.** Auto-assign a "Find Civilization" or "Explore the Area" quest when creating a new mortal character. Guide the player toward the nearest settlement.

3. **Place dungeon entrances.** Add STAIRS_DOWN tiles at ruins and special locations so players can actually enter generated dungeons. Wire up the transition to render dungeon interiors.

4. **Reduce idle NPC percentage.** Assign default activities to NPCs who have no work. Consider "socializing", "wandering", "resting", "shopping", or "worshipping" as fallback activities rather than empty string.

5. **Trigger kingdom events more frequently.** Lower the thresholds for war declarations, trade agreements, and diplomatic events. After 5000 ticks of a feudal simulation, SOMETHING political should happen.

6. **Activate trade caravans.** Ensure the trade system spawns caravans between settlements within the first in-game day. Trade is a key part of the economy but never fires.

7. **Add death cause tracking.** Record what killed each NPC (combat, starvation, old age, disease) and display it in the chronicle/death screen.

8. **Fix Creature comparison operator.** Add `__lt__` to the Creature class (or use key functions for sorting) to prevent crashes.

9. **Add dawn/dusk color tints.** Overlay an orange/amber tint during dawn and dusk transitions. The current system goes from bright to dark with no color shift.

10. **Improve creature visibility.** At strategy zoom, creatures are tiny colored dots. Add creature name letters (first letter of kind) or small icons to make them identifiable without zooming in.

### Updated Overall Ratings

| Category | Previous (mortal_playtest) | Current | Trend |
|----------|---------------------------|---------|-------|
| Visual Quality | 7/10 | 7.5/10 | Improved: water rendering, settlement detail |
| Gameplay Systems | 6/10 | 7/10 | Improved: NPC work, kingdom economy |
| World Simulation | 6/10 | 6.5/10 | Slight improvement: economy flows, but idle NPCs |
| Combat | 5/10 | 5/10 | No change: untested due to sort bug |
| UI/UX | 8/10 | 8.5/10 | Improved: inventory tabs, character sheet |
| Dungeon System | 3/10 | 3/10 | No change: still data-only, no entry points |
| Day/Night Cycle | 4/10 | 3/10 | Regressed: binary transitions visible |
| New Player Experience | 4/10 | 4/10 | No change: still no starting quest |
| **Overall** | **5.5/10** | **6/10** | **Modest improvement** |

---

## Files Referenced

- Script: `/Users/george/claude_test/autonomous_world/viewers/full_playtest.py`
- Screenshots: `/Users/george/claude_test/autonomous_world/viewers/full_playtest_output/`
- Log: `/Users/george/claude_test/autonomous_world/viewers/full_playtest_output/playtest_log.txt`

## Screenshot Manifest (27 total)

| Screenshot | Description |
|------------|-------------|
| S1_01_spawn_point | Player at Temple of Awakening, FOV visible |
| S1_02_character_sheet | Full D&D character sheet panel |
| S1_03_inventory | Inventory with equipped Wooden Sword |
| S1_04_quest_log | Empty quest log (0/5) |
| S1_05_walking_to_settlement | Between Temple and Hearthstone, creatures/NPCs visible |
| S1_06_at_settlement | Inside Hearthstone village, buildings and NPCs |
| S2_01_town_before | Copperdale town before simulation |
| S2_02_town_after_2000_ticks | Same view after 2000 ticks, NPC positions changed |
| S2_03_world_map_after | World map view of region |
| S3_01_ruins_exterior | Buried Sanctum ruins on desert terrain |
| S3_03_world_overview | Zoomed-out world map |
| S4_dawn | Dawn (04:48) -- full darkness overlay |
| S4_morning | Morning (07:12) -- full bright |
| S4_midday | Midday (12:00) -- full bright |
| S4_afternoon | Afternoon (14:24) -- full bright |
| S4_dusk | Dusk (16:48) -- still full bright (bug) |
| S4_evening | Evening (18:00) -- still full bright (bug) |
| S4_night | Night (19:12) -- full darkness |
| S4_midnight | Midnight (22:48) -- full darkness |
| S4_water_midday | Lake at midday -- beautiful blue water |
| S4_water_night | Same lake at night -- dimmed with overlay |
| S4_shallow_water | Shallow water area with sand beaches |
| S5_01_initial_state | Spawn area at start of session 5 |
| S5_02_world_map_initial | World map before simulation |
| S5_03_after_5000_ticks | Same area after 5000 ticks |
| S5_04_world_map_after | World map after simulation |
| S5_05_character_sheet | Character sheet after simulation |

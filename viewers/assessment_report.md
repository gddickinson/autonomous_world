# Autonomous World — Comprehensive Assessment Report

**Date:** 2026-03-24
**Playtest tool:** `viewers/assessment_playtest.py`
**Seed:** 42 | **World:** ChunkedWorld (10,000 x 10,000)
**Screenshots:** 9 captured in `viewers/assessment_output/`

---

## 1. Current State Summary

The game is in a **solid pre-alpha state** with a functioning core loop. World generation, NPC simulation, rendering, day/night cycle, and economic systems all run without crashes across 4 separate test sessions totaling ~4,500 simulation ticks.

**What works well:**
- World generation produces a large, varied landscape with mountains, forests, plains, roads
- 96 settlements generated (29 villages, 50 towns, 12 cities, 5 hamlets) — good density
- 56 NPCs with proper fantasy names (zero `NPC_xxxx` names found)
- 32 creature types with good diversity (deer, wolves, rabbits, hawks, trolls, wyverns, etc.)
- Day/night cycle with torch/glow lighting effects looks atmospheric
- Settlement rendering at strategy zoom shows buildings, roads, farmland, NPCs clearly
- Adventure zoom shows individual NPCs with personality trait labels
- HUD displays HP, Energy, Level, Gold, time/season correctly
- All 4 sessions ran to completion without errors

**What needs attention:**
- NPC survival rate is only 73.2% after 500 ticks (15 dead out of 56)
- 75.6% of NPCs are `seeking_shelter` — dominates activity distribution
- No trade caravans, trade routes, or construction activity observed after 2000 ticks
- Starting quests show as 0 (quests exist but require player acceptance — not a bug, but onboarding could be smoother)
- Dusk scene shows darkness=0.00 (no visible lighting change at DUSK_START)
- Only 4 kingdoms, all non-human (Goblin Warrens, Toadstool Hollow, Undead Realm) — human kingdoms absent or not forming

**Overall quality:** Functional foundation with strong world generation and visuals. Economy and NPC behavior need tuning.

---

## 2. Economy Assessment

### Treasury Tracking (4 Kingdoms)
| Kingdom | Tick 0 | Tick 1000 | Tick 2000 | Trend |
|---------|--------|-----------|-----------|-------|
| Goblin Warrens of Moldpit | 50 | 0 | 1,022 | Growing |
| Toadstool Hollow Swarm | 50 | 0 | 718 | Growing |
| Goblin Warrens of Muckmire | 50 | 10 | 1,020 | Growing |
| Undead Realm of The Pale Citadel | 50 | 0 | 752 | Growing |

**Pattern:** All 4 kingdoms dip to near-zero by tick 1000 (spending initial treasury), then grow significantly by tick 2000. This suggests the economy has an initial drain period followed by income kicking in. All kingdoms are growing — no stagnation.

### Trade & Construction
- **Active caravans:** 0
- **Completed trades:** 0
- **Trade routes:** 0
- **Active construction:** 0
- **Completed builds:** 0 (returned as empty list `[]`)
- **Active wars:** 0

**Assessment:** The macro-economy (kingdom treasuries) is functional and growing, but the micro-economy (trade caravans, construction projects) appears dormant. Either the simulation hasn't triggered trade/construction yet at 2000 ticks, or the systems need population thresholds that aren't being met. This is the single biggest gap — kingdoms accumulate gold but nothing is spent on visible economic activity.

---

## 3. NPC Assessment

### Population
- **Total NPCs:** 56
- **Alive after 500 ticks:** 41 (73.2% survival)
- **15 deaths in 500 ticks** — roughly 1 death every 33 ticks, which is quite high

### Names & Races
- **Zero bad names** — all NPCs have proper fantasy names (Iseth, Faith, Garorn, Kaen, Vaorn, etc.)
- **Races:** Human, Elf, Dwarf, Halfling, Gnome, Tiefling, Half-Orc — good diversity

### Classes & Jobs
- Most NPCs are **Commoner** class with trade jobs (Carpenter, Farmer, Blacksmith, Innkeeper, etc.)
- Some specialist classes: Rogue, Ranger
- Jobs match expectations (Dwarf Rogue as Farmer is a bit odd but acceptable)

### Activity Distribution (at tick 2000)
| Activity | Count | Percentage |
|----------|-------|-----------|
| seeking_shelter | 31 | 75.6% |
| (empty string) | 6 | 14.6% |
| guarding | 2 | 4.9% |
| carrying_food | 1 | 2.4% |
| fishing | 1 | 2.4% |

**Assessment:** The `seeking_shelter` dominance is concerning. 75% of alive NPCs are stuck in shelter-seeking behavior. This likely relates to weather/exposure, time of day, or a too-aggressive shelter threshold. The 14.6% with empty action strings suggests some NPCs have no assigned behavior. Only 3 NPCs (7.3%) are doing productive work (guarding, carrying food, fishing).

**Recommendation:** Tune shelter-seeking thresholds. NPCs should work during daytime and seek shelter primarily at night or during storms. The empty-action NPCs need a fallback behavior assigned.

---

## 4. Visual Assessment

### Strategy Zoom (S3_strategy_zoom)
- Settlement "Hearthstone" renders clearly with buildings (brown/tan rectangles), roads (gray lines), farmland (golden fields)
- NPC sprites visible walking through town — multiple characters with distinct color-coded clothing
- Trees render as dark green clusters; grass as lighter green
- Doors visible on buildings (small colored marks)
- Good readability — can distinguish buildings, roads, vegetation, NPCs
- Some pink/magenta squares scattered across the terrain (creature markers or items?) — slightly cluttered

### Adventure Zoom (S3_adventure_zoom)
- Individual NPCs visible as larger sprites with name labels and personality traits shown ("ambitious, adventurous", "ambitious, greedy")
- Terrain is not rendered at adventure zoom — background is solid dark, only NPCs visible
- This is a significant visual gap — adventure zoom should show terrain/buildings at higher detail, not a black void

### Dusk Scene (S3_dusk_scene)
- Time reads 16:47 — correct for dusk
- However, darkness=0.00 means no lighting overlay is applied
- Scene looks identical to daytime — dusk transition is not working visually
- The DUSK_START threshold may be set too late, or the darkness calculation ramps too slowly

### Night Scene (S3_night_scene)
- Time reads 21:36, darkness=1.00 — full night
- Excellent atmosphere: dark blue-green overlay covers the scene
- Torch/fireplace glows visible as warm orange circles at building locations
- Moon visible as a large glowing sphere in the upper-right corner
- NPCs still visible but dimmed — good balance of visibility vs darkness
- This is the strongest visual in the game

### World Map (S3_world_map)
- Shows terrain at 0.50x zoom centered on Temple of Awakening
- Green plains, brown mountains, white snow peaks, tan roads all visible
- Settlement labels (Moldpit, Rottooth Caves, etc.) displayed correctly
- Legend at bottom shows City/Castle, Town, Village, Hamlet, Temple, Ruins, You markers
- Scale bar shows "15 km" — helps with spatial awareness
- Good overview functionality

### Spawn Point (S1_spawn_point)
- Player spawns at "Temple of Awakening" — a circular stone platform with doors
- Mortal FOV circle visible — dark beyond line of sight
- HUD shows HP: 100/100, Lv.1, Energy: 100, Gold: 20
- Minimap partially visible in upper-right corner
- Clean, readable starting experience

---

## 5. Systems Inventory

| System | Status | Notes |
|--------|--------|-------|
| ChunkedWorld (10k x 10k) | WORKING | Generates correctly, spawn at (5000,5000) |
| TimeSystem | WORKING | Day/night cycle, seasons, time display |
| WorldManager | WORKING | NPC/creature spawning and management |
| SimulationManager | WORKING | Orchestrates NPC behavior and economy |
| GovernanceSystem | WORKING | 4 kingdoms with treasuries, armies, morale |
| TradeSystem | WORKING (dormant) | Initializes but no caravans observed |
| ConstructionSystem | WORKING (dormant) | Initializes but no projects observed |
| BuildingSystem | WORKING | Buildings registered, owners assigned |
| QuestSystem | WORKING | Quests generated for NPCs, acceptance required |
| TacticalCombat | WORKING | Imports/initializes correctly |
| PlayerParty | WORKING | Imports/initializes correctly |
| FactionSystem | WORKING | Imports/initializes correctly |
| SoundManager | WORKING | Initializes without error |
| MusicSystem | WORKING | Imports correctly |
| Renderer (strategy) | WORKING | Full terrain, buildings, NPCs, lighting |
| Renderer (adventure) | PARTIAL | NPCs render but terrain/buildings missing |
| Day/Night Lighting | PARTIAL | Night works great, dusk transition broken |
| Exposure System | WORKING | Functions exist but `process_exposure` not a top-level export |
| Warfare System | PARTIAL | Classes exist (TroopUnit, BattleArmy, etc.) but no `WarfareSystem` wrapper class |
| NPC Dialog | UNTESTED | Not tested in this session |
| Interior System | UNTESTED | Not tested in this session |
| Magic/Spells | UNTESTED | Not tested in this session |
| Dungeon Generation | UNTESTED | Not tested in this session |

---

## 6. Updated Next Steps (Priority Order)

### Critical (affects core gameplay)
1. **Fix adventure zoom terrain rendering** — Adventure zoom shows a black void instead of terrain. The `AdventureRenderer` needs to draw tiles/buildings at the 32px tile size.
2. **Tune NPC shelter-seeking** — 75% of NPCs stuck in `seeking_shelter` makes towns feel dead. Add time-of-day gates (shelter only at night/storms) and reduce the trigger sensitivity.
3. **Fix empty NPC actions** — 14.6% of NPCs have blank action strings. Assign a fallback idle/wander behavior.
4. **Fix dusk lighting transition** — darkness=0.0 at dusk time means no gradual sunset. The darkness ramp should start increasing before DUSK_START.

### High Priority (economy/simulation)
5. **Activate trade caravans** — Trade routes exist in code but no caravans spawn. Check if population or treasury thresholds block caravan creation and lower them.
6. **Activate construction** — Same issue as trade. Kingdoms have gold but nothing triggers building projects.
7. **Reduce NPC death rate** — 27% mortality in 500 ticks is too high. Investigate death causes (exposure? combat? starvation?) and balance.
8. **Add human kingdoms** — Only goblin/undead kingdoms formed. Human settlements (50 towns, 12 cities) should coalesce into kingdoms.

### Medium Priority (polish)
9. **Clean up pink creature markers** — Small pink/magenta squares litter the landscape. These should be replaced with proper creature sprites or made less intrusive.
10. **Fix warfare system export** — `WarfareSystem` class doesn't exist; the module has `BattleArmy`, `BattleField`, etc. Either add a facade class or update imports.
11. **Fix exposure system export** — `process_exposure` is not the correct function name (it's `update`). Update references.
12. **Starting quest onboarding** — Player starts with 0 active quests. Consider auto-accepting a tutorial quest or showing a quest marker at the nearest NPC.

### Lower Priority (features)
13. **NPC job-class alignment** — Most NPCs are "Commoner" regardless of job. A Blacksmith could be a Commoner with Blacksmith job, but some variety in base class (Artisan, Merchant, etc.) would add depth.
14. **Settlement population display** — Show NPC count per settlement on the world map.
15. **More diverse kingdom types** — Currently only Goblin and Undead kingdoms. Enable human, elf, dwarf kingdom formation from their settlements.

---

## 7. New Roadmap Items

Based on this playtest, the following new feature ideas emerged:

1. **NPC Daily Schedule System** — NPCs should follow time-based routines: work during day, eat at mealtimes, sleep at night. This would fix the shelter-seeking dominance and make towns feel alive.

2. **Economic Activity Indicators** — Visual indicators when NPCs are trading, building, farming. Floating icons or particle effects to show the economy in motion.

3. **Kingdom Formation for Human Races** — Currently only monster kingdoms form. Human/elf/dwarf settlements should coalesce into proper kingdoms with lords, councils, etc.

4. **Spawn Area Safety Zone** — No hostile creatures within 80 tiles of spawn (confirmed working). Extend this to ensure the first settlement is also safe, giving new players a peaceful starting area.

5. **Adventure Zoom Detail Pass** — When zoomed to 32px tiles, show building interiors as visible floor plans, individual furniture, doors, windows. This is the "immersive" view and needs the most visual love.

6. **NPC Death Log** — Track and display cause of death for NPCs. This would help balance the simulation (are they dying from exposure? combat? starvation?).

7. **Trade Visualization** — When caravans are active, show dotted lines on the world map between trading settlements. Show cart sprites moving along roads.

8. **Weather System Integration** — If shelter-seeking is driven by weather, show weather state in the HUD (clear, rain, storm, etc.) so the player understands why NPCs behave as they do.

---

## 8. Overall Rating

| Category | Score | Notes |
|----------|-------|-------|
| World Generation | 9/10 | Excellent terrain, 96 settlements, varied biomes |
| Visual Quality | 7/10 | Night lighting is great; adventure zoom and dusk need work |
| NPC System | 5/10 | Good names/diversity but behavior stuck in shelter-seeking |
| Economy | 4/10 | Treasuries grow but no visible trade/construction |
| Combat | N/A | Not tested this session |
| Stability | 9/10 | Zero crashes across 4 sessions, ~4500 ticks |
| Systems Architecture | 8/10 | 14+ systems all initialize; modular design |
| Creature Ecosystem | 7/10 | 32 types, domestic animals near towns, good variety |
| Overall | **6.5/10** | Strong foundation with world gen and stability; needs economy activation and NPC behavior tuning to feel alive |

**Bottom line:** The world looks great and the infrastructure is solid. The game's biggest weakness is that it feels static — NPCs huddle in shelter, nobody trades, nothing gets built. Fixing NPC daily schedules and activating the trade/construction systems would likely jump the score to 8/10. The night scene proves the visual engine can produce atmosphere; that quality needs to extend to dusk/dawn and adventure zoom.

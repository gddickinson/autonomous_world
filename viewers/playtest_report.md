# Autonomous World - Playtest Report

**Date:** 2026-03-23
**Seed:** 42
**World:** 2000x2000 tiles, 372 structures, 644 NPCs, ~4850 creatures

---

## 1. Graphics Quality

### Terrain
- Terrain uses flat-colored tiles at 16px (strategy) and 32px (adventure) scales. The colors are pleasant and readable: green grass, dark green forests, brown mountains, blue water, tan sand, grey stone roads.
- Forests render with a crosshatch/checker pattern overlay in adventure view, giving a textured appearance. Dense forest is visually darker and distinct from regular forest.
- Mountains use a repeated triangle/peak pattern that reads clearly as mountainous terrain at both zoom levels.
- Sand/beach transitions look natural with jagged borders following noise contours.
- Farmland has a tilled-row pattern that's clearly distinguishable from plain grass.

### Buildings
- Buildings are rendered as rectangular floor areas (grey-blue for stone, brown for wood) surrounded by darker wall borders. Doors are visible as colored rectangles on building edges.
- In adventure view (32px), individual furniture items (tables, chests, beds) are visible inside buildings as small colored rectangles.
- Castles and cities have larger, more complex building clusters. The difference between city (stone, blue-grey), town (mixed), and hamlet (wood, brown) buildings is visible.
- Windows appear as small blue-grey marks on walls.

### NPCs and Player
- NPCs are rendered as small humanoid sprites (~16-20px tall) with distinct body colors (purple, green, brown, pink, blue, etc.) representing different clothing/roles.
- NPCs carry visible items: swords/tools as white lines beside their bodies, shields as small shapes.
- The player character is a bright yellow figure with a circular glow/highlight, making them easy to spot.
- NPC name labels appear above characters in white text. Action labels (e.g., `*guard*`, `*walk*`, `*trade*`, `*fish*`) appear in colored text near NPCs.
- Trait text (e.g., "lonely, compassionate, lazy, cheerful") appears below NPC names in grey text when close.

### Creatures
- Creatures are rendered as small animal sprites: deer (brown quadrupeds), hawks/crows (small bird shapes), sheep (white quadrupeds), rabbits (tiny shapes), spiders (dark multi-legged forms).
- Creatures are identifiable by shape but quite small at strategy zoom. Adventure view makes them more readable.

### Overall Visual Assessment
The graphics are functional pixel-art style. They successfully communicate game state (terrain, buildings, NPCs, actions) at a glance. The art style is consistent throughout -- retro/roguelike aesthetic.

**Rating: 6/10** -- Functional and readable but basic. The tile-based rendering is clean but lacks visual richness (no shadows, no ambient occlusion, limited animation visible in screenshots).

---

## 2. Settlement Realism

### Positive
- Settlements have roads connecting buildings, creating natural-looking pathways.
- Cities (Thornwall, Brighthollow) have many buildings packed together with connecting roads -- feels appropriately dense.
- Castles (Northwatch Keep, Stormhold Citadel) have buildings of different sizes organized around a central area.
- NPCs are distributed throughout settlements, not clustered in one spot.
- Labeled structures like "Temple of Awakening" and "Hearthstone" (tavern?) add points of interest.
- Inns/taverns are labeled with names like "The Rooster's Crow" and "The Weary Traveler" with their route connections.
- Named landmarks like "Forgotten Temple" appear on the map.

### Needs Improvement
- Building layouts are mostly rectangular grids. Real medieval towns have organic, irregular layouts.
- No visible market squares, wells, fountains, or other town infrastructure.
- Settlements lack clear defensive walls or gates (even for castles and cities).
- No visible gardens, yards, or courtyards between buildings.
- Hamlet "Fogmere" has only 2 buildings visible -- feels more like a camp than a hamlet.
- Buildings are all axis-aligned rectangles, no L-shapes or irregular floor plans.

**Rating: 5/10** -- Recognizable as settlements with good variety in size, but layouts are too grid-like and lack medieval character.

---

## 3. Terrain Rendering

### Positive
- The world map (full overview) shows a convincing island landmass with natural-looking coastlines, peninsulas, and internal lakes.
- Biomes transition naturally: grass -> forest -> dense forest, grass -> sand -> water.
- Mountains with snow peaks are visible in the northern regions (though snow was not found within search radius of spawn).
- Swamp areas have their own distinct color.
- Rivers and lakes have natural irregular shapes.
- Roads are clearly visible as tan/brown paths connecting settlements.
- The world map overlay shows settlement names, a legend (City/Castle, Town, Village, Hamlet, Temple, Ruins), and a scale bar.

### Needs Improvement
- Water is a flat single color (blue) with no wave effects, shore gradients, or depth variation.
- The adventure-view water screenshot shows the player standing in the ocean with nothing but flat blue tiles in every direction -- there should be shore features or the player shouldn't be able to walk into deep water.
- No visible rivers as continuous waterways (just lakes/ponds).
- Mountain terrain is just a repeating triangle pattern -- could use height variation.
- No visible wildlife in wilderness areas (most creatures were near settlements).

**Rating: 6/10** -- World generation produces natural-looking geography at the macro level. Up close, terrain is quite flat and repetitive.

---

## 4. NPC Behavior

### What NPCs Are Doing
Based on the 200-tick simulation warmup and NPC inspection:
- **Active behaviors observed:** masonry, hunting, fishing, tanning, guarding, commuting, going_to_storage, administering, trading, studying, farming, walking
- **Idle NPCs:** Some NPCs had empty action strings (doing ''), suggesting they were between tasks or idle.
- NPCs are spread across settlements doing a variety of jobs, not all clustered doing the same thing.
- Guards are positioned at settlement edges (visible `*guard*` labels).
- Traders and commuters move between locations.

### Positive
- NPCs show diverse actions. In a single settlement, you can see guards, traders, fishermen, craftspeople.
- Action labels (`*trade*`, `*guard*`, `*fish*`, `*walk*`) give immediate feedback on what NPCs are doing.
- NPCs carry items (visible swords/tools).
- NPC trait display (e.g., "greedy, bookworm") adds personality.

### Needs Improvement
- NPC `job` attribute shows as "unknown" for all inspected NPCs, even though they clearly have actions. The job field might not be populated correctly.
- Some NPCs have empty current_action strings.
- No visible conversations or social interactions in the screenshots (though SHOW_NPC_CONVERSATIONS is enabled).
- NPCs don't visually change their sprite when performing different actions (a guard looks the same as a fisherman except for position).

**Rating: 7/10** -- Good variety of NPC behaviors with clear labeling. The simulation is clearly running and NPCs are doing meaningful activities.

---

## 5. Combat

### Observations
- Only passive creatures were found in the initial search: hawks, crows (all in "wandering" state).
- No active combat scenarios were captured -- all creatures were at full HP and wandering.
- No hostile creatures (wolves, bandits, undead) were encountered near the spawn area.
- The creature count is high (4850+) suggesting a living world, but most visible creatures are passive wildlife.

### Assessment
- Could not assess combat visuals, damage numbers, attack animations, or health bar rendering from these screenshots.
- The game appears to have combat systems (Space:Attack in keybinds, combat stats in character sheet) but peaceful starting conditions make it hard to test.

**Rating: N/A** -- Could not evaluate combat from this playtest. Need to either find hostile creatures or initiate combat manually.

---

## 6. UI/UX

### HUD
- **Bottom-left:** HP bar (red), Energy bar (blue), Level, Gold -- all clearly readable.
- **Top-center:** Day counter, season, and 24h time display -- clean and informative.
- **Top-left:** Control hints (WASD:Move, Shift:Run, etc.) in monospace font on dark background.
- The HUD is minimal and doesn't obstruct gameplay view.

### Character Sheet
- Clean layout with ability scores (STR/DEX/CON/INT/WIS/CHA), combat stats, class abilities, spells, skills with level bars.
- Skills show progress bars for visual feedback.
- All text is readable in monospace font.

### Inventory
- Shows equipped weapon/armor, capacity (4/20), item categories (All/Weapons/Armor/Consumables/Materials/Quest/Tools).
- Selected item shows description tooltip with stats.
- Clean, functional layout.

### Quest Log
- Shows "No active quests" which is expected for a headless god-mode session.
- Clean panel with close instructions.

### Pause Menu
- Comprehensive keybinding reference organized by category (Movement, Combat, Interaction, Menus).
- Very helpful for new players.

### Planet View
- Impressive 3D globe rendering of "Planet Edras" with continents, two moons (Lunara, Thal), and a side panel showing world lore (nations, population, climate).
- Shows year/day/season/daylight hours/moon phases.
- This is a polished feature that adds depth to the world.

### World Map
- Clean overhead view with settlement markers color-coded by type.
- Legend, scale bar, zoom level indicator, and coordinates displayed.
- Zoom levels work well from full-world to local area.

**Rating: 8/10** -- UI is clean, readable, and informative. The planet view is a standout feature. Panels use consistent styling.

---

## 7. Overall Feel

The game presents a living medieval world with impressive scope. Key impressions:

- **World Generation** is strong. The island landmass with varied biomes, coastlines, inland lakes, and distributed settlements feels natural and explorable.
- **The simulation** is clearly active -- NPCs perform diverse activities (guarding, trading, fishing, farming, masonry, studying), creating a sense of a functioning society.
- **Scale** is ambitious: 644 NPCs across 29 settlements (2 cities, 5 castles, 5 towns, 10 villages, 7 hamlets) with nearly 5000 creatures.
- **Dual view modes** (16px strategy / 32px adventure) are a great design choice, letting players zoom between oversight and immersion.
- **Day/night cycle** works well with a convincing darkness overlay at night that creates a radius of visibility around the player.
- **Lore depth** is impressive -- the planet view with dual moons, 6 nations, astronomy system, and named locations like "Temple of Awakening" suggest rich worldbuilding.
- **Art style** is functional pixel-art. It gets the job done but won't wow anyone visually.

The game feels like a sophisticated simulation/roguelike hybrid with strong systems but visual presentation that could use polish.

**Overall Rating: 6.5/10** -- Strong foundations in simulation, world generation, and game systems. Visual presentation and settlement design are the main areas needing improvement.

---

## 8. Top 10 Improvements Needed

### 1. Settlement Layout Generation (HIGH PRIORITY)
Buildings are placed in rigid rectangular grids. Implement organic town generation: curved streets, market squares, irregular lots, central plazas. Castles should have walls, keeps, courtyards, and gates.

### 2. Water Rendering (HIGH PRIORITY)
Water is a flat single color. Add: shore gradients (shallow-to-deep), wave animation patterns, river currents as directional flow indicators, and prevent the player from walking into deep ocean (the water adventure screenshot showed the player standing in open ocean with nothing around).

### 3. NPC Visual Differentiation (MEDIUM-HIGH)
All NPCs look like the same basic humanoid with different shirt colors. Differentiate by profession: guards should have helmets/armor sprites, fishermen should have poles, merchants should have carts/stalls, farmers should have tools. This would immediately make settlements more readable.

### 4. Combat/Threat Encounters (MEDIUM-HIGH)
The game world is very peaceful. Need more visible hostile encounters: wolf packs near forests, bandit camps along roads, undead in ruins. Combat is a core game system but was impossible to encounter in a 200-tick session near spawn.

### 5. Building Interior Variety (MEDIUM)
Building interiors are visible from above but are mostly empty rectangles with a few furniture dots. Add more interior detail: forge equipment for blacksmiths, shelves for shops, altars for temples, brewing equipment for taverns.

### 6. Day/Night Transition Smoothness (MEDIUM)
Dawn, midday, and dusk screenshots looked nearly identical (no visible lighting change). Only the night screenshot showed a darkness effect. The dusk/dawn transitions should have visible orange/pink tinting or gradual dimming.

### 7. NPC Job Field Population (LOW-MEDIUM)
The NPC `job` attribute returns "unknown" for all NPCs despite them clearly having active behaviors (masonry, fishing, etc.). This suggests a data pipeline issue -- jobs should be populated and visible in NPC inspection.

### 8. Terrain Transition Blending (LOW-MEDIUM)
Biome boundaries are sharp pixel edges (grass immediately becomes sand, forest stops abruptly). Add transition tiles or blending for more natural terrain borders.

### 9. Road Visual Quality (LOW)
Roads are flat tan-colored tiles. Add: cobblestone texture for city roads, dirt paths for rural roads, road edges/borders, and perhaps cart tracks or footprints for traveled routes.

### 10. Creature Variety Near Settlements (LOW)
The creature search found almost exclusively hawks and crows in the first 8 creatures. Add domestic animals near settlements (dogs, cats, pigs, horses in stables) and more diverse wildlife in the wilderness (foxes, bears, wolves in appropriate biomes).

---

## Screenshot Summary

| Category | Count | Key Files |
|----------|-------|-----------|
| World Overview | 4 | full_world, world_map at 3 zoom levels |
| Settlement Visits | 20 | 10 settlements x 2 views (strategy + adventure) |
| NPC Close-ups | 5 | Individual NPC views |
| Terrain Types | 6 | forest, dense_forest, mountain, coast, swamp, farmland |
| Creatures | 4 | hawk, crows near settlements |
| Building Detail | 4 | Close-up city buildings |
| Water Features | 2 | Lake (strategy + adventure views) |
| Road Network | 2 | Road area + world map overlay |
| UI Panels | 5 | character sheet, inventory, quest log, pause menu, planet view |
| Time of Day | 4 | dawn, midday, dusk, night |
| **Total** | **56** | |

All screenshots saved to `viewers/playtest_output/`

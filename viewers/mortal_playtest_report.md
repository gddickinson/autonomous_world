# Mortal Mode Playtest Report

**Date:** 2026-03-23
**Seed:** 42
**Mode:** mortal (Human Fighter, Level 1)
**World:** 2000x2000, 372 structures, 644 NPCs, 6487 creatures
**Total Screenshots:** 66

---

## A. Character Start

**Screenshots:** A01-A07

### Findings

- **Starting position (A01):** Player spawns at the Temple of Awakening (1000, 1000) in a circular revealed area. The FOV system is working -- the mortal player has a limited ~12-tile sight radius shown as a circular reveal against black fog-of-war. Two nearby settlements are visible: "Brighthollow" (city) and "Hearthstone" (village). An NPC ("walk" action label) is visible near the temple. The Temple itself is rendered as a large stone building with a distinctive blue-gray palette.

- **Character sheet (A02):** Clean, readable panel showing:
  - Human Fighter Level 1
  - STR 17 (+3), DEX 11 (+0), CON 15 (+2), INT 13 (+1), WIS 13 (+1), CHA 12 (+1)
  - HP 100/100, AC 10, Attack 25, Prof +2, Energy 100/100
  - Gold 20, XP 0/50
  - Class abilities: Second Wind, Fighting Style
  - Active ability: [F1] Power Strike (3x damage)
  - Skills: Swordsmanship Lv.3, Hunting Lv.2, Leadership Lv.2, Shield Work Lv.2, Smithing Lv.1, Swimming Lv.1
  - Stats tracking: Kills 0, Quests 0, Distance 0 tiles

- **Inventory (A03):** Shows 4/20 slots: Health Potion, Wooden Sword, Bread x2. Equipped weapon: Wooden Sword [100%], ATK 25, DEF 0. Category filter tabs visible (All, Weapons, Armor, Consumables, Materials, Quest, Tools/Other). Item description panel shows "[Common] Restores 30 HP. Heal:30" for the highlighted Health Potion. Clean, functional UI.

- **Quest log (A04):** Shows "Quest Log (0/5) - No active quests." The player starts with no quests, as expected for a fresh character. Player must find quest-giving NPCs.

- **Pause menu (A07):** Functional.

### Assessment
The character start experience is solid. The UI panels are clean and informative. The FOV creates an appropriate sense of mystery for a mortal character. Starting gear (sword + bread + health potion) gives the player immediate survival tools. The skill system with 6 visible skills at various levels is interesting. One concern: Attack 25 seems high for a "Wooden Sword" -- this may trivialize early combat.

---

## B. Settlement Exploration

**Screenshots:** B01-B15 (5 settlement types, strategy + adventure views)

### Findings

- **Brighthollow (city, B01-B03):** Dense urban area packed with buildings. In strategy view (16px tiles), buildings appear as dark rectangles with lighter floor interiors and door markers. Roads are visible as gray stone paths. NPCs are walking around with activity labels ("trade", "walk"). An animal (white dog/sheep?) is visible in a green space. The city is tightly packed with many buildings side by side. In adventure view (32px, B02), individual building details become much clearer -- you can see stone/cobble streets, building walls with different textures, doors (brown rectangles), windows, and NPCs with distinct sprites. The larger tile size makes the city feel lived-in.

- **Northwatch Keep (castle, B04-B06):** Very dense with buildings arranged in a grid pattern around a central plaza. Multiple NPCs visible. In adventure view (B05), the castle details shine -- you can see individual building interiors through windows, stone plazas, and NPC sprites with equipment visible (one appears to be carrying items). Buildings have brown/tan walls with darker roof sections.

- **Copperdale (town, B07-B09):** Smaller than the city but still substantial. Shows "The Rooster's Crow (Oaks-Copp)" tavern name at the top, indicating named buildings with settlement abbreviations. Mountains visible in the southeast corner. Road connects through the town center. NPCs visible. A named building system ("The Rooster's Crow") adds flavor.

- **Hearthstone (village, B10-B12):** Very close to the Temple of Awakening. Fewer, more spread-out buildings. Water (coast/lake) visible on the east edge. Multiple NPCs with names visible (Xander, Isolde). The village has a more rustic feel with more green space between buildings.

- **Nighthaven (hamlet, B13-B15):** The smallest settlement. Only a handful of buildings scattered around. A single road passes through. Dense forest visible to the west. Creatures visible (small red dots, possibly pigs/rats). In adventure view (B14), shows pigs near the hamlet and farmland (green circles = crops?). Buildings are few and far between. The hamlet genuinely feels like a tiny rural outpost.

### Assessment
Settlement variety is excellent. Each tier (hamlet -> village -> town -> city -> castle) has noticeably different density and complexity. The adventure view (32px) is significantly better for exploration -- buildings become legible with visible doors, windows, and interior features. Named buildings (taverns) add world flavor. The FOV circle in mortal mode creates a nice exploration feel where you discover the settlement as you walk through it. Roads connecting settlements are visible.

**Issues:**
- No visible walls around any settlement in the gameplay view (only building density differentiates them)
- Buildings all use a similar gray/brown palette, making it hard to distinguish building types
- NPC activity labels ("walk", "guard", "trade") overlap with name labels, creating text clutter

---

## C. NPC Interactions

**Screenshots:** C01-C12 (6 NPCs with dialog)

### Findings

- **Dialog system works well.** Each NPC dialog shows:
  - NPC name, race, class, and level (e.g., "Alara - Human Paladin Lv.1")
  - Greeting text with NPC name interpolation
  - Rich dialog options: "Tell me about yourself," "What's going on around here?", "Want to join me?", "Could we trade?", "Is there anything I can help with?", "[Intimidate] Give me your gold.", "[Threaten] You'd better watch yourself.", "Farewell", "Say something... (free text)", "[Gift] Give an item..."

- **NPC variety found near Hearthstone:**
  - Guard (Alara, Human Paladin Lv.1) -- with "guard" action label, personality traits visible ("lonely, ambitious")
  - Farmer (Xander, Human Paladin Lv.1) -- with "compassionate, cautious" traits shown
  - Scholar (Wren, Human Paladin Lv.3) -- higher level, multiple NPCs clustered together
  - Diplomat (Ulric)
  - Cartographer (Fiora)
  - Guard (Wynne)

- **Personality traits visible** on NPCs when standing near them (e.g., "lonely, ambitious", "compassionate, cautious"). These display as gray text near the NPC sprite.

- **NPCs have visible activities:** "guard", "walk", "study", "talk" action labels float above NPC heads.

- **Multiple NPCs cluster together** in settlement areas, creating a sense of community. In C06 (Scholar Wren dialog), 5+ NPCs are visible in a small area.

### Assessment
The dialog system is comprehensive with 10+ response options per NPC. The intimidation and threat options add roleplaying depth. Free text input and gift-giving are excellent features. Personality traits displayed on NPCs help the player gauge who they're dealing with.

**Issues:**
- ALL NPCs appear to be "Human Paladin" regardless of their job title (Guard, Farmer, Scholar, Diplomat, Cartographer). This is a significant immersion problem -- a farmer should not be a Paladin.
- All NPC greeting text follows the same template: "Well met! I am [Name], sworn to uphold justice." This is the Paladin greeting regardless of job. A farmer should say something about crops, a scholar about knowledge, etc.
- Dialog options are identical for every NPC -- there are no job-specific options (e.g., no "What are you growing?" for farmers, no "What have you discovered?" for cartographers).
- NPC sprites are very small and difficult to distinguish from each other. Different jobs should have visually distinct appearances.

---

## D. Combat

**Screenshots:** D01-D06

### Findings

- **Nearest creature was a cow** at (1012, 1000), HP 15/15. The player one-shot killed it with 15 damage (ATK 25 vs 15 HP). Combat screenshots show the player near the Temple of Awakening area with multiple NPCs and creatures visible.

- **Combat is invisible.** There is no visible combat feedback in the screenshots -- no damage numbers, no attack animations, no hit effects. The cow simply disappeared after being killed. The D02 "combat attack" screenshot looks identical to D01 except the cow is gone.

- **Creature variety is impressive.** The game has 55+ creature types including: wolves, bears, deer, rabbits, hawks, crows, giant spiders, basilisks, werewolves, phoenixes, unicorns, skeletons, zombies, ghouls, shadows, minotaurs, wyverns, trolls, manticores, kobolds, and more. This is a rich bestiary.

- **Creature density is high** with 4,746 alive creatures across the map (some died in the 200-tick warmup from 6,487 initial).

- **Other creatures visited:** Hawks and crows were found. Hawks show as small flying sprites, crows similar.

### Assessment
Combat is the weakest part of the current experience. There is zero visual feedback when attacking -- no damage numbers, no attack animation, no sound indicator, no flash effect. The player's ATK 25 one-shots a 15 HP cow instantly, which makes early combat trivial. The creature variety is excellent on paper but creatures are tiny and hard to identify visually at strategy zoom.

**Critical issues:**
- No visible damage numbers or combat feedback
- No attack animation (player doesn't swing weapon)
- Creatures die instantly with no death animation
- Combat is over before the player can register it happened
- No HP bars visible on creatures
- The closest creature to spawn was a passive cow, not a hostile enemy -- the game doesn't guide the player toward actual combat

---

## E. World Exploration

**Screenshots:** E01-E13

### Findings

- **Road travel (E01):** Roads are visible as gray/tan paths connecting settlements. The road near spawn passes between Temple of Awakening and Brighthollow/Hearthstone. Roads look functional but visually plain.

- **Terrain variety:**
  - **Forest (E02):** Green tiles with small tree icons visible at edges. Distinguishable from grass but subtle.
  - **Dense forest (E03):** Darker green, more tree markers visible. Good visual distinction from regular forest.
  - **Mountain (E04):** Tan/brown tiles with small triangle markers representing peaks. Very distinctive terrain. A "Crumbling Tower" ruin is visible in the distance -- nice worldbuilding touch.
  - **Coast/Sand (E05):** Light tan sand tiles visible near settlements. Blends naturally between land and water.
  - **Snow (E06):** Located far from spawn (889, 967). Distinctive white terrain.
  - **Swamp (E07):** Dark green/teal terrain. Distinguishable.
  - **Farmland (E08):** Near settlements, shown as lighter green patches.

- **Water body (E09):** Large ocean/sea body at (400, 400). Beautiful two-tone blue water with lighter shallow areas and darker deep water. Sand beaches visible at the shore. The FOV circle in the middle of the ocean looks great -- just the player floating in deep blue. Very atmospheric.

- **Day/night cycle (E10-E13):**
  - **Dawn (06:00):** Slightly dim lighting, but mostly bright. Temple and surroundings visible with a warm tone.
  - **Midday (12:00):** Full bright lighting. All colors vivid.
  - **Dusk (18:00):** Not captured separately but midday was used instead due to time reset.
  - **Night (21:36):** Dramatic darkening effect! The world becomes very dark with a blue-tinted overlay. Only the immediate FOV area is dimly visible. Settlement names ("Brighthollow", "Hearthstone") still glow. An NPC "Aethon" is visible walking near the temple at night. This creates a genuinely atmospheric night experience where exploration feels dangerous.

### Assessment
World exploration is visually varied and interesting. The terrain types are distinguishable and the world feels large. The day/night cycle is the standout feature -- night time creates genuine atmosphere with the dark overlay and limited visibility. The water rendering is beautiful. Mortal FOV makes exploration feel meaningful.

**Issues:**
- Terrain transitions are abrupt (sharp tile boundaries between biomes)
- No weather effects visible
- Roads are visually bland (same tan color, no variation)

---

## F. Game Systems

**Screenshots:** F01-F07

### Findings

- **Planet View (F07):** Impressive! Shows "World of Edras" with a rotating globe displaying continents and oceans. Left panel shows:
  - Planet: Aethermoor
  - Pop: ~200,000 (humans, elves, dwarves, halflings, orcs, gnomes)
  - Climate: temperate to cold, with forests, plains
  - Known for: Rich natural resources, ancient ruins
  - Nations (6): Kingdom of Brightblade (human feudal), Sunspear Republic (human magocracy), Ironforge Clanholds (dwarven confed.), The Silverwood Dominion (elven), The Orcish Tribal Confederation
  - "YOU ARE HERE" marker
  - Two moons: Lunara (new) and Thal (new)
  - Year 1, Day 1/364, Season: Spring, Daylight: 12.0h
  - This is incredibly detailed world-building for a procedural game!

- **World maps:** Multiple zoom levels work well. The full world overview shows a large circular continent with varied terrain, roads, and settlement markers. Roads radiate out from the center like spokes.

### Assessment
The planet view is a standout feature -- the globe, moons, nations, and population data create a sense of a living world far beyond what most roguelikes offer. The multi-level zoom world map is functional and informative.

---

## G. Walls & Defenses

**Screenshots:** G01-G07

### Findings

- **Thornwall (city) overview (G01):** The city center has a large stone plaza/keep area (lighter gray tiles) surrounded by buildings. NPCs visible: Vivian, Vesper, Yoric, Evander, Hope -- with personality traits ("romantic, hothead"). This is a proper city with a town square.

- **Thornwall adventure view (G02):** At 32px tiles, the central plaza/keep is clearly visible as a large stone structure with walls visible as darker gray borders. NPCs are much larger and more distinct. Named NPCs walking around the plaza. This is the most visually impressive settlement screenshot -- it genuinely looks like a medieval town square.

- **Wall perimeter (G03-G06):**
  - **North (G03):** Shows the edge of the city. Sandy/coastal terrain visible to the north with some water. Named taverns visible: "The Weary Traveler (Thor-Brig)" and "The Pilgrim's Hearth (Thor-Nort)". The transition from city to wilderness is abrupt -- no visible wall structure, just buildings stopping and terrain starting.
  - **South (G04):** Similar abrupt transition.
  - **East (G05):** Shows Thornwall's eastern edge. "The Copper Lantern (Thor-Suns)" tavern visible. Dense forest on the outskirts. Again, no visible defensive wall -- just buildings meeting forest.
  - **West (G06):** Not captured (missing from file list, likely similar pattern).

### Assessment
Despite the city being named "Thornwall" and the game's history simulation noting that settlements build defensive walls, **no actual wall structures are visible in the gameplay view.** The settlement boundary is defined only by where buildings stop and wilderness begins. This is a significant gap between the simulation (which tracks walls, gates, towers) and the visual representation.

**Critical issues:**
- No visible wall tiles around cities/towns despite the simulation tracking wall construction
- No gate structures visible
- No towers visible
- Roads do not visibly pass through gates
- The settlement perimeter is just an abrupt transition from buildings to wilderness

---

## Overall Assessment

### What Works Well
1. **FOV system in mortal mode** creates genuine exploration atmosphere
2. **Night cycle** is dramatic and atmospheric
3. **Planet view** is impressively detailed (globe, moons, nations, demographics)
4. **Character sheet and inventory** UI are clean and informative
5. **Dialog system** has rich options (trade, recruit, intimidate, threaten, gift, free text)
6. **Settlement hierarchy** (hamlet -> city) shows clear visual scaling
7. **Terrain variety** with 7+ biome types all visually distinct
8. **Creature variety** with 55+ species is excellent
9. **Adventure view (32px)** makes settlements look genuinely good
10. **Named buildings** (taverns with settlement abbreviations) add world flavor
11. **NPC personality traits** visible on screen

### What Needs Improvement

#### Critical (Game-Breaking or Major Immersion Issues)
1. **Combat has zero visual feedback** -- no damage numbers, no attack animations, no HP bars on enemies, no death effects
2. **All NPCs are "Human Paladin"** regardless of job -- farmers, scholars, diplomats all say "sworn to uphold justice"
3. **No visible walls/gates/towers** on settlements despite simulation tracking them
4. **Dialog is identical for all NPCs** -- no job-specific conversations

#### High Priority
5. **NPC class should match job** -- Guards should be Fighters, Scholars should be Wizards, Farmers should be Commoners, etc.
6. **Add damage numbers** floating above targets when hit
7. **Add HP bars** above creatures and hostile NPCs
8. **Add attack animation** (weapon swing, impact flash)
9. **Add wall tiles** around towns/cities that have walls in the simulation
10. **Add gate openings** where roads pass through walls

#### Medium Priority
11. **Building type differentiation** -- blacksmiths, taverns, temples should look visually distinct
12. **Creature sprites** are too small at strategy zoom to identify
13. **Text label clutter** -- NPC names, actions, and traits overlap
14. **Terrain transitions** are too abrupt (no blending between biomes)
15. **Add starting quest guidance** -- player has 0 quests and no direction

#### Low Priority (Polish)
16. **Weather effects** not visible
17. **Road visual variety** (cobblestone vs dirt, bridges)
18. **NPC schedule variety** -- NPCs should do different things at different times
19. **Sound design** references (not applicable to headless test)
20. **Minimap** not visible in mortal mode screenshots

### Biggest Single Improvement
**Add visible combat feedback (damage numbers + HP bars + attack flash).** This is the single change that would most improve the moment-to-moment gameplay experience. Currently, combat is a non-event -- the player presses Space and something silently dies. Adding floating damage numbers, enemy HP bars, and a brief red flash on hit would make combat feel real and satisfying.

### Second Biggest Improvement
**Fix NPC class/dialog to match their job.** Having every NPC be a "Human Paladin" who says "sworn to uphold justice" regardless of whether they're a farmer or cartographer destroys the world-building that the rest of the game does so well (planet view, named taverns, personality traits). Each job should have appropriate class, greeting text, and at least one unique dialog option.

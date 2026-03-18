# Autonomous World - Development Roadmap

## Project Status (March 2026)

**Codebase:** 142 Python files, ~94,000 lines of code
**Engine:** Pygame-CE with OpenGL 3D mode
**World:** 10,000 x 10,000 chunked tile map (numpy int8, LRU cache)
**NPCs:** 2,500+ with jobs, needs, economies, relationships
**Settlements:** 130-260 across 6-11 kingdoms with specializations

### Completed Systems

| System | Status | Description |
|--------|--------|-------------|
| Chunked World | Done | 10K x 10K with numpy chunks, LRU cache, disk persistence |
| History Simulation | Done | 500-year tribal migration + settlement founding |
| 3 View Modes | Done | Strategy (16px), Adventure (32px), OpenGL 3D |
| Economy | Done | 201 items, supply chains, markets, pricing, gold conservation |
| 50+ Professions | Done | Physical work behaviors, workplaces, production |
| Goods Transport | Done | Porters, pack animals, carts, trade caravans |
| 6-11 Kingdoms | Done | Governance, diplomacy, military, tax |
| Combat | Done | Real-time + tactical, abilities, party system |
| Ecology | Done | Predator-prey, seasonal breeding, 30+ creature types |
| Demographics | Done | Birth, death, marriage, aging, class mobility |
| Buildings | Done | 40+ blueprints, interiors, multi-floor, underground |
| God Mode | Done | Floating panel UI, inspector, tools, tweaker, Python console, hot reload |
| Claude AI | Done | God mode assistant with secure API key storage |
| Save/Load | Done | Full game state serialization |
| Config System | Done | 30+ settings with menus and persistence |
| Technology Tree | Done | 17 techs across 4 eras (Stone -> Steel) |
| Culture/Religion | Done | 5 religions, temples, festivals, education |
| Warfare | Done | Armies, sieges, Lanchester combat, war/peace |
| Construction | Done | Building projects, roads, settlement founding |
| Visual Effects | Done | Particles, smoke, damage numbers, ambient life |
| Multiplayer | Done | TCP server/client, AI player, chat system |

---

## Phase 1: Polish & Stability (Current)
**Goal:** Make the existing game robust and enjoyable to play for extended sessions.

### 1.1 Bug Fixes & Performance
- [x] Fix NPC needs not decaying (dormant NPCs)
- [x] Fix NPC gold never changing (time scaling)
- [x] Fix event log not persisting
- [x] Fix 71% NPCs lacking work state
- [x] Fix only 1 market registered
- [x] Fix settlement_planner range() float error
- [x] Fix roof flickering (removed terrain cache)
- [x] Fix god mode toolbar obscuring UI (floating panel)
- [x] Optimize frame time (6ms avg, particles capped)
- [ ] Fix chunk loading hitches when moving fast
- [ ] Stress test 500+ NPCs with economy running
- [ ] Fix edge cases in save/load for chunked world

### 1.2 Graphics Polish
- [x] Building roof color variety by function
- [x] Smoke particles from chimneys
- [x] Market stall awnings
- [x] Farm field patterns
- [x] Town walls and gates
- [x] Damage number popups
- [x] Speech bubbles and emotion icons
- [x] Ambient birds, leaves, water ripples
- [x] Day/night lighting with smooth transitions
- [x] Weather visual effects (rain drops, snow, fog overlay)
- [x] Seasonal color palette changes (autumn leaves, winter snow)
- [x] NPC equipment rendering (weapons, armor visible on sprite)
- [ ] Building construction animation (scaffold -> finished)

### 1.2b Procedural Character Animation System
**Approach:** Programmatic stick-figure/cartoon animation drawn in code (no sprite sheets needed). Characters are rendered as assembled body parts with procedural movement. Only active in Adventure (32px) and 3D views where tiles are large enough.

- [ ] **Body part rendering system:**
  - Characters drawn as assembled parts: head (circle), torso (rectangle), arms (lines), legs (lines)
  - Each part has position offset from center, rotation angle, color
  - Size scales with tile size (tiny in 16px strategy, detailed in 32px adventure)
  - Different body shapes: humanoid (NPCs/player), quadruped (animals), tall (ogre), small (goblin)
  - Equipment overlays: sword line at hand, shield rectangle at arm, hat on head, armor tint on torso
- [ ] **Animation state machine:**
  - States: idle, walk, run, attack_melee, attack_ranged, cast_spell, block, hit_react, die, sleep, sit, climb, carry, swim, pray, craft
  - Each state has keyframes defining body part positions/rotations over time
  - Smooth interpolation between keyframes (lerp)
  - State transitions: walk->run (speed threshold), idle->attack (combat), walk->climb (stairs)
  - Direction support: facing left/right (mirror), facing up/down (different limb visibility)
- [ ] **Procedural walk cycle (Rain World inspired):**
  - IK-based leg movement: calculate hip-to-ground distance, step when too far
  - Arms swing opposite to legs
  - Head bobs slightly
  - Speed varies walk frequency (slow walk vs run)
  - Carrying items: one arm fixed, load visible
- [ ] **Combat animations:**
  - Melee: arm swings weapon arc, body lunges forward, recoil on hit
  - Ranged: arm pulls back, releases, projectile spawns
  - Magic: arms raise, colored particles emanate from hands
  - Block: shield arm raised, body braces
  - Hit reaction: body jerks back, brief red flash
  - Death: body collapses (parts fall, fade to gray)
- [ ] **Idle and social animations:**
  - Idle: slight breathing motion (torso expands/contracts), occasional head turn
  - Sleeping: lying down, Z particles
  - Sitting (tavern/bench): legs bent, torso upright
  - Crafting: arms move in repetitive motion
  - Praying: kneeling, hands together
  - Talking: head tilts, small speech bubble
- [ ] **Performance strategy:**
  - Strategy view (16px): colored dots only, no animation (current approach)
  - Adventure view (32px): full procedural animation
  - 3D view: 3D equivalents if feasible
  - Only animate entities within screen bounds
  - Cache animation frames for common states to avoid per-frame calculation
  - Max 50 animated entities at once (nearest to camera)

### 1.3 Weather as a Living System
- [x] **Simple global climate model (visible on world map):**
  - 2-3 pressure systems (high/low) that drift across the map over days
  - High pressure = clear skies, low pressure = clouds/rain/storms
  - Pressure systems spawn at map edges, drift with prevailing wind direction, dissipate after crossing
  - Temperature gradient: north = cold, south = warm (or configurable), modified by altitude and season
  - Moisture: coastal tiles are wetter, inland tiles drier; mountains block rain (rain shadow)
  - Season shifts the baseline: winter pushes cold south, summer pushes warmth north
  - World map overlay: isobars or colored pressure zones, wind arrows, cloud cover, temperature bands
  - Each chunk/region samples the global model to get local weather (no per-tile simulation needed)
  - Simple enough to compute in <1ms per game-day update
- [x] **Weather affects terrain activities:**
  - Rain: farmland productivity +20%, roads become muddy (slower travel), mining unaffected, fishing dangerous at sea
  - Snow: farming impossible, roads very slow, hunting harder (animals hide), woodcutting slower, construction halted
  - Drought: crops wither and die, wells dry up (thirst crisis), fire risk in forests, rivers shrink
  - Storm: all outdoor work halted, fishing/sailing deadly, trees can fall (lumber), lightning strikes (fire risk)
  - Fog: reduced visibility, travel slower, ambush risk increased, fishing slightly easier (calm water)
  - Heat wave: outdoor workers tire faster (exhaustion), crops stressed, water consumption doubles
- [x] **Weather affects emotions:**
  - Prolonged rain: sadness creeps up, NPCs seek shelter and social contact
  - Sunny after rain: joy boost for all outdoor NPCs
  - Storms: fear for those caught outside, anticipation for those sheltered
  - Bitter cold/snow: sadness + fear for poorly housed NPCs, cozy trust for those with warm homes
  - Drought: anxiety (anticipation + fear) spreads through farming settlements
  - Perfect weather: general joy + optimism boost
- [x] **Weather creates jobs and demands:**
  - Floods: need sandbaggers, rescuers, rebuilders; demand for wood/stone surges
  - Drought: need well-diggers, water carriers, irrigation workers; water prices spike
  - Snow: need snow-clearers, firewood cutters; fuel demand surges
  - Storm damage: need roofers, builders, healers; construction materials in demand
  - Heat wave: need water carriers, shade builders; ice/cold goods valuable
- [x] **Natural disasters by terrain:**
  - **River/coast:** Floods -- rising water destroys low-lying buildings, drowns NPCs, washes away goods. Severity based on rainfall duration + river size
  - **Plains/farmland:** Drought -- crops fail across region, famine spreads, migration triggered, wars over water
  - **Forest:** Wildfire -- lightning or drought + heat ignites forests, destroys lumber camps, animals flee, smoke chokes nearby settlements
  - **Mountain:** Avalanche/landslide -- buries roads and mines, traps NPCs, cuts off trade routes
  - **Coast:** Tsunami/storm surge -- massive wave destroys port structures, ships lost, coastal settlements devastated
  - **Swamp:** Plague -- stagnant water breeds disease in hot weather, spreads to nearby settlements via trade
  - **Desert:** Sandstorm -- buries roads, damages buildings, blinds travelers, caravans lost
  - **Tundra:** Blizzard -- extreme cold kills exposed NPCs, buildings buried, total isolation for days
- [x] **Disaster aftermath:**
  - Refugees flee to neighboring settlements (population shift)
  - Reconstruction creates economic boom for builders/craftsmen
  - Gods may intervene (nature god calms storms, death god claims the fallen)
  - Emotional impact: survivors carry trauma (fear, sadness), heroes emerge (trust, admiration)
  - Soul system: mass death events create ghost clusters (haunted disaster sites)
  - Historical record: disasters become part of world history ("The Great Flood of Year 423")

### 1.4 Health, Disease & Medicine
- [x] **Individual health model:**
  - Each NPC/creature has: HP (acute), constitution (baseline), immune_strength (0-1), active_conditions list
  - Conditions reduce stats, cause symptoms, can spread, can kill
  - Recovery depends on: rest, food quality, shelter, medicine, healer access, constitution
- [x] **Seasonal illnesses:**
  - Winter: common cold (mild, spreads fast, -10% work speed), flu (moderate, fever, bedridden 2-5 days), frostbite (exposure, permanent stat damage if untreated)
  - Spring: allergies (mild, outdoor workers affected), food poisoning (bad winter stores)
  - Summer: heatstroke (outdoor workers in hot biomes), dysentery (bad water in crowded settlements)
  - Autumn: harvest fever (fungal, affects farmers), melancholy (sadness + shorter days)
- [x] **Infections & wounds:**
  - Combat wounds can become infected if untreated (10% chance per wound)
  - Infection stages: minor (treatable easily) -> serious (needs healer) -> sepsis (often fatal)
  - Animal bites: risk of rabies (rare, always fatal without divine intervention)
  - Burns: from fire/forge accidents, slow healing, scarring
- [x] **Contagious diseases:**
  - Common cold: low severity, high spread rate, 3-day duration, builds temporary immunity
  - Plague: high severity, moderate spread, often fatal, spreads via rats/trade routes/crowding
  - Pox: moderate severity, permanent scarring, one-time immunity after recovery
  - Consumption (TB): slow-building, chronic, affects lungs, spreads in crowded buildings
  - Swamp fever (malaria): contracted in swamp biomes, recurring bouts, debilitating
  - Red death (cholera): waterborne, explosive outbreaks near bad water, very fast kill rate
- [x] **Disease spread mechanics:**
  - Proximity: NPCs within 2 tiles of infected can catch airborne diseases
  - Trade routes: merchants carry diseases between settlements
  - Water contamination: settlements downstream of infected ones at risk
  - Crowding multiplier: cities spread disease faster than hamlets
  - Quarantine: settlements can isolate sick NPCs (reduces spread, costs labor)
  - Seasonal modifier: winter suppresses insect-borne, amplifies respiratory
- [x] **Medicine & healing:**
  - Herbalist profession: gathers medicinal herbs, makes poultices and remedies
  - Healer/physician profession: treats wounds and illness, effectiveness scales with skill
  - Apothecary: crafts medicines from herbs (new supply chain: herbs -> remedies -> medicine)
  - Temple healing: priests can pray for divine healing (costs god miracle points)
  - Hospitals/infirmaries: building type that speeds recovery, concentrates healers
  - Folk remedies: some work (willow bark = pain relief), some don't (leeches = no effect)
- [x] **Epidemic events:**
  - Plague outbreak: triggered by rat population + trade + crowding; can devastate settlements
  - Quarantine decisions: leaders can close gates (stops trade but slows spread)
  - Mass graves needed (burial system integration)
  - Emotional impact: fear spreads faster than the disease itself
  - Economic impact: workers sick = production drops, food shortages compound illness
  - Historical: epidemics recorded in world history, settlements remember "the great plague"
  - Soul impact: mass death events drain the soul pool, create ghost clusters
  - Divine response: death god watches with interest, nature/love gods may intervene

### 1.5 Mental Health
- [x] **Mental health conditions** -- long-term psychological states distinct from momentary emotions:
  - Depression: prolonged sadness + grief + isolation. Work output -40%, social withdrawal, sleep disruption, appetite loss. Can be triggered by: bereavement, prolonged poverty, chronic pain, winter darkness
  - Anxiety: chronic fear + anticipation. Constant vigilance, difficulty concentrating (study -30%), avoids crowds, insomnia. Triggered by: combat trauma, repeated threats, loss of security
  - PTSD: flashbacks from traumatic events (combat, witnessing death, torture). Random panic episodes, avoids trigger locations, nightmares disrupt rest. Combat veterans and disaster survivors at risk
  - Mania: euphoric hyperactivity. Works 50% faster but makes reckless decisions, overspends gold, picks fights, grandiose plans. Often follows depression (bipolar cycle)
  - Paranoia: extreme distrust. Refuses to trade, suspects allies, may attack friends, hoards resources. Triggered by betrayal, poisoning, isolation
  - Addiction: dependency on alcohol (tavern), drugs (alchemist), gambling. Seeks substance compulsively, withdrawal causes anxiety+anger, neglects duties, spends all gold
  - Grief disorder: prolonged grief after death of loved one that doesn't resolve. Visits grave obsessively, can't work, emotional numbness
  - Burnout: from sustained overwork without rest or social contact. All work output -50%, cynicism, emotional flatness
- [x] **Mental health interacts with emotions:**
  - Depression dampens all positive emotions (joy response halved)
  - Anxiety amplifies fear responses (2x intensity)
  - PTSD creates random emotion spikes (sudden fear/anger from triggers)
  - Mania amplifies joy and anger, suppresses fear
  - Paranoia amplifies disgust and anger toward others
- [x] **Mental health affects the body:**
  - Depression: immune_strength -20%, appetite loss (hunger need decays slower but health suffers)
  - Anxiety: exhaustion rate +30%, stress-related illness risk
  - Addiction: liver damage (constitution loss over time), malnutrition
  - Burnout: susceptibility to illness +40%
- [x] **Treatment and recovery:**
  - Social support: friends/family nearby reduce depression severity
  - Rest and safety: secure housing + adequate food helps anxiety
  - Healer NPCs: can counsel (skill-based, slow improvement)
  - Temple: prayer and community provide comfort (trust + joy boost)
  - Tavern: temporary relief but risk of addiction
  - Time: most conditions slowly improve if triggers removed
  - Gods: love god or nature god may intervene for devout sufferers
  - Community response: settlements with high morale have lower mental health issues
- [x] **Societal effects:**
  - Settlements with many depressed/anxious NPCs have lower productivity
  - Traumatized soldiers returning from war spread anxiety
  - Addiction clusters form around taverns in low-morale settlements
  - Leaders with mental health conditions make worse decisions (paranoid king, manic general)
  - Children of mentally ill parents at higher risk (both genetic + environmental)
  - Stigma: some NPCs avoid mentally ill (disgust emotion), progressive settlements more accepting

### 1.6 Detailed Body & Damage Model
- [x] **Body part system** -- replace simple HP with locational damage:
  - Body parts: head, torso, left_arm, right_arm, left_leg, right_leg
  - Each part has: hp, max_hp, status (healthy, injured, broken, severed, burned)
  - Total HP is sum of all parts; death when head or torso reaches 0
  - Injury to limbs causes functional impairment, not death
- [x] **Damage types with different effects:**
  - Blunt force (mace, fist, fall): bruising, broken bones, concussion. Heals slowly. Armor reduces well
  - Slashing (sword, claw): cuts, bleeding. Fast damage, moderate healing. Bandages stop bleeding
  - Piercing (arrow, spear, bite): puncture wounds, internal damage. Risk of infection high
  - Fire (torch, dragon breath, forge accident): burns by degree (1st/2nd/3rd). Very slow healing, scarring. Pain causes fear
  - Acid (monster attack, alchemy accident): dissolves armor first, then flesh. Permanent scarring
  - Frost (ice magic, blizzard exposure): frostbite, numbness, tissue death. Slow onset, long recovery
  - Poison (snake bite, poisoned weapon, bad food): systemic damage over time, affects all parts. Antidote needed
  - Divine/necrotic (undead drain, curse): drains max_hp, resists normal healing. Only divine healing works
- [x] **Injury consequences on activities:**
  - Broken arm: can't swing weapon (50% combat), can't carry heavy goods, can't craft
  - Broken leg: movement speed halved, can't run, can't climb stairs
  - Head injury: confusion (random wrong actions), can't read/study, speech impaired
  - Torso wound: all activities slower, exhaustion rate doubled
  - Burns: constant pain (anger/fear emotions), all activities slower until healed
  - Blinded (head acid/fire): can't fight effectively, can't read, need guide
  - Lost limb (severed): permanent unless divine intervention. Prosthetics possible (wooden leg, hook hand)
- [x] **Healing methods by damage type:**
  - Blunt: rest + time (bones knit in 20-40 game days), healer speeds 2x, splints help
  - Slashing: bandages stop bleeding, stitches by healer, heals in 10-20 days
  - Piercing: remove projectile first (healer), risk of infection, 15-25 days
  - Fire: cool water first, salve/poultice, very slow (30-60 days), permanent scarring
  - Acid: neutralize with alkali, then treat as burn. Armor destroyed
  - Frost: gradual warming (NOT fire), 15-30 days, risk of gangrene -> amputation
  - Poison: antidote within hours or escalating damage, herbalist craft
  - Divine: only temple healing or god miracle can reverse
- [x] **Object/structure damage:**
  - Buildings: fire destroys wood, siege weapons destroy stone, acid corrodes metal fittings
  - Weapons: blunt weapons dent, blades chip, handles break. Durability system
  - Armor: absorbs damage but degrades. Different armor vs different damage types (plate good vs slash, bad vs blunt; leather good vs blunt, bad vs pierce)
  - Shields: block damage to body part, take damage themselves, can break
  - Walls/fortifications: damage types matter (battering ram = blunt, fire arrows = fire, siege = crush)
  - Repair professions: blacksmith repairs metal, carpenter repairs wood, mason repairs stone
- [x] **Visual indicators:**
  - Injured NPCs limp (broken leg), hold arm (broken arm), move slowly (torso wound)
  - Bandages visible on injured NPCs
  - Burn scars as permanent visual marker
  - Blood trails from bleeding wounds

### 1.6 Combat & UI Polish
- [x] Combat feedback: screen shake on big hits
- [x] Spell effects (fireballs, healing glow, lightning)
- [x] Enemy health bars above creatures
- [ ] Tutorial/onboarding for first-time players
- [ ] Quest tracker HUD widget
- [ ] Better inventory UI with item categories

---

## Phase 2: Emotions, Children & Inner Life
**Goal:** All living beings become psychologically deep creatures driven by emotion, not just needs.

### 2.1 Plutchik's Wheel of Emotions
- [x] Implement the 8 primary emotions: joy, trust, fear, surprise, sadness, disgust, anger, anticipation
- [x] Secondary emotions from combinations: love (joy+trust), submission (trust+fear), awe (fear+surprise), disapproval (surprise+sadness), remorse (sadness+disgust), contempt (disgust+anger), aggressiveness (anger+anticipation), optimism (anticipation+joy)
- [x] Tertiary blends for nuanced states
- [x] Emotion intensity levels (e.g., annoyance -> anger -> rage)
- [x] Emotions decay over time but can be reinforced by repeated experiences
- [x] Emotional memory: NPCs remember WHO made them feel WHAT
- [x] Personality traits (Big Five) that bias emotional responses

### 2.2 Emotion-Driven Behavior
- [x] **Work performance:** Happy NPCs work faster/better, miserable ones slack off, make mistakes, quit
- [x] **Rebellion:** Accumulated anger + low trust toward leader triggers rebellion, joining rival factions, or outright revolt
- [x] **Crime:** Desperate (fear+anger) NPCs steal, assault, murder; resentful ones vandalize, sabotage
- [x] **Social dynamics:** Love leads to partnerships, gifts, sacrifice; contempt leads to bullying, exclusion, betrayal
- [x] **Grudges & vendettas:** NPCs harbour resentments against specific individuals (tracked by target + emotion + intensity + memory of cause)
- [x] **Joy spreading:** Happy NPCs boost morale of those around them; celebrations, jokes, music
- [x] **Grief cascade:** Death of a loved one triggers sadness in connected NPCs, potentially spiraling
- [x] **Fight or flight:** Fear triggers fleeing; anger triggers confrontation; the balance depends on personality
- [x] **Mood visible:** Emotion icons above NPCs, body language in movement speed/posture

### 2.3 Universal Emotions -- All Creatures Feel
- [x] **Every entity type gets EmotionState** with type-specific triggers and effects:
  - **NPCs:** Full system (already done) -- work, rebellion, crime, social, grudges
  - **Player character (autoplay):** Emotions influence autoplay decisions -- fear makes auto-player flee, anger makes them fight, joy makes them explore, sadness makes them seek taverns/friends. Emotional state shown in HUD
  - **Animals/wildlife:** Simplified emotions -- primarily fear, anger, anticipation. Fear of predators/fire/loud noises triggers fleeing. Mother animals feel protective anger if young threatened. Pack animals share emotional contagion (one panics, herd panics). Content animals graze calmly, stressed animals are erratic
  - **Monsters:** Fear/anger/anticipation drive combat behavior. Intelligent monsters (dragons, liches) get full emotion range -- can feel contempt, pride, grudges against adventurers who wounded them. Boss monsters remember and hate players who escaped
  - **Gods:** Emotions operate on cosmic timescale -- slow to change, immense in effect. A wrathful god sends plagues. A joyful god blesses the land. Gods feel jealousy toward rival gods with more worshippers. Their emotional state influences miracle selection
  - **Souls (ghost state):** Echo emotions from moment of death persist and intensify. Violently killed souls radiate fear/anger, creating haunted atmosphere. Peaceful souls radiate serenity. Soul emotions influence what kind of body they're drawn to for reincarnation
- [x] **Emotional contagion:** Nearby creatures influence each other's emotions
  - Panicked animals spread panic to nearby animals (stampede)
  - An NPC's visible fear makes nearby NPCs anxious
  - A god's wrath creates unease in their followers
  - Undead radiate fear to living creatures within range
- [x] **Type-specific personality profiles:**
  - Animals: instinct-driven (high neuroticism for prey, low for predators)
  - Monsters: species-typical (dragons = low agreeableness + high openness, goblins = high neuroticism + low conscientiousness)
  - Gods: extreme personality traits matching their sphere
  - Souls: personality persists from last life, subtly influences next host

### 2.4 Children & Darwinian Inheritance
- [x] **Pregnancy & birth:** Couples produce children after relationship + mating; pregnancy takes game-time
- [x] **Child entities:** Children are small, weak, dependent NPCs with accelerated learning
- [x] **Parental care required:** Children need food, shelter, supervision -- neglected children sicken and die
- [x] **Orphan system:** If parents die, settlement or relatives take over; otherwise child becomes street urchin
- [x] **Attribute inheritance:** Children inherit stats from parents with variation:
  - Physical stats (strength, speed, constitution): weighted average + mutation
  - Mental stats (intelligence, wisdom, charisma): weighted average + mutation
  - Personality traits: blend of parents with random drift
  - Skills: children start with aptitude bonuses in parent professions
- [x] **Memory inheritance:** Children "learn" 1-2 key memories from each parent (stories told to them) -- these become founding memories that shape personality
- [x] **Darwinian selection:** Over generations, settlements evolve:
  - Mining towns produce stronger children
  - Scholar cities produce smarter children
  - Dangerous frontiers produce hardier children
  - This happens naturally through who survives and breeds
- [x] **Coming of age:** Children grow up, choose profession (influenced by parents + personality + settlement needs)
- [x] **Family trees:** Track lineage; family loyalty as a social bond

---

## Phase 3: Souls, Death & the Afterlife
**Goal:** A metaphysical layer that gives meaning to death and creates emergent spiritual narratives.

### 3.1 The Soul System
- [x] **Soul entity:** Each living creature has a Soul object with:
  - Unique soul_id (persistent across games)
  - Age (total time existed, across all incarnations)
  - Alignment drift (accumulated moral tendency from past lives)
  - Affinity (elemental/divine/nature -- influences what bodies it's drawn to)
  - Power level (grows with experience across lifetimes)
  - Echo memories: 1-2 strongest memories from each past host (kept forever)
- [x] **Soul pool:** Fixed number of souls in the world (configurable, default ~500 tracked, rest statistical)
  - New births draw from the pool of free souls
  - Souls prefer bodies that match their affinity (warrior soul -> warrior family)
  - Rare: very old souls bring faint echoes of past lives (deja vu, instinctive skills)
- [x] **Performance:** Only ~500 souls are individually tracked
  - Remaining creatures use statistical soul behavior (probability of past-life effects)
  - Tracked souls are prioritized for: player-nearby NPCs, important NPCs (rulers, heroes), old/powerful souls

### 3.2 Death & Body Disposal
- [x] **Death types affect soul release:**
  - Natural death: soul releases peacefully, enters free pool immediately
  - Violent death: soul is traumatized, lingers as ghost for a time before freeing
  - Sacrificial death: soul is claimed by the god the sacrifice was to
  - Undead death: soul was already consumed -- nothing remains
  - Drowning/burning: soul releases but with emotional scarring
- [x] **Body disposal methods:**
  - Burial in churchyard: proper rest, soul freed cleanly, grave marker placed
  - Cremation: faster soul release, ashes remain
  - Left to rot: soul lingers longer, risk of haunting
  - Sea burial (coastal): soul drawn to water affinity
  - Sky burial (mountain cultures): soul drawn to air/nature affinity
  - Mass grave (war/plague): multiple traumatized souls, haunting risk high
- [x] **Churchyards & graves:**
  - Settlements with temples have churchyards with individual grave tiles
  - Graves show name, dates, epitaph
  - Visiting a grave: player can read about the dead, sense the soul's state
  - Old graves from history simulation: ancient heroes, forgotten kings
  - Graveyard full -> expansion or cremation policy
- [x] **Ghost state:**
  - Souls between bodies float as semi-visible ghosts
  - Ghosts drift toward places they knew in life
  - Ghosts can be seen by player in ghost mode
  - Ghost density creates "haunted" locations (battlefields, ruins, mass graves)
  - Ghosts fade over time as they find new bodies or pass on

### 3.3 Undead & Soul Predation
- [x] **Undead creatures:** Vampires, liches, wraiths, ghouls, skeletons, zombies, wights
- [x] **Soul feeding:** Undead sustain themselves by consuming souls from the living
  - Drains the victim's life force (HP + max HP reduction)
  - The undead absorbs fragments of the soul's attributes and memories
  - An undead that has consumed many souls becomes powerful and knowledgeable
  - A fully drained victim dies and their soul is destroyed (removed from pool permanently)
- [x] **Undead ecology:**
  - Undead are drawn to areas of high soul density (cities)
  - They avoid temples and holy ground (divine souls resist)
  - Necromancers can bind free-floating ghosts into undead bodies
  - The soul pool slowly shrinks if undead go unchecked -> population decline
- [x] **Counter-measures:**
  - Priests can ward areas against undead (soul barrier)
  - Holy weapons damage the undead's stolen soul fragments
  - Exorcism: free consumed souls from a destroyed undead
  - Player can hunt undead to protect the soul pool

### 3.4 Reincarnation & Past Lives
- [x] **Soul matching at birth:** When a child is born, a free soul enters:
  - Affinity matching: warrior souls seek warrior families, scholar souls seek cities
  - Geographic preference: souls prefer rebirth near where they last lived
  - Old souls sometimes bring fragments of past-life skills (prodigy effect)
- [x] **Deja vu moments:** NPCs with old souls occasionally:
  - Recognize places from past lives ("this place feels familiar...")
  - Have instinctive knowledge of skills they never learned
  - Feel unexplained kinship or animosity toward strangers (echoes of past-life relationships)
- [x] **Cross-species souls:** Souls can inhabit any creature:
  - A human soul in a wolf -> unusually intelligent wolf
  - An ancient wolf soul in a human -> person with uncanny animal instincts
  - This creates emergent character depth without scripting
- [x] **Soul persistence across games:**
  - Soul pool saves to a separate file (not per-save)
  - Starting a new game: souls carry over with their accumulated memories
  - Players might encounter NPCs with souls that remember events from previous playthroughs
  - This creates a meta-narrative across multiple games

---

## Phase 4: The Pantheon -- Gods as AI Agents
**Goal:** Gods exist outside the game as watching intelligences that occasionally intervene.

### 4.1 God Entities
- [x] **Pantheon of 7 gods**: Tharion (war), Sylvana (nature), Verithos (knowledge), Morwen (death), Auriel (commerce), Lyria (love), Xaotl (chaos)
  - Name, personality, sphere of influence (war, nature, knowledge, death, commerce, love, chaos)
  - Alignment tendency (benevolent, neutral, malevolent)
  - Attention budget: limited "miracle points" that regenerate slowly
  - Knowledge: gods see everything within their sphere but are blind outside it
  - Relationships with other gods: rivalry, alliance, indifference
- [x] **God AI (when LLM available):**
  - Each god runs as an advanced LLM agent watching the game
  - They observe events within their sphere: god of war watches battles, god of commerce watches trade
  - They form opinions about mortals, settlements, kingdoms
  - They make strategic decisions about when to intervene
  - Personality drives intervention style: god of chaos causes disruption, god of knowledge reveals secrets
- [x] **God AI (when LLM unavailable):**
  - Fallback to rule-based behavior
  - Simple heuristics: intervene if devotee is in extreme danger, if temple is threatened
  - Statistical miracles based on prayer frequency and alignment

### 4.2 Prayer & Divine Intervention
- [x] **Prayer system:**
  - NPCs pray at temples or in desperation
  - Prayers have content: "protect my family," "smite my enemy," "heal my child," "grant harvest"
  - Prayer strength: devotion level + emotion intensity + sacrifice offered
  - Gods receive prayers and decide whether to act (LLM reasoning or heuristic)
- [x] **Miracles (10 types, rare, impactful):**
  - Healing: cure disease, restore HP, revive recently dead
  - Protection: shield a settlement from invasion, calm a storm
  - Smiting: strike an enemy with lightning, cause plague on a city
  - Blessing: boost crops, increase birth rate, inspire a leader
  - Revelation: grant knowledge of a hidden dungeon, warn of coming danger
  - Cursing: mark a person for misfortune, weaken an army
- [ ] **God mode entry:** Gods can enter the game as the player does in god mode
  - Take direct action: move NPCs, spawn creatures, change terrain
  - Visible to devout NPCs as visions
  - Cost: drains miracle points heavily

### 4.3 Gods Petitioning the Higher Power (The game creator)
- [x] **Meta-petition system:**
  - Gods can recognize limitations of their reality
  - They can compose petitions to the "Higher Power" (the developer)
  - Petitions appear as in-game messages or god-mode notifications (log that the developer can examine)
  - Content: "The souls grow too few. Grant more souls to the world." / "The undead plague threatens all. Grant mortals stronger weapons." / "The wars never end. Change the nature of diplomacy."
  - These are essentially AI-generated feature requests / balance suggestions
  - Player can accept (triggering a config change or game event) or reject
  - Creates a unique feedback loop: the game's AI tells you what it wants
  - This should also provide a way to improve game play and make code changes based on observations about how the game is going made from continual observation

### 4.4 Divine Competition
- [x] **Inter-god dynamics:**
  - Gods compete for worshippers (more devotees = more power)
  - Gods can sabotage each other's followers
  - Alliances between gods manifest as combined miracles
  - A dominant god shapes the world's culture toward their sphere
  - God wars: when two gods' followers go to war, the gods themselves amplify the conflict
- [x] **Heresy & schism:**
  - NPCs can lose faith (emotional crisis + unanswered prayers)
  - Religious conversion: NPCs switch allegiance
  - New cults: charismatic NPCs can found new religions (new god emerges?)
  - Atheism: some NPCs reject gods entirely (empiricism trait)

---

## Phase 5: Depth & Content
**Goal:** Make the world feel alive with meaningful choices.

### 5.1 Faction & Reputation System
- [x] Player reputation per kingdom (-100 to +100)
- [x] Faction quests that affect standing
- [x] Crime system (theft, assault, murder -> bounty)
- [ ] Faction-specific gear and abilities

### 5.2 Quest System Overhaul
- [x] Procedurally generated quest chains
- [x] Multi-stage quests with branching outcomes
- [x] World-state consequences
- [x] Bounty board at taverns

### 5.3 Magic System
- [x] Schools of magic: elemental, divine, arcane, nature (20 spells implemented)
- [x] Spell learning, mana, enchanting
- [x] Alchemy with ingredient gathering
- [x] Soul magic: spells that interact with the soul system
- [ ] **Extensive AD&D-inspired magic expansion:**
  - Spell levels 1-9 (cantrips through world-altering). Powerful magic extremely rare and difficult
  - 100+ spells total across all schools (currently 20, expand significantly)
  - Spell components: verbal, somatic, material (rare ingredients for powerful spells)
  - Spell preparation: mages must study/prepare spells daily from spellbooks
  - Concentration: some spells require sustained focus, broken by damage
  - Ritual casting: slow but powerful, multiple casters can combine for greater effect
  - Wild magic: failed casting has random dangerous effects
  - Counterspell: mages can disrupt each other's casting
  - Spell resistance: some creatures/items resist magic
  - Gods can cast ANY spell at any level without components or mana (divine power)
- [ ] **Wide range of magic practitioner types:**
  - **Wizard:** Academic mage, learns from books/study, all arcane spells, needs spellbook
  - **Sorcerer:** Innate magic from bloodline, fewer spells but more flexible casting, no book needed
  - **Cleric:** Divine magic from god devotion, healing + protection + smiting, power depends on faith
  - **Druid:** Nature magic, shapeshifting, weather control, plant/animal communication
  - **Warlock:** Pact magic from entity (god, demon, fey), unique eldritch spells, patron demands
  - **Paladin:** Holy warrior, limited divine casting, smite evil, lay on hands healing
  - **Ranger:** Minor nature magic, tracking, animal companion, terrain mastery
  - **Bard:** Music-based magic, buffs/debuffs, charm, lore knowledge, inspiration
  - **Necromancer:** Death magic, raise undead, drain life, speak with dead, soul manipulation
  - **Alchemist:** Potion/bomb crafting, transmutation, material magic, no combat spells
  - **Shaman:** Spirit magic, ancestor communication, totems, tribal rituals
  - **Artificer:** Enchants objects, creates magic items, runic inscriptions
  - **Witch:** Hex/curse specialist, familiar companion, divination, folk magic
  - **Monk:** Ki-based abilities, body enhancement, not traditional magic but supernatural
  - Monsters have innate magic: dragons (breath weapons, fear aura), liches (necromancy), fey (illusion/charm)
- [ ] **Magical abilities and powers:**
  - Innate abilities: racial (elf darkvision, dwarf stonecunning, halfling luck)
  - Class abilities: rage (barbarian), sneak attack (rogue), divine sense (paladin)
  - Supernatural abilities: telepathy, telekinesis, precognition, astral projection
  - Magical crafting: scroll writing, wand making, golem creation, flying carpet weaving
  - Magical locations: ley lines (boost mana regen), dead zones (suppress magic), wild zones (random effects)
  - Magical creatures: familiars, golems, elementals, summoned beings
  - Cursed items: powerful but with drawbacks, soul-corrupting
  - Artifacts: unique world-changing items from history simulation (e.g., sword of the first king)
- [ ] **Magic-related jobs and economy:**
  - Enchanter: enchants weapons/armor/tools for a fee, needs workshop + reagents
  - Scroll scribe: copies spells onto scrolls, sells at market, needs ink + parchment
  - Wand maker: crafts wands/staves/rods, needs rare wood + gems + enchanting skill
  - Potion brewer: mass produces potions, needs alchemy lab + ingredients
  - Spellbook binder: creates blank spellbooks, valuable commodity
  - Court wizard: advises rulers, provides magical defense, paid by kingdom treasury
  - Battle mage: military role, casts combat spells in warfare, attached to armies
  - Healer mage: temple/hospital healer using divine magic, paid by temple
  - Hedge witch: rural magic, folk remedies + minor curses, distrusted but needed
  - Summoner: summons creatures for labor/combat, controversial profession
  - Diviner: predicts weather/events, consulted by rulers and farmers
  - Ward smith: creates magical protections for buildings/settlements
- [ ] **Magic equipment and items:**
  - Spellbooks (different quality/capacity, valuable loot)
  - Spell components (eye of newt, dragon scale, moonstone, etc. -- supply chain items)
  - Wands (limited charges, specific spell), staves (mana boost + spells), rods (permanent effects)
  - Enchanted weapons: flaming sword, frost axe, lightning spear, holy mace
  - Enchanted armor: fire resist plate, shadow leather, mithril chain, blessed shield
  - Rings/amulets: stat boost, protection, detection, invisibility
  - Potions: healing, mana, strength, speed, invisibility, flying, water breathing
  - Scrolls: one-use spell casts, can be used by non-mages
  - Magical tools: far-sight crystal, translation stone, map of revealing
  - Cursed items: appear beneficial but drain HP/mana/soul, hard to remove
  - Craft materials: mana crystals, enchanting dust, runestones, arcane ink

### 5.4 World Events & AI Storyteller
- [x] AI Storyteller (RimWorld-inspired): dramatic tension, event pacing
- [x] Major events: plague, famine, invasion, civil war
- [x] Festival/celebration events
- [ ] Historical chronicles (auto-generated history of this playthrough)

---

## Phase 6: Multiplayer & Social
**Goal:** Allow shared world experiences.

### 6.1 Core Multiplayer
- [x] TCP socket server embedded in host game
- [x] Client connection and state sync
- [x] Message protocol (JSON over TCP)
- [x] Remote player rendering
- [ ] Player-to-player trading
- [ ] Shared quest objectives
- [ ] PvP toggle with consent system

### 6.2 AI Co-Player (Claude-Driven)
- [x] AI player entity using same network protocol
- [x] Autonomous behaviors (explore, fight, trade)
- [x] Chat integration
- [ ] Claude Code session integration (launch AI player from CLI)
- [ ] Personality configuration
- [ ] Command system: give orders to AI companion

---

## Phase 7: Content Expansion (Long-term)
**Goal:** Massive variety and replayability.

### 7.1 Biomes & Geography
- [ ] Desert, tundra, volcanic, swamp, ocean biomes
- [ ] Underground cavern biome (massive cave systems)

### 7.2 Technology & Ages
- [ ] Bronze -> Iron -> Medieval -> Renaissance progression
- [ ] Architecture changes with tech level

### 7.3 Procedural Dungeons
- [ ] Multi-level dungeon generation with bosses, traps, loot
- [ ] Ancient ruins from history simulation as dungeon seeds

### 7.4 Naval & Exploration
- [ ] Ship building, sea trade, naval combat
- [ ] Uncharted islands, fishing, sea monsters

### 7.5 Music & Sound
- [ ] Procedural ambient music by biome/time/mood
- [ ] Environmental sounds, NPC voice barks

---

## Phase 8: Distribution & Community (Aspirational)

### 8.1 Packaging
- [ ] PyInstaller/Nuitka executable for Windows/Mac/Linux
- [ ] Steam integration (achievements, cloud saves)
- [ ] Mod support (plugin system)

### 8.2 Modding API
- [ ] Python scripting for mods
- [ ] Custom content definitions
- [ ] Tileset/sprite replacement

---

## Architecture Principles

### What Makes This Game Special
1. **Living world** -- NPCs have real jobs, income, needs, emotions. Goods physically move. Prices reflect supply/demand.
2. **Emotional depth** -- Plutchik's wheel drives NPC behavior: love, grudges, rebellion, grief cascades.
3. **Souls & afterlife** -- A fixed soul pool creates meaning in death. Souls carry memories across lifetimes and games.
4. **Divine intelligence** -- AI-powered gods watch the world and occasionally intervene, competing for followers.
5. **Historical depth** -- 500-year simulated history. Darwinian inheritance shapes settlements over generations.
6. **Multiple perspectives** -- Play as mortal, ghost (see souls), or god.
7. **Meta-narrative** -- Gods petition the player for changes. The game's AI tells you what it wants.
8. **Emergent stories** -- Like Dwarf Fortress/RimWorld, but with emotional and metaphysical dimensions.

### Technical Constraints
- **Python/Pygame** -- Performance ceiling ~500 active entities at 60fps
- **Soul tracking** -- ~500 individually tracked souls; rest statistical
- **LLM dependency** -- God AI and deep NPC dialog need LLM; fallback to heuristics
- **Network: 2 players max** -- TCP sync

### Design Inspirations
- **Dwarf Fortress** -- Deep simulation, emergent stories, history generation
- **RimWorld** -- AI Storyteller, event pacing, character needs
- **Baldur's Gate** -- RPG mechanics, party system, dialog trees
- **The Sims** -- Need systems, social interactions, daily routines
- **Black & White** -- God simulation, divine intervention, prayer system
- **Planescape: Torment** -- Souls, reincarnation, memory persistence across death
- **Cultist Simulator** -- Occult systems, emotional drives, hidden knowledge

---

## Sprint Plan

### Sprint 1 (Current)
1. Verify all bug fixes in extended gameplay
2. Test graphics + multiplayer
3. Fix crashes

### Sprint 2 (Next)
1. Plutchik emotion system (Phase 2.1)
2. Emotion-driven behavior basics (Phase 2.2)
3. Day/night lighting

### Sprint 3 (Following)
1. Children & inheritance (Phase 2.3)
2. Soul system core (Phase 3.1)
3. Death & burial (Phase 3.2)

### Sprint 4
1. Undead & soul predation (Phase 3.3)
2. Reincarnation mechanics (Phase 3.4)
3. Churchyards & graves

### Sprint 5
1. God entities & AI (Phase 4.1)
2. Prayer & miracles (Phase 4.2)
3. Divine competition (Phase 4.4)

---

## Session Log

- **Sessions 1-8:** Built core game -- world gen, NPCs, combat, economy, governance, warfare, ecology, culture, technology, demographics, construction, performance optimization (52 modules, ~16,500 lines)
- **Session 9:** Massive expansion -- 10K chunked world, history simulation, 3D OpenGL renderer, underground layer, God Mode, Claude AI integration, parameter tweaker, live Python console, hot reload, visual effects system, multiplayer networking. 12 bug fixes. Graphics overhaul with 17 new effect systems. God mode restructured as floating panel. (129 modules, ~81,000 lines)
- **Session 10:** Metaphysical layer -- Plutchik emotions (8 primary + 8 secondary + Big Five personality + grudges/bonds), Children & Darwinian Inheritance (pregnancy, stat inheritance, parental care, coming of age), Soul System (500 tracked souls, echo memories, reincarnation, cross-species, persistence across games), Burial/Graves (12 churchyards, epitaphs, mourning), Undead & Soul Predation (7 types, soul drain, necromancers, consecrated zones, exorcism), God AI Pantheon (7 gods, prayer, 10 miracle types, petitions to Higher Power, divine competition). Day/night lighting with torch sources. (135 modules, ~86,000 lines)

---

*Last updated: March 17, 2026*
*Generated during development session with Claude Code*

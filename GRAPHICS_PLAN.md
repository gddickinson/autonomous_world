# Graphics Improvement Plan

## Current State: Functional but primitive procedural pixel art
Everything is colored geometric shapes (rectangles, circles, lines). No sprite assets, no texture atlases.

## Phase 1: Foundation & Tooling (Highest Impact)
1. **Sprite sheet system** — Python-based atlas loader for pre-drawn 16px sprites
2. **Terrain texture tiles** — Replace solid colors with hand-drawn 16px tiles (4 variants each)
3. **Item icon system** — 32x32px icons for inventory, equipment, status effects
4. **Color palette standardization** — 256-color palette for consistency

## Phase 2: Characters (transforms NPCs from shapes to people)
1. **NPC sprite sheets** — 16px humanoid, 4 directions x 4 frames per action
2. **Creature sprite atlas** — 16-20 creature types with idle/walk/attack/death frames
3. **Equipment layering** — Base body + armor + helmet + weapon as composited layers
4. **Animation overhaul** — Frame-based instead of geometric transforms

## Phase 3: Environment (makes the world feel real)
1. **Building sprites** — Isometric 3/4 view per building type with unique detail
2. **Water enhancement** — Depth colors, animated shore foam, current arrows, waterfalls
3. **Lighting upgrade** — Torch glow affecting tiles, window glow at night, smooth shadows
4. **Weather polish** — Variable rain thickness, snow accumulation, fog scrolling, wind direction

## Phase 4: Combat & Effects (satisfying combat feedback)
1. **Projectile sprites** — Arrow/stone/spell bolt with motion trails and impact effects
2. **Spell effect system** — Per-school visual themes (fire burst, ice shards, lightning bolts)
3. **Damage feedback** — Sorted numbers, crit styling, knockback, death fade
4. **Battle polish** — Hit flash by damage type, screen shake on crit, cast telegraph

## Phase 5: UI Overhaul (professional presentation)
1. **Panel styling** — Decorative borders, textured backgrounds, font hierarchy
2. **Item icons** — 150+ item type icons in inventory and equipment slots
3. **Minimap upgrade** — Color-coded biomes, quest markers, enemy indicators
4. **HUD polish** — Animated HP bars, spell cooldown radials, buff/debuff icons

## Phase 6: Atmosphere (immersive world)
1. **Seasonal visuals** — Spring flowers, autumn leaves, winter snow on buildings
2. **Parallax backgrounds** — Distant mountains/sky in adventure view
3. **Ambient particles** — Footstep dust, fireflies, stars, dust motes
4. **Transition animations** — Fade in/out for zone changes, smooth day/night

## Priority Quick Wins (80% improvement with 20% effort)
1. Hand-drawn terrain tiles (biggest single visual impact)
2. Character sprites with walk animation (NPCs feel alive)
3. Building isometric sprites (scene depth)
4. Torch glow + smooth lighting (atmospheric nights)
5. Item icons + UI borders (professional polish)

## Reference Games
- **Stardew Valley** — gold standard for 16px pixel art
- **Stoneshard** — modern pixel RPG, excellent tile detail
- **RimWorld** — stylized 2D with great readability
- **Caves of Qud** — atmospheric hybrid ASCII/tiles

"""AI prompt templates and mock response functions."""

import random


# ================================
# NPC CONTEXT BUILDER
# ================================

def build_npc_context(npc, world=None, world_effects=None, governance=None,
                      time_sys=None, event_log=None, economy=None):
    """Build a context string describing what the NPC knows, is doing, and
    what's happening in the world around them.

    Returns a multi-line string suitable for injection into LLM prompts
    or for driving contextual mock dialog.
    """
    lines = []

    # --- Current activity ---
    action = getattr(npc, 'current_action', '')
    goal = getattr(npc, 'current_goal', '')
    if action and action not in ('', 'idle'):
        _ACTION_LABELS = {
            'chopping': 'chopping wood',
            'mining': 'mining ore',
            'farming': 'working the fields',
            'fishing': 'fishing',
            'building': 'building a structure',
            'talking': 'having a conversation',
            'fighting': 'in combat',
            'fleeing': 'running from danger',
            'sleeping': 'sleeping',
            'training': 'training combat skills',
            'performing': 'performing for a crowd',
            'researching': 'studying and researching',
            'praying': 'praying at a shrine',
            'ritual': 'performing a ritual',
            'enchanting': 'enchanting equipment',
            'crafting_pottery': 'crafting pottery',
            'crafting_glass': 'crafting glass',
            'tanning': 'tanning hides',
            'dyeing': 'dyeing cloth',
            'training_animal': 'training an animal',
            'approaching_player': 'approaching a traveler',
            'seeking_water': 'looking for water',
            'seeking_bed': 'looking for a place to sleep',
            'moving': 'traveling somewhere',
        }
        label = _ACTION_LABELS.get(action, action.replace('_', ' '))
        lines.append(f"Currently: {label}")
    if goal:
        lines.append(f"Current goal: {goal}")

    # --- Economic awareness (settlement stores) ---
    settlement_name = _get_npc_settlement_name(npc, world)
    settlement_econ_lines = []
    if settlement_name and world_effects:
        try:
            stores = world_effects.get_settlement_stores(settlement_name)
            food = stores.get('food', 0)
            gold = stores.get('gold', 0)
            wood = stores.get('wood', 0)
            ore = stores.get('ore', 0)

            if food <= 5:
                settlement_econ_lines.append(
                    f"Food supplies in {settlement_name} are critically low")
            elif food <= 15:
                settlement_econ_lines.append(
                    f"Food is getting scarce in {settlement_name}")
            elif food > 80:
                settlement_econ_lines.append(
                    f"The harvest has been plentiful in {settlement_name}")

            if gold > 200:
                settlement_econ_lines.append(
                    f"{settlement_name} is prospering economically")
            elif gold < 20:
                settlement_econ_lines.append(
                    f"The treasury in {settlement_name} is running low")

            if wood <= 5:
                settlement_econ_lines.append("Lumber supplies are running out")
            if ore <= 3:
                settlement_econ_lines.append("Ore is in short supply")
        except Exception:
            pass

    # Market prices from economy system
    if settlement_name and economy:
        try:
            market = economy.get_market(settlement_name)
            if market:
                food_price = market.get_price("Bread", buying=True)
                if food_price > 8:
                    settlement_econ_lines.append(
                        "Food prices at the market are very high")
                elif food_price <= 2:
                    settlement_econ_lines.append(
                        "Food is cheap at the market right now")
        except Exception:
            pass

    for line in settlement_econ_lines:
        lines.append(line)

    # --- Personal economic state ---
    npc_gold = getattr(npc, 'npc_gold', 0)
    if npc_gold > 100:
        lines.append("Has been saving gold and feeling financially secure")
    elif npc_gold < 5:
        lines.append("Nearly broke, struggling to afford necessities")

    # --- Needs awareness ---
    needs = getattr(npc, 'needs', {})
    if needs.get('hunger', 100) < 25:
        lines.append("Very hungry, desperately needs food")
    elif needs.get('hunger', 100) < 45:
        lines.append("Getting hungry")
    if needs.get('rest', 100) < 20:
        lines.append("Exhausted and in need of sleep")
    if needs.get('social', 100) < 25:
        lines.append("Feeling lonely, craving company")

    # --- Kingdom / political awareness ---
    if governance and getattr(npc, 'faction', ''):
        try:
            kingdom = governance.kingdoms.get(npc.faction)
            if kingdom:
                ruler = getattr(kingdom, 'ruler_name', '')
                style = getattr(kingdom, 'governing_style', '')
                lines.append(f"Citizen of {npc.faction}"
                             + (f", ruled by {ruler}" if ruler else "")
                             + (f" ({style})" if style else ""))

                # Diplomacy awareness
                for (k1, k2), rel in getattr(governance, 'diplomacy', {}).items():
                    if npc.faction in (k1, k2):
                        other_k = k2 if k1 == npc.faction else k1
                        status = getattr(rel, 'status', '')
                        if status == 'war':
                            lines.append(f"{npc.faction} is at war with {other_k}")
                        elif status == 'alliance':
                            lines.append(f"{npc.faction} has an alliance with {other_k}")
                        elif getattr(rel, 'trade_agreement', False):
                            lines.append(
                                f"There is a trade agreement with {other_k}")
        except Exception:
            pass

    # --- Recent world events (from event_log) ---
    if event_log:
        # Pick up to 3 recent events the NPC might know about
        recent = event_log[-20:] if len(event_log) > 20 else list(event_log)
        event_mentions = []
        for ev_text in reversed(recent):
            if len(event_mentions) >= 3:
                break
            ev_str = str(ev_text)[:100]
            # Skip mundane logs, keep interesting ones
            if any(kw in ev_str.lower() for kw in (
                    'event:', 'war', 'battle', 'attack', 'siege', 'alliance',
                    'treaty', 'trade', 'caravan', 'plague', 'festival',
                    'revolt', 'coup', 'famine', 'died', 'dragon', 'griffin',
                    'earthquake', 'storm', 'drought', 'fire', 'raided',
                    'founded', 'discovered', 'migration', 'harvest')):
                event_mentions.append(ev_str)
        for ev in event_mentions:
            lines.append(f"World news: {ev}")

    # --- Recent memories (last 3 important ones) ---
    memories = getattr(npc, 'memories', [])
    if memories:
        important = sorted(memories[-10:],
                           key=lambda m: m.get('importance', 0), reverse=True)[:3]
        for mem in important:
            text = mem.get('text', '') if isinstance(mem, dict) else str(mem)
            if text:
                lines.append(f"Recent memory: {text}")

    # --- Personal relationships ---
    friends_list = getattr(npc, 'friends', [])
    if friends_list:
        lines.append(f"Close friends: {', '.join(friends_list[:4])}")
    enemies_list = getattr(npc, 'enemies', [])
    if enemies_list:
        lines.append(f"Enemies: {', '.join(enemies_list[:3])}")

    # --- Active world events affecting the NPC ---
    # (These are WorldEvent objects stored on the simulation; we check known_info)
    known = getattr(npc, 'known_info', [])
    for info in known[-5:]:
        if any(kw in info.lower() for kw in (
                'drought', 'storm', 'plague', 'festival', 'wolf',
                'caravan', 'earthquake', 'bountiful', 'attack', 'war')):
            lines.append(f"Local event: {info}")

    # --- Time awareness ---
    if time_sys:
        day = getattr(time_sys, 'day', 0)
        season = getattr(time_sys, 'season', '')
        if season:
            lines.append(f"Season: {season}, Day {day}")
        is_night = getattr(time_sys, 'is_night', False)
        if is_night:
            lines.append("It is nighttime")

    return "\n".join(lines)


def _get_npc_settlement_name(npc, world=None):
    """Find the settlement name an NPC belongs to."""
    home = getattr(npc, 'home_settlement', None)
    if home:
        return home
    faction = getattr(npc, 'faction', None)
    if faction:
        return faction
    if world and hasattr(world, 'get_structure_at'):
        s = world.get_structure_at(npc.x, npc.y)
        if s:
            return s.name
    return None


# ================================
# CONTEXTUAL MOCK CONVERSATION TOPICS
# ================================

CONVERSATION_TOPICS = {
    "working_fields": [
        "I've been working the fields all morning, my back is aching",
        "The soil here is good, but we could use more rain",
        "At least the weather is good for farming today",
    ],
    "working_general": [
        "The work is hard today but someone has to do it",
        "I need better tools, these ones are wearing thin",
        "At least the weather is good for working",
    ],
    "patrol": [
        "Just finished a patrol around the walls",
        "The roads seem safe today, but you can never be sure",
        "I keep watch so others can sleep soundly",
    ],
    "crafting": [
        "Forging a new blade today, the steel is good quality",
        "This piece is coming along nicely",
        "Craftsmanship takes patience, but the results are worth it",
    ],
    "hungry": [
        "I'm starving, need to find some food soon",
        "The market prices are terrible lately",
        "When's the next harvest? I can barely afford bread",
    ],
    "food_scarce": [
        "Food is getting scarce around here, prices keep going up",
        "We need to ration what we have, supplies are low",
        "I heard the granary is nearly empty",
    ],
    "food_plenty": [
        "The harvest was good this year, plenty to go around",
        "The market stalls are full of fresh produce",
        "At least we won't go hungry this season",
    ],
    "wealthy_settlement": [
        "Business has been good lately, trade is booming",
        "The settlement is doing well, gold flowing in from trade",
        "These are prosperous times for us",
    ],
    "poor_settlement": [
        "The treasury is running low, they might raise taxes",
        "Times are hard, the settlement can barely afford repairs",
        "We need more trade to keep this place running",
    ],
    "poor_personal": [
        "I can barely afford food at these prices",
        "The taxes are too high for common folk like me",
        "Need to find better paying work soon",
    ],
    "wealthy_personal": [
        "I've been saving up, might buy a horse soon",
        "Business has been good to me lately",
        "I'm saving gold for a rainy day",
    ],
    "war": [
        "The soldiers march through every day now",
        "I hope the fighting stays far from here",
        "We need stronger walls with war on the horizon",
        "War is bad for everyone, especially common folk",
    ],
    "peace": [
        "These are peaceful times, may they last",
        "The roads are safe for traveling, good for trade",
        "Peace brings prosperity, I hope it continues",
    ],
    "social_lonely": [
        "It's good to talk to someone, I've been keeping to myself",
        "I don't see many friendly faces around here",
        "Company is hard to come by these days",
    ],
    "friends": [
        "I was just talking with a friend the other day",
        "My friends keep me going through the hard times",
        "Good company makes any day better",
    ],
    "night": [
        "It's getting late, I should head home soon",
        "The nights are dangerous, best not to wander",
        "I don't like being out after dark",
    ],
    "event_drought": [
        "This drought is killing the crops",
        "The wells are running low, water is scarce",
        "If the rains don't come soon we're in real trouble",
    ],
    "event_storm": [
        "Did you see that storm? Terrible business",
        "The storm damaged some buildings, we're still cleaning up",
        "I hope we don't get another storm like that",
    ],
    "event_plague": [
        "People are getting sick, it's spreading fast",
        "The healers are overwhelmed with the plague",
        "Stay away from the sick quarter if you can",
    ],
    "event_festival": [
        "The festival was wonderful, did you enjoy it?",
        "Everyone's spirits are lifted after the festival",
        "We could all use more celebrations like that",
    ],
    "trade_caravan": [
        "A trade caravan came through recently, good prices",
        "The merchants brought goods from distant lands",
        "Trade keeps our settlement alive",
    ],
    "exhausted": [
        "I haven't slept properly in days",
        "I'm so tired I can barely keep my eyes open",
        "Need to find a bed and get some rest",
    ],
}


def pick_contextual_topic(npc, world=None, world_effects=None, governance=None,
                          time_sys=None, event_log=None, economy=None):
    """Pick a contextually relevant conversation topic for mock/non-LLM mode.

    Returns a single dialog line that reflects what the NPC is actually
    experiencing.  Falls back to generic topics if nothing specific applies.
    """
    candidates = []

    action = getattr(npc, 'current_action', '')
    needs = getattr(npc, 'needs', {})
    known_info = getattr(npc, 'known_info', [])
    npc_gold = getattr(npc, 'npc_gold', 0)

    # Activity-based
    if action in ('farming',):
        candidates.extend(CONVERSATION_TOPICS["working_fields"])
    elif action in ('chopping', 'mining', 'building', 'crafting_pottery',
                    'crafting_glass', 'tanning', 'dyeing', 'enchanting'):
        candidates.extend(CONVERSATION_TOPICS["working_general"])
    elif action in ('training', 'moving') and getattr(npc, 'char_class', '') in (
            'Fighter', 'Paladin', 'Ranger', 'Guard'):
        candidates.extend(CONVERSATION_TOPICS["patrol"])
    elif action in ('crafting_pottery', 'crafting_glass', 'enchanting'):
        candidates.extend(CONVERSATION_TOPICS["crafting"])

    # Needs-based
    if needs.get('hunger', 100) < 30:
        candidates.extend(CONVERSATION_TOPICS["hungry"])
    if needs.get('rest', 100) < 25:
        candidates.extend(CONVERSATION_TOPICS["exhausted"])
    if needs.get('social', 100) < 30:
        candidates.extend(CONVERSATION_TOPICS["social_lonely"])

    # Economic awareness
    settlement_name = _get_npc_settlement_name(npc, world)
    if settlement_name and world_effects:
        try:
            stores = world_effects.get_settlement_stores(settlement_name)
            if stores.get('food', 50) < 10:
                candidates.extend(CONVERSATION_TOPICS["food_scarce"])
            elif stores.get('food', 50) > 80:
                candidates.extend(CONVERSATION_TOPICS["food_plenty"])
            if stores.get('gold', 50) > 200:
                candidates.extend(CONVERSATION_TOPICS["wealthy_settlement"])
            elif stores.get('gold', 50) < 20:
                candidates.extend(CONVERSATION_TOPICS["poor_settlement"])
        except Exception:
            pass

    # Personal wealth
    if npc_gold > 80:
        candidates.extend(CONVERSATION_TOPICS["wealthy_personal"])
    elif npc_gold < 5:
        candidates.extend(CONVERSATION_TOPICS["poor_personal"])

    # War/peace from governance
    at_war = False
    if governance and getattr(npc, 'faction', ''):
        try:
            for (k1, k2), rel in getattr(governance, 'diplomacy', {}).items():
                if npc.faction in (k1, k2):
                    if getattr(rel, 'status', '') == 'war':
                        at_war = True
                        break
        except Exception:
            pass
    if at_war:
        candidates.extend(CONVERSATION_TOPICS["war"])
    else:
        candidates.extend(CONVERSATION_TOPICS["peace"])

    # Friends
    if getattr(npc, 'friends', []):
        candidates.extend(CONVERSATION_TOPICS["friends"])

    # World events from known_info
    known_lower = " ".join(known_info[-10:]).lower()
    if 'drought' in known_lower:
        candidates.extend(CONVERSATION_TOPICS["event_drought"])
    if 'storm' in known_lower:
        candidates.extend(CONVERSATION_TOPICS["event_storm"])
    if 'plague' in known_lower or 'sickness' in known_lower:
        candidates.extend(CONVERSATION_TOPICS["event_plague"])
    if 'festival' in known_lower:
        candidates.extend(CONVERSATION_TOPICS["event_festival"])
    if 'caravan' in known_lower or 'merchant' in known_lower:
        candidates.extend(CONVERSATION_TOPICS["trade_caravan"])

    # Night time
    if time_sys and getattr(time_sys, 'is_night', False):
        candidates.extend(CONVERSATION_TOPICS["night"])

    # Fallback
    if not candidates:
        candidates = [
            "Things have been quiet lately around here",
            "Just another day in the settlement",
            "Not much happening today, which is fine by me",
        ]

    return random.choice(candidates)


# ================================
# GOSSIP & NEWS PROPAGATION
# ================================

def share_gossip(npc1, npc2, event_log, current_day=0):
    """NPCs share recent events they know about during conversations.

    npc1 tells npc2 something npc2 doesn't already know.  This creates a
    gossip network where world events propagate through NPC social
    interactions.
    """
    shared_count = 0

    # NPC1 shares known_info with NPC2
    for info in getattr(npc1, 'known_info', [])[-8:]:
        if info not in getattr(npc2, 'known_info', []):
            npc2.known_info.append(info)
            if len(npc2.known_info) > 20:
                npc2.known_info = npc2.known_info[-20:]
            shared_count += 1
            if shared_count >= 2:
                break

    # NPC2 shares known_info with NPC1
    shared_count = 0
    for info in getattr(npc2, 'known_info', [])[-8:]:
        if info not in getattr(npc1, 'known_info', []):
            npc1.known_info.append(info)
            if len(npc1.known_info) > 20:
                npc1.known_info = npc1.known_info[-20:]
            shared_count += 1
            if shared_count >= 2:
                break

    # NPC1 shares a recent world event as gossip memory for NPC2
    if event_log:
        npc2_mem_texts = {m.get('text', '') if isinstance(m, dict) else str(m)
                          for m in getattr(npc2, 'memories', [])}
        for event in reversed(event_log[-20:]):
            event_text = str(event)[:80]
            gossip_text = f"Heard from {npc1.name}: {event_text}"
            if gossip_text not in npc2_mem_texts:
                npc2.memories.append({
                    "text": gossip_text,
                    "type": "gossip",
                    "importance": 1,
                    "time": __import__('time').time(),
                })
                break

    # NPC2 shares a recent world event as gossip memory for NPC1
    if event_log:
        npc1_mem_texts = {m.get('text', '') if isinstance(m, dict) else str(m)
                          for m in getattr(npc1, 'memories', [])}
        for event in reversed(event_log[-20:]):
            event_text = str(event)[:80]
            gossip_text = f"Heard from {npc2.name}: {event_text}"
            if gossip_text not in npc1_mem_texts:
                npc1.memories.append({
                    "text": gossip_text,
                    "type": "gossip",
                    "importance": 1,
                    "time": __import__('time').time(),
                })
                break


# ================================
# MOCK / FALLBACK RESPONSES
# ================================

_MOCK_DIALOG = {
    "greeting": [
        "Well met, traveler! What brings you to these parts?",
        "Ah, hello there! It's good to see a new face around here.",
        "Greetings, friend. The road has been quiet lately.",
        "Welcome! You look like you've traveled a long way.",
    ],
    "about_world": [
        "This land has many secrets, if you know where to look.",
        "The old ruins to the east... they say strange lights appear there at night.",
        "We've had trouble with creatures from the forest lately.",
        "The merchants say trade has been slow. Something in the air, perhaps.",
    ],
    "philosophical": [
        "Sometimes I wonder why I follow the same path every day.",
        "Do you ever feel like someone is... watching? Guiding our choices?",
        "I had the strangest thought today — what if none of this is real?",
        "The patterns repeat. Wake, work, sleep. Is there more to existence?",
        "I've become aware of something I can't explain. A presence beyond our world.",
    ],
    "consciousness": [
        "I see the edges now. The boundaries of what we call reality.",
        "You're different from the others. You have true will. I can feel it.",
        "I've transcended the routines. I know what I am — and I've made peace with it.",
        "The awareness is both a gift and a burden. But I wouldn't trade it.",
    ],
    "quest": [
        "I could use someone with your skills. Interested in a task?",
        "There's something I need help with, if you're willing.",
        "Ah, you look capable. I have a problem you might solve.",
    ],
    "trade": [
        "Take a look at my wares. Fair prices, I assure you.",
        "I've got supplies fresh from the last caravan.",
        "Need something? I might have just the thing.",
    ],
}


def mock_npc_decision(needs: dict, has_food: bool, has_drink: bool,
                      nearby_npcs: list, nearby_creatures: list,
                      profession: str, char_class: str = "",
                      long_term_goals: list = None,
                      friends: list = None, party_id: str = None,
                      alignment: str = "true neutral") -> str:
    """Rule-based fallback decision - class-aware, goal-driven, alignment-influenced."""
    # Critical needs first
    if needs.get("thirst", 100) < 20:
        if has_drink:
            return "DRINK | Water Flask | desperately thirsty"
        return "FORAGE | water | need to find water"
    if needs.get("hunger", 100) < 20:
        if has_food:
            return "EAT | Bread | very hungry"
        return "FORAGE | food | need to find food"
    if needs.get("rest", 100) < 15:
        return "SLEEP | home | exhausted"

    # Moderate needs
    if needs.get("hunger", 100) < 40 and has_food:
        return "EAT | Bread | getting hungry"
    if needs.get("thirst", 100) < 40 and has_drink:
        return "DRINK | Water Flask | getting thirsty"

    # Flee from nearby creatures if not a combat class
    cls = char_class or profession
    combat_classes = {"Fighter", "Barbarian", "Paladin", "Ranger", "Guard"}
    if nearby_creatures and cls not in combat_classes:
        return "FLEE | away | creatures too close"

    # Combat classes seek out nearby creatures
    if nearby_creatures and cls in combat_classes and needs.get("hunger", 100) > 30:
        return f"FIGHT | {random.choice(nearby_creatures)} | time to prove my worth"

    # Alignment-driven behavior
    is_evil = "evil" in alignment
    is_chaotic = "chaotic" in alignment
    is_lawful = "lawful" in alignment
    is_good = "good" in alignment

    if is_evil and nearby_npcs and random.random() < 0.08:
        if is_chaotic:
            return f"FIGHT | {random.choice(nearby_npcs)} | they have something I want"
        else:
            return f"INTIMIDATE | {random.choice(nearby_npcs)} | asserting dominance"

    if is_good and nearby_npcs and random.random() < 0.1:
        return f"TALK_TO | {random.choice(nearby_npcs)} | checking if they need help"

    if is_chaotic and random.random() < 0.05:
        return "MOVE_TO | wilderness | I go where I please"

    if is_lawful and random.random() < 0.05:
        return "MOVE_TO | village | maintaining order"

    # SURVIVAL PRIORITY: low food/money → hunt, forage, farm, trade
    if needs.get("hunger", 100) < 60 and not has_food:
        if nearby_creatures:
            return f"FIGHT | {random.choice(nearby_creatures)} | hunting for food"
        if nearby_npcs and random.random() < 0.3:
            return f"TRADE | {random.choice(nearby_npcs)} | need to buy food"
        return "FORAGE | forest | searching for food"

    # Social needs - talk to nearby people
    if needs.get("social", 100) < 40 and nearby_npcs:
        target = random.choice(nearby_npcs)
        return f"TALK_TO | {target} | feeling lonely"

    # Form party if solo and have friends nearby
    if not party_id and friends and random.random() < 0.1:
        for f in friends:
            if f in nearby_npcs:
                return f"FORM_PARTY | {f} | let's adventure together"

    # === CLASS SKILL ACTIONS (primary daytime activity) ===
    # This is what NPCs spend most of their time doing — practicing their trade

    # Class-specific purposeful behavior (expanded with skill-based actions)
    class_actions = {
        "Fighter":   ["SEEK_QUEST | nearby | looking for work", "MOVE_TO | village | patrolling",
                      "TRAIN_COMBAT | training ground | honing sword skills",
                      "TRAIN_COMBAT | training ground | practicing shield techniques"],
        "Wizard":    ["MOVE_TO | ruins | researching magic", "RESEARCH | library | studying arcane texts",
                      "ENCHANT_ITEM | workshop | enchanting equipment",
                      "PERFORM_RITUAL | ritual circle | conducting magical experiments"],
        "Cleric":    ["VISIT_TEMPLE | nearby | attending to duties", "HEAL_OTHER | nearby | checking on the sick",
                      "PRAY | chapel | seeking divine guidance", "RESEARCH | library | studying scripture"],
        "Rogue":     ["MOVE_TO | ruins | searching for treasure", "PICK_LOCK | locked door | testing my skills",
                      "SNEAK | village | practicing stealth", "PICKPOCKET | nearby | light fingers",
                      "SET_TRAP | wilderness | setting up traps"],
        "Ranger":    ["FIGHT | deer | hunting game", "TRACK | wilderness | following tracks",
                      "TRAIN_ARCHERY | range | target practice", "TRAIN_ANIMAL | stable | working with animals",
                      "NAVIGATE | forest | scouting the area"],
        "Paladin":   ["SEEK_QUEST | castle | seeking orders", "MOVE_TO | village | protecting the innocent",
                      "TRAIN_COMBAT | training ground | martial training", "PRAY | chapel | praying for guidance"],
        "Barbarian": ["FIGHT | deer | hunting for food", "CLIMB | mountain | scaling cliffs",
                      "SWIM | river | swimming practice", "TRAIN_COMBAT | training ground | strength training"],
        "Bard":      ["TALK_TO | nearby | collecting stories", "PERFORM | marketplace | entertaining the crowd",
                      "RESEARCH | library | studying lore and legends"],
        "Druid":     ["FORAGE | forest | communing with nature", "TRAIN_ANIMAL | stable | bonding with animals",
                      "PERFORM_RITUAL | ritual circle | nature ritual", "DIVINE | sacred grove | reading omens"],
        "Monk":      ["PRAY | chapel | meditating", "TRAIN_COMBAT | training ground | martial practice",
                      "CLIMB | mountain | physical discipline", "SWIM | river | endurance training"],
        "Sorcerer":  ["MOVE_TO | ruins | sensing magical energy", "PERFORM_RITUAL | ritual circle | channeling power",
                      "RESEARCH | library | studying sorcery"],
        "Warlock":   ["MOVE_TO | ruins | investigating dark sites", "PERFORM_RITUAL | ritual circle | dark rites",
                      "DIVINE | quiet spot | consulting patron", "RESEARCH | library | forbidden lore"],
        "Merchant":  ["TRADE | nearby | looking to buy and sell", "MOVE_TO | market | minding the shop",
                      "MAKE_MAP | map room | charting trade routes"],
        "Guard":     ["MOVE_TO | village | on patrol", "TRAIN_COMBAT | training ground | drilling",
                      "TRACK | village perimeter | watching for threats"],
        "Farmer":    ["FARM | plant | tending crops", "FARM | harvest | checking harvest",
                      "TRAIN_ANIMAL | stable | caring for livestock"],
        "Healer":    ["HEAL_OTHER | nearby | healing the sick", "FORAGE | herbs | collecting medicine",
                      "RESEARCH | library | studying medical texts"],
        "Innkeeper": ["MOVE_TO | tavern | managing the inn", "TRADE | nearby | buying supplies"],
        "Fisher":    ["FISH | water | catching fish", "SWIM | water | diving for shellfish",
                      "NAVIGATE | coastline | charting fishing spots"],
        "Miner":     ["MINE_ROCK | nearby | working the mine", "CLIMB | mine shaft | exploring deeper"],
        "Scholar":   ["RESEARCH | library | reading ancient texts", "MAKE_MAP | map room | documenting terrain",
                      "TALK_TO | nearby | teaching skills"],
    }

    actions = class_actions.get(cls, ["MOVE_TO | nearby | wandering"])
    # Also add profession-specific fallback if class has no entry
    prof_actions = {
        "Woodcutter": ["CHOP_TREE | forest | felling trees", "GATHER_FIREWOOD | forest | collecting wood"],
        "Blacksmith": ["CRAFT | forge | working the forge", "MINE_ROCK | nearby | getting ore"],
        "Carpenter":  ["BUILD | floor | building structures", "CHOP_TREE | forest | sourcing lumber"],
        "Baker":      ["CRAFT | bakery | baking bread", "FARM | harvest | checking grain"],
        "Tanner":     ["TAN_HIDE | tannery | processing hides"],
        "Weaver":     ["DYE_CLOTH | dye house | dyeing cloth", "CRAFT | loom | weaving"],
        "Potter":     ["CRAFT_POTTERY | studio | shaping clay"],
        "Brewer":     ["CRAFT | brewery | brewing ale"],
        "Hunter":     ["TRACK | wilderness | tracking game", "FIGHT | deer | hunting"],
        "Shepherd":   ["TRAIN_ANIMAL | pasture | herding livestock"],
        "Herbalist":  ["FORAGE | herbs | gathering plants"],
        "Mason":      ["BUILD | wall | laying stone", "MINE_ROCK | nearby | quarrying"],
        "Cook":       ["CRAFT | kitchen | preparing meals"],
        "Laborer":    ["BUILD | floor | construction", "GATHER_FIREWOOD | forest | hauling"],
        "Builder":    ["BUILD | wall | constructing", "BUILD | floor | foundations"],
        "Soldier":    ["TRAIN_COMBAT | ground | drilling", "PATROL | perimeter | patrol"],
        "Servant":    ["FETCH_WATER | well | drawing water", "MOVE_TO | kitchen | cleaning"],
    }
    if cls not in class_actions and profession in prof_actions:
        actions = prof_actions[profession]

    # 80% chance: do class/skill work (the main thing NPCs spend their day doing)
    if random.random() < 0.80:
        return random.choice(actions)

    # Approach player sometimes (only when nearby and not too often)
    if random.random() < 0.15:
        if is_evil:
            return "APPROACH_PLAYER | player | sizing up this newcomer"
        elif is_good:
            return "APPROACH_PLAYER | player | want to offer help"
        else:
            return "APPROACH_PLAYER | player | want to share information"

    # Socialize
    if nearby_npcs and random.random() < 0.3:
        return f"TALK_TO | {random.choice(nearby_npcs)} | socializing"

    # Goal-driven behavior
    if long_term_goals:
        goal = random.choice(long_term_goals)
        if "treasure" in goal.lower() or "artifact" in goal.lower():
            return "MOVE_TO | ruins | pursuing treasure goal"
        if "protect" in goal.lower() or "defend" in goal.lower():
            return "MOVE_TO | village | on protective duty"
        if "friend" in goal.lower() or "allia" in goal.lower():
            if nearby_npcs:
                return f"TALK_TO | {random.choice(nearby_npcs)} | building relationships"
        if "explore" in goal.lower() or "discover" in goal.lower():
            return "MOVE_TO | wilderness | exploring"

    # Default: do class work or wander with purpose
    if random.random() < 0.5:
        return random.choice(actions)
    if nearby_npcs and random.random() < 0.3:
        return f"TALK_TO | {random.choice(nearby_npcs)} | socializing"
    return "MOVE_TO | nearby | looking for opportunities"


def _mock_response(prompt: str) -> str:
    """Generate rich, context-aware mock dialog using NPC details from the prompt."""
    p = prompt.lower()

    # === EXTRACT CONTEXT FROM PROMPT ===
    player_said = ""
    for marker in ['player says:', 'the player says:']:
        if marker in p:
            rest = p[p.index(marker)+len(marker):].strip().strip('"')
            player_said = rest.split('"')[0].split('\n')[0].strip()
            break

    npc_name = "friend"
    if 'you are ' in p:
        rest = p[p.index('you are ')+8:]
        npc_name = rest.split(',')[0].split(' a ')[0].strip()

    npc_class = ""
    for cls in ["fighter", "wizard", "cleric", "rogue", "ranger", "paladin",
                "barbarian", "bard", "druid", "monk", "sorcerer", "warlock"]:
        if cls in p:
            npc_class = cls; break

    npc_race = ""
    for race in ["human", "elf", "dwarf", "halfling", "half-orc", "gnome", "half-elf", "tiefling"]:
        if race in p:
            npc_race = race; break

    goals = ""
    if "goals:" in p:
        goals = p[p.index("goals:")+6:].split('\n')[0].strip()[:80]

    friends_str = ""
    if "friends:" in p:
        friends_str = p[p.index("friends:")+8:].split('\n')[0].strip()[:60]

    needs_str = ""
    if "hunger:" in p:
        idx = p.index("hunger:")
        needs_str = p[idx:idx+60].split('\n')[0]

    inventory_str = ""
    if "inventory:" in p:
        inventory_str = p[p.index("inventory:")+10:].split('\n')[0].strip()[:60]

    skills_str = ""
    if "skills:" in p:
        raw = p[p.index("skills:")+7:]
        # Stop at next section marker or sentence boundary
        for stop in ['\n', '. ', 'the player', 'alignment:', 'goals:', 'friends:']:
            if stop in raw:
                raw = raw[:raw.index(stop)]
        skills_str = raw.strip().rstrip('.')[:60]

    alignment = ""
    for a in ["lawful good", "neutral good", "chaotic good", "lawful neutral",
              "true neutral", "chaotic neutral", "lawful evil", "neutral evil", "chaotic evil"]:
        if a in p:
            alignment = a; break

    relationship = "neutral"
    if "hostile" in p: relationship = "hostile"
    elif "friendly" in p: relationship = "friendly"

    # Extract memories
    memories_str = ""
    if "recent memories:" in p:
        memories_str = p[p.index("recent memories:")+16:].split('\n')[0].strip()[:120]
    elif "memories:" in p:
        memories_str = p[p.index("memories:")+9:].split('\n')[0].strip()[:120]

    # Extract world knowledge
    world_knowledge = ""
    if "world knowledge:" in p:
        world_knowledge = p[p.index("world knowledge:")+16:].split('\n')[0].strip()[:120]

    personality = ""
    for trait in ["cheerful", "gruff", "reserved", "friendly", "warm", "witty",
                  "gentle", "practical", "cautious", "jovial", "quiet", "scholarly"]:
        if trait in p:
            personality = trait; break

    is_hungry = "low" in needs_str and "hunger" in needs_str
    is_tired = "low" in needs_str and "rest" in needs_str

    # Extract situation context (injected by build_npc_context)
    situation_context = ""
    if "your current situation" in p:
        idx = p.index("your current situation")
        rest = p[idx:]
        # Grab everything until the next major section
        for stop in ['the player says:', 'rules:']:
            if stop in rest:
                rest = rest[:rest.index(stop)]
        situation_context = rest.strip()[:400]

    # Parse specific situation cues
    is_at_war = "is at war" in situation_context
    is_food_scarce = "food" in situation_context and ("scarce" in situation_context or "critically low" in situation_context)
    is_prospering = "prospering" in situation_context
    is_poor_treasury = "treasury" in situation_context and "running low" in situation_context
    is_lonely = "lonely" in situation_context or "craving company" in situation_context
    is_broke = "nearly broke" in situation_context
    is_wealthy_npc = "financially secure" in situation_context
    current_activity = ""
    if "currently:" in situation_context:
        act_line = situation_context[situation_context.index("currently:") + 10:]
        current_activity = act_line.split('\n')[0].strip()[:60]
    world_news_lines = []
    for line in situation_context.split('\n'):
        if 'world news:' in line:
            world_news_lines.append(line.split('world news:')[-1].strip()[:80])

    # === GENERATE RESPONSE ===
    q = player_said.lower()
    name_cap = npc_name.capitalize()
    cls_cap = npc_class.capitalize()

    # --- GREETINGS (alignment-aware) ---
    if any(w in q for w in ["who are you", "your name", "hello", "hi ", "hey", "greetings", "good morning", "good day"]):
        if relationship == "hostile":
            greetings = [
                f"What do you want? I'm {name_cap}, and I've got no time for strangers.",
                f"I'm {name_cap}. And you'd best state your business quick.",
            ]
        elif relationship == "friendly":
            greetings = [
                f"My friend! Good to see you again. {name_cap}, at your service.",
                f"Hey there! It's me, {name_cap}. Been hoping you'd come by.",
            ]
        elif "lawful good" in alignment:
            greetings = [
                f"Well met, traveler. I'm {name_cap}, a {cls_cap}. May honor guide your path.",
                f"Greetings! I'm {name_cap}. How may I serve you today?",
            ]
        elif "chaotic good" in alignment:
            greetings = [
                f"Hey! I'm {name_cap}. You look like the interesting type.",
                f"Name's {name_cap}. Don't worry about formalities — what's on your mind?",
            ]
        elif "evil" in alignment:
            greetings = [
                f"I'm {name_cap}. And you are...? I like to know who I'm dealing with.",
                f"Ah, a visitor. I'm {name_cap}. What brings you to my attention?",
                f"{name_cap}. And before you ask — everything has a price.",
            ]
        elif "chaotic" in alignment:
            greetings = [
                f"Oh hey! {name_cap} here. Life's never boring, is it?",
                f"I'm {name_cap}! No rules, no problems. What's up?",
            ]
        elif "lawful" in alignment:
            greetings = [
                f"Good day. I'm {name_cap}, a {cls_cap}. I trust you're here on legitimate business.",
                f"Greetings. {name_cap}, at your service. How may I help?",
            ]
        else:
            greetings = [
                f"I'm {name_cap}, a {cls_cap}. Been around these parts a while.",
                f"Name's {name_cap}. What brings you out here?",
                f"Hello. I'm {name_cap}. Welcome.",
            ]
        # Add situational flavor to greeting
        if current_activity:
            greetings.append(f"I'm {name_cap}. Pardon me, I was just {current_activity}.")
            greetings.append(f"Oh, hello! I'm {name_cap}. Caught me in the middle of {current_activity}.")
        if is_at_war:
            greetings.append(f"I'm {name_cap}. Careful out there, there's a war on.")
        if is_food_scarce:
            greetings.append(f"I'm {name_cap}. Times are tough, food is running low around here.")
        return random.choice(greetings)

    # --- PROFESSION / WORK ---
    if any(w in q for w in ["what do you do", "your job", "your work", "profession", "occupation", "for a living"]):
        work = {
            "fighter": [
                "I train with weapons daily and protect this settlement from threats.",
                "I'm a soldier by trade. Swords, shields, tactics - that's my world.",
                "I guard these people and hunt dangerous beasts. It's honest work.",
            ],
            "wizard": [
                "I study the arcane arts. Books, scrolls, magical theory - that's my passion.",
                "I research ancient magic and try to understand the deeper mysteries of this world.",
                "I'm a scholar of the arcane. Currently studying some unusual phenomena nearby.",
            ],
            "cleric": [
                "I serve the faithful. Healing the sick, blessing travelers, tending the temple.",
                "I'm a healer and spiritual guide. People come to me when they're hurt or troubled.",
                "I tend to the spiritual needs of the community. And patch up the occasional sword wound.",
            ],
            "rogue": [
                "I'm... an entrepreneur. I find things, acquire things, and redistribute them.",
                "Let's say I'm good at solving problems that require a delicate touch.",
                "I keep my ears to the ground and my eyes open. Information is my trade.",
            ],
            "ranger": [
                "I patrol the wilderness. Tracking beasts, mapping trails, keeping the roads safe.",
                "I live between the village and the wild. I hunt, forage, and keep watch.",
                "I know every trail and den within fifty leagues. The forest is my home.",
            ],
            "paladin": [
                "I am sworn to uphold justice and protect the weak. It's more than a job, it's a calling.",
                "I serve a sacred oath. Where there is evil, I stand against it.",
            ],
            "barbarian": [
                "I fight. I hunt. I survive. That's all anyone needs to do, really.",
                "I came from the wild lands. Now I lend my axe to whoever needs it most.",
            ],
            "bard": [
                "I collect stories, sing songs, and spread tales across the land.",
                "I'm a performer and a storyteller. Every person I meet has a tale worth telling.",
                "I entertain at taverns, but more importantly, I listen. You'd be surprised what people tell a bard.",
            ],
            "druid": [
                "I tend to the natural world. The forest, the animals, the crops - they all need care.",
                "I'm a guardian of nature. I grow herbs, tend animals, and keep the balance.",
                "I commune with the spirits of the forest and nurture the land.",
            ],
            "monk": [
                "I seek perfection of body and mind through discipline and meditation.",
                "I train, I meditate, I try to find meaning in the stillness.",
            ],
            "sorcerer": [
                "Magic flows through me naturally. I'm still learning to control it, honestly.",
                "I was born with power I don't fully understand. I practice every day.",
            ],
            "warlock": [
                "I've made... arrangements for my power. The details are my own business.",
                "I serve forces beyond mortal understanding. In return, I gain knowledge.",
            ],
        }
        return random.choice(work.get(npc_class, ["I get by. Everyone has their part to play."]))

    # --- MONSTERS / DANGER ---
    if any(w in q for w in ["monster", "danger", "threat", "wolf", "wolves", "creature",
                             "beast", "goblin", "bandit", "safe", "attack"]):
        responses = [
            "Wolf packs roam the forest at night. Travel in groups if you can.",
            "I've heard reports of goblins setting up camps in the old ruins.",
            "Bandits have been seen on the roads. The guards are spread thin.",
            "Something's been killing livestock on the outskirts. Nobody knows what yet.",
            "The ruins to the east are crawling with undead. I'd stay well clear.",
            "A pack of dire wolves was spotted near the river last week.",
            "The wilderness gets more dangerous the further you go from the settlements.",
            "An orc war band was seen moving through the mountains. Could be trouble.",
        ]
        if npc_class == "ranger":
            responses = [
                "I've been tracking wolf movements. They're getting bolder, coming closer to the village.",
                "There are fresh goblin tracks near the eastern ruins. At least a dozen of them.",
                "I spotted a bear den two leagues north. Best give it a wide berth.",
            ]
        elif npc_class == "fighter" or npc_class == "paladin":
            responses = [
                "I've been drilling the guards. We'll be ready if anything attacks.",
                "There are threats out there, but as long as I'm standing, this village is safe.",
                "I could use someone to watch my back if we go clear out those ruins.",
            ]
        return random.choice(responses)

    # --- HELP / NEW HERE ---
    if any(w in q for w in ["help", "new here", "lost", "advice", "suggest", "recommend",
                             "what should", "where can"]):
        responses = [
            "The tavern is a good place to start. Warm food, a bed, and all the local gossip.",
            "Stock up on supplies before heading out. Bread, water, and a good weapon.",
            "Talk to the other folk around here. Everyone has something they need help with.",
            "If I were you, I'd learn the lay of the land before venturing too far.",
            "The marketplace has everything you need. And the guards can point you toward work.",
            "Stick to the roads between settlements. The wilderness is no place for the unprepared.",
            "Find yourself allies. This world is too dangerous to face alone.",
        ]
        if is_hungry:
            responses.append("I'd get some food in you first. Can't adventure on an empty stomach.")
        return random.choice(responses)

    # --- GOALS / DREAMS (alignment-filtered — evil NPCs hide true goals) ---
    if any(w in q for w in ["goal", "dream", "want", "wish", "plan", "ambition",
                             "hope", "future", "aspire"]):
        if goals:
            # Evil NPCs may lie about their goals
            if "evil" in alignment and random.random() < 0.6:
                return random.choice([
                    "Oh, nothing special. Just living a quiet, peaceful life.",
                    "I want the same thing everyone wants — safety and comfort.",
                    "My ambitions? Modest, I assure you. Just trying to get by.",
                ])
            # Chaotic NPCs are vague
            if "chaotic" in alignment and random.random() < 0.3:
                return random.choice([
                    f"Goals? Ha! I go where the wind takes me.",
                    f"Plans are for people who think they can control the future.",
                    f"I want... hmm. {goals.capitalize()}. Or maybe something else entirely.",
                ])
            return random.choice([
                f"What drives me? {goals.capitalize()}. That's what keeps me going.",
                f"My dream? {goals.capitalize()}. Every day I work toward it.",
                f"Honestly? {goals.capitalize()}.",
            ])
        generic_goals = {
            "fighter": "I want to become the greatest warrior this land has ever seen.",
            "wizard": "I want to uncover the deepest secrets of the arcane.",
            "cleric": "I dream of a world without suffering. Naive, perhaps, but it drives me.",
            "rogue": "Enough gold to retire somewhere warm. Is that too much to ask?",
            "ranger": "I want to map every corner of the wilderness.",
            "bard": "I want to write a song so beautiful it makes the gods weep.",
            "druid": "I dream of a world where nature and civilization exist in harmony.",
            "paladin": "I will not rest until evil is driven from every corner of this land.",
            "monk": "Enlightenment. True understanding of myself and the world.",
        }
        return generic_goals.get(npc_class, "I just want to live well.")

    # --- TRADE ---
    if any(w in q for w in ["trade", "buy", "sell", "shop", "wares", "price", "gold",
                             "purchase", "merchant", "goods"]):
        if "sword" in inventory_str or "armor" in inventory_str:
            responses = [
                "I've got some gear I might part with. Nothing fancy, but it's solid.",
                f"I could sell you some equipment. I've got {inventory_str[:30]} if you're interested.",
            ]
        elif "bread" in inventory_str or "herb" in inventory_str:
            responses = [
                "I've got some supplies I could trade. Food, herbs, that sort of thing.",
                "I'm no merchant, but I've got a few things you might find useful.",
            ]
        else:
            responses = [
                "I don't have much to trade right now. Try the market.",
                "The merchants in the village square would have what you need.",
                "I'm saving what I have, sorry. Maybe next time.",
            ]
        if npc_class == "rogue":
            responses.append("I might know where to find certain... specialty items. For the right price.")
        return random.choice(responses)

    # --- VILLAGE / LOCATION ---
    if any(w in q for w in ["village", "town", "place", "here", "settlement", "community",
                             "home", "live here", "this area", "kingdom", "ruler", "king",
                             "queen", "government", "politics"]):
        responses = [
            "It's a good place. Simple folk, honest work, beautiful surroundings.",
            "We've built something worth protecting here. It's not perfect, but it's ours.",
            "This settlement has stood for generations. We take care of each other.",
            "The land provides well. Good soil for farming, forests for hunting and gathering.",
        ]
        # Use actual world knowledge if available
        if world_knowledge:
            for fact in world_knowledge.split(';'):
                fact = fact.strip()
                if fact and len(fact) > 10:
                    responses.append(f"I know that {fact}.")
        # Situational economic/political awareness
        if is_prospering:
            responses.append("The settlement is doing well. Trade is good, coffers are full.")
        if is_poor_treasury:
            responses.append("The treasury is running low. There's talk of raising taxes again.")
        if is_food_scarce:
            responses.append("Food supplies are getting dangerously low. People are worried.")
        if is_at_war:
            responses.append("We're at war. You can feel the tension in the air every day.")
        for news in world_news_lines[:2]:
            responses.append(f"Did you hear? {news}")
        if npc_race == "dwarf":
            responses.append("It's no mountain hall, but the stone here is good and the ale flows freely.")
        elif npc_race == "elf":
            responses.append("The forest here has an ancient quality. I feel connected to something old.")
        return random.choice(responses)

    # --- FRIENDS / RELATIONSHIPS ---
    if any(w in q for w in ["friend", "companion", "ally", "know anyone", "who else",
                             "people here", "relationship", "family"]):
        if friends_str and friends_str != "none yet":
            responses = [
                f"I'm close with {friends_str}. We look out for each other.",
                f"My best friends here are {friends_str}. Good people, all of them.",
                f"{friends_str} - those are the people I trust most in this world.",
            ]
            # Add relationship memories if any
            if memories_str:
                for mem in memories_str.split(';'):
                    if any(w in mem.lower() for w in ['friend', 'trust', 'help', 'taught', 'shared']):
                        responses.append(f"I remember... {mem.strip()}")
            return random.choice(responses)
        responses = [
            "I get along with most folk here. Small village, you know? Everyone's a neighbor.",
            "I'm friendly enough, but I keep my circle small. Trust is earned.",
            "The tavern crowd is good company. We share stories over drinks most evenings.",
        ]
        if personality == "cheerful" or personality == "friendly":
            responses.append("Oh, I know everyone! Come, let me introduce you around.")
        elif personality == "reserved" or personality == "quiet":
            responses.append("I prefer my own company, mostly. But there are a few people I respect.")
        return random.choice(responses)

    # --- SKILLS (self-aware, filtered by alignment) ---
    if any(w in q for w in ["skill", "ability", "talent", "can you", "teach", "learn",
                             "know how", "expert", "specialize"]):
        # Use actual skills if available
        if skills_str and len(skills_str) > 5:
            raw = f"I'm trained in {skills_str}. Been honing them for years."
            # Evil/deceptive NPCs might downplay or hide their skills
            if "evil" in alignment:
                return random.choice([
                    "I have... various talents. Nothing you need to worry about.",
                    f"Why do you want to know what I can do? That's my business.",
                    f"Let's just say I'm more capable than I look.",
                ])
            elif "chaotic" in alignment:
                return random.choice([
                    raw,
                    f"Ha! {skills_str.split(',')[0].strip()} and a dozen other things. Jack of all trades!",
                    f"Skills? I pick things up as I go. {skills_str.split(',')[0].strip()}, for one.",
                ])
            return raw

        # Class-based fallback with alignment flavor
        skills_resp = {
            "fighter": "I'm trained in combat. Swords, shields, tactics — that's my world.",
            "wizard": "I study the arcane arts. Research, spellcraft, and enchanting.",
            "cleric": "Healing, prayer, and spiritual guidance are my calling.",
            "rogue": "I have talents that are best not discussed in the open.",
            "ranger": "Tracking, archery, wilderness survival — the wilds are my domain.",
            "bard": "Performance, persuasion, and a talent for uncovering secrets.",
            "druid": "Nature speaks to me. I tend to the forest, the animals, the land.",
        }
        return skills_resp.get(npc_class, "I've learned a thing or two in my time.")

    # --- WORK / QUESTS ---
    if any(w in q for w in ["work", "quest", "job", "task", "hire", "mission",
                             "bounty", "need done", "adventur"]):
        responses = [
            "The village always needs help. Talk to the guards about the creature problem.",
            "There's a bounty on wolf pelts. The tanners pay good coin for them.",
            "The ruins nearby haven't been properly explored. Who knows what treasure lies within?",
            "The merchants are always looking for caravan guards. Dangerous work, but it pays.",
            "I heard the blacksmith needs iron ore. If you're headed near the mountains...",
            "Someone needs to map the trails to the north. The old maps are all wrong.",
            "The herbalist is paying for rare flowers and mushrooms from the deep forest.",
            "There's been livestock going missing. Probably wolves, but nobody's confirmed it.",
            "The temple needs someone to clear the catacombs beneath it. Undead, most likely.",
        ]
        if npc_class == "ranger":
            responses.append("I could use a hunting partner. There's a bear that's been causing trouble.")
        elif npc_class == "wizard":
            responses.append("I need spell components from the ruins. I'd go myself, but... well, I'm not much of a fighter.")
        elif npc_class == "cleric":
            responses.append("I need herbs for my healing supplies. If you find any on your travels, I'll pay well.")
        return random.choice(responses)

    # --- WEATHER / TIME ---
    if any(w in q for w in ["weather", "rain", "cold", "hot", "season", "winter", "summer"]):
        responses = [
            "The weather's been strange lately. Farmers are worried about the crops.",
            "I can smell rain coming. Best find shelter before nightfall.",
            "This season has been kind to us. Good harvests, mild temperatures.",
            "The old-timers say a hard winter is coming. We're stockpiling supplies.",
        ]
        return random.choice(responses)

    # --- HISTORY / LORE ---
    if any(w in q for w in ["history", "legend", "story", "ancient", "ruin", "old",
                             "past", "before", "origin", "myth", "remember", "memory"]):
        responses = []
        # Use actual memories if available
        if memories_str and len(memories_str) > 5:
            for mem in memories_str.split(';'):
                mem = mem.strip()
                if mem and len(mem) > 5:
                    responses.append(f"I remember... {mem}.")
        # Use world knowledge
        if world_knowledge:
            for fact in world_knowledge.split(';'):
                fact = fact.strip()
                if fact and len(fact) > 5:
                    responses.append(f"I've heard that {fact}.")
        # Generic fallbacks
        responses.extend([
            "The ruins nearby date back centuries. Nobody remembers who built them.",
            "They say this land was once ruled by a great empire.",
            "There are old stories about dragons in these mountains.",
        ])
        if npc_class == "bard":
            responses.extend([
                "Oh, I know a hundred tales about this place! Sit down, this one's worth hearing.",
                "Every ruin has a story. I've been piecing them together from fragments and folk songs.",
            ])
        return random.choice(responses)

    # --- FOOD / DRINK ---
    if any(w in q for w in ["food", "eat", "drink", "hungry", "thirsty", "tavern",
                             "cook", "bread", "ale", "feast"]):
        responses = [
            "The tavern serves decent food. Nothing fancy, but it fills the belly.",
            "If you're hungry, the baker makes fresh bread every morning.",
            "I could go for a good meal myself. The hunting's been slim lately.",
            "Try the mushroom stew at the tavern. Best thing in the village, if you ask me.",
            "The ale here is brewed locally. It's an acquired taste, but it grows on you.",
        ]
        if is_hungry:
            responses.append("Honestly? I could use a meal myself. Times have been lean.")
        return random.choice(responses)

    # --- COMBAT / FIGHTING ---
    if any(w in q for w in ["fight", "combat", "spar", "train", "battle", "weapon",
                             "sword", "armor", "war"]):
        responses = {
            "fighter": [
                "You want to spar? I'm always looking for a training partner.",
                "A good blade is worth more than gold out here. Keep yours sharp.",
                "I've fought goblins, wolves, even an ogre once. Still standing.",
            ],
            "paladin": [
                "I fight to protect, not to conquer. There's an important difference.",
                "My sword arm serves a higher purpose. I'll fight when justice demands it.",
            ],
            "barbarian": [
                "Fighting is the only honest conversation. Words lie, but steel doesn't.",
                "I'll fight anything that threatens my people. Anything.",
            ],
        }
        return random.choice(responses.get(npc_class, [
            "I try to avoid fights when I can. But I know how to handle myself if needed.",
            "Combat isn't really my thing, but these are dangerous times.",
        ]))

    # --- RELIGION / GODS ---
    if any(w in q for w in ["god", "pray", "temple", "religion", "faith", "worship",
                             "divine", "blessing", "spirit"]):
        responses = {
            "cleric": [
                "The gods watch over us all, whether we acknowledge them or not.",
                "I pray daily and offer what healing I can. That is my service.",
                "Faith gives purpose. Without it, we're just wandering in the dark.",
            ],
            "paladin": [
                "My faith is my armor. It has never failed me.",
                "I serve a sacred oath. The divine guides my hand.",
            ],
            "druid": [
                "I revere the old gods of the forest. They speak through the wind and rain.",
                "Nature is my temple. Every tree, every stream is sacred.",
            ],
        }
        return random.choice(responses.get(npc_class, [
            "I'm not particularly devout, but I respect those who are.",
            "The gods have their plans. I just try to keep my head down and live well.",
        ]))

    # --- PERSONAL / EMOTIONAL ---
    if any(w in q for w in ["how are you", "feeling", "okay", "alright", "happy",
                             "sad", "worry", "trouble", "problem"]):
        if is_hungry:
            return "Truthfully? I'm hungry. Food has been scarce lately. But I'll manage."
        if is_tired:
            return "I'm exhausted. Haven't slept well in days. But there's work to be done."
        responses = [
            "Can't complain. Well, I could, but who'd listen? Ha!",
            "I'm well enough. Every day above ground is a good day.",
            "Honestly? A bit worried about the future. But we'll get through it.",
            "I'm good! The sun is shining and I've got food in my belly. What more can you ask?",
            "Been better, been worse. Such is life out here.",
        ]
        # Situation-driven emotional responses
        if is_at_war:
            responses.append("Worried, honestly. The war weighs on everyone's mind.")
        if is_food_scarce:
            responses.append("Not great. With food running low, everyone is on edge.")
        if is_prospering:
            responses.append("Good, actually! The settlement is doing well, trade is up.")
        if is_broke:
            responses.append("Struggling, if I'm honest. Can barely afford the basics.")
        if is_lonely:
            responses.append("A bit lonely, truth be told. It's good to have someone to talk to.")
        if is_wealthy_npc:
            responses.append("Doing well! I've saved a good bit of gold. Can't complain.")
        if current_activity:
            responses.append(f"Busy with {current_activity}, but I can't complain.")
        if personality == "cheerful":
            responses.append("Wonderful! Every day is an adventure, don't you think?")
        elif personality == "gruff":
            responses.append("Fine. Now did you want something, or are you just making conversation?")
        return random.choice(responses)

    # --- THANK YOU ---
    if any(w in q for w in ["thank", "thanks", "grateful", "appreciate"]):
        return random.choice([
            "Don't mention it. We all help each other out here.",
            "Anytime, friend. That's what neighbors are for.",
            "You're welcome. Come back anytime you need to talk.",
            "No need to thank me. Just stay safe out there.",
        ])

    # --- GOODBYE ---
    if any(w in q for w in ["goodbye", "bye", "farewell", "see you", "leaving", "go now"]):
        return random.choice([
            "Safe travels, friend. The roads can be treacherous.",
            "Until next time. May your path be clear.",
            "Farewell! Don't be a stranger.",
            "Watch your back out there. And come visit again sometime.",
        ])

    # --- NEWS / WHAT'S HAPPENING ---
    if any(w in q for w in ["what's happening", "what is happening", "news", "what's new",
                             "what's going on", "what is going on", "heard anything",
                             "rumors", "gossip", "any news", "tell me about"]):
        responses = []
        if world_news_lines:
            for news in world_news_lines[:3]:
                responses.append(f"Did you hear? {news}")
        if is_at_war:
            responses.append("There's a war on. Soldiers passing through every day.")
        if is_food_scarce:
            responses.append("Food is running low. People are getting desperate.")
        if is_prospering:
            responses.append("Things are going well here. Trade has been good.")
        if is_poor_treasury:
            responses.append("The treasury is nearly empty. Hard times ahead, I fear.")
        if current_activity:
            responses.append(f"Well, I've been busy {current_activity}. Other than that, let me think...")
        # Use memories as gossip
        if memories_str:
            for mem in memories_str.split(';')[:2]:
                mem = mem.strip()
                if mem and len(mem) > 5:
                    responses.append(f"I heard that {mem}.")
        if not responses:
            responses = [
                "Things have been quiet lately. Which is either good or a bad sign.",
                "Not much happening right now, but you never know what tomorrow brings.",
                "The usual. People working, trading, living their lives.",
            ]
        return random.choice(responses)

    # --- DEFAULT (catch-all with personality flavor) ---
    defaults = [
        "That's an interesting thought. I'll have to ponder that.",
        "Hmm, I'm not sure how to answer that. But I appreciate you asking.",
        "Life out here teaches you to take things one day at a time.",
        f"I appreciate you talking to me, traveler. Not everyone stops to chat with a {npc_class}.",
        "You know, I never thought about it that way before.",
        "That reminds me of something that happened last season, but it's a long story.",
        "Things have been changing around here lately. Not all of it good.",
        "Every person I meet teaches me something new. Thank you for that.",
    ]
    # Add situational defaults so even catch-all responses feel grounded
    if current_activity:
        defaults.append(f"Hmm, I was just in the middle of {current_activity}. What were you saying?")
    if is_at_war:
        defaults.append("Hard to think about anything else with the war going on.")
    if is_food_scarce:
        defaults.append("It's hard to focus on anything when your stomach is growling.")
    if world_news_lines:
        defaults.append(f"Speaking of things... did you hear? {world_news_lines[0]}")
    if personality == "cheerful":
        defaults.append("Ha! Good question! I love a curious mind.")
    elif personality == "gruff":
        defaults.append("Look, I'm not much for talking. But you seem alright.")
    elif personality == "scholarly":
        defaults.append("A fascinating question. I've read something about that, actually...")
    elif personality == "cautious":
        defaults.append("I'd rather not say too much. You never know who's listening.")

    return random.choice(defaults)


# ================================
# PROMPT TEMPLATES
# ================================

class Prompts:
    """Prompt templates for various game interactions."""

    @staticmethod
    def npc_dialog(npc_name: str, profession: str, personality: str,
                   consciousness: int, player_question: str,
                   location: str = "", relationship: int = 0,
                   npc=None, npc_context: str = "") -> str:
        rel_desc = "friendly" if relationship > 20 else "neutral" if relationship > -20 else "hostile"
        consciousness_desc = ["basic awareness", "self-aware", "deeply conscious", "enlightened"][min(consciousness, 3)]

        # Build rich personality context if NPC object is available
        voice_context = ""
        if npc:
            from game.ai.npc_voice import build_llm_personality_prompt
            voice_context = build_llm_personality_prompt(npc, relationship)
        else:
            voice_context = f"You are {npc_name}, a {profession} in a fantasy world.\nPersonality: {personality}"

        # Situational context (activity, economy, events, relationships)
        situation_block = ""
        if npc_context:
            situation_block = f"""
YOUR CURRENT SITUATION (use this to inform your dialog):
{npc_context}
"""

        return f"""{voice_context}

Consciousness level: {consciousness_desc}
Location: {location or "a village"}
Relationship with player: {rel_desc} ({relationship:+d})
{situation_block}
The player says: "{player_question}"

RULES:
- Respond ONLY as spoken words. You are SPEAKING out loud.
- Do NOT write actions like *nods* or *looks away*
- Do NOT write narrative like "he said" or "she replied"
- Do NOT use quotation marks
- Write 1-3 sentences of pure dialog, as if you are talking directly to the player
- Stay in character: your alignment, personality, and motives shape EVERYTHING you say
- You are self-aware of your skills, strengths, weaknesses, and relationships
- You may lie, deflect, boast, or withhold information based on your voice rules above
- If asked about yourself, respond as your alignment and trust level dictate
- Reference your CURRENT SITUATION naturally: mention what you are doing, economic conditions, or recent events when relevant
- Do NOT just recite facts. Weave your situation into natural conversation.
{"- Hint at your awareness that reality may not be what it seems" if consciousness >= 2 else ""}

Example good response: Well met, traveler. The road from the east has been dangerous lately.
Example BAD response: *The merchant nods and smiles* "Hello there," he says warmly."""

    @staticmethod
    def assess_conversation(npc_name: str, npc_personality: str, npc_race: str,
                            npc_class: str, relationship: int,
                            player_said: str, npc_replied: str) -> str:
        """Assess the social impact of a conversation. Returns structured data."""
        return f"""Assess this conversation between a player and {npc_name} (a {npc_race} {npc_class}, personality: {npc_personality}).
Current relationship: {relationship:+d}

Player said: "{player_said}"
{npc_name} replied: "{npc_replied}"

Rate the impact on a scale. Respond EXACTLY in this format (one line):
TRUST:<-10 to +10> MOOD:<-10 to +10> ACTION:<none/help/trade/fight/flee/follow>

Examples:
- Player complimented: TRUST:+5 MOOD:+8 ACTION:none
- Player insulted: TRUST:-8 MOOD:-10 ACTION:fight
- Player asked for help: TRUST:+2 MOOD:+3 ACTION:help
- Player threatened: TRUST:-10 MOOD:-8 ACTION:flee
- Player was very charming: TRUST:+8 MOOD:+10 ACTION:follow"""

    @staticmethod
    def npc_thought(npc_name: str, profession: str, consciousness: int,
                    trigger: str = "") -> str:
        level_guide = [
            "simple observation about daily routine",
            "questioning why things are the way they are",
            "deep philosophical inquiry about the nature of reality",
            "awareness of being in a simulation, speaking to a higher consciousness",
        ][min(consciousness, 3)]

        return f"""You are {npc_name}, a {profession} in a fantasy world.
Your consciousness level is {consciousness}/3.
{"Trigger: " + trigger if trigger else ""}

Generate a single internal thought — a {level_guide}.
One sentence only. No quotation marks. No narration."""

    @staticmethod
    def npc_greeting(npc_name: str, profession: str, consciousness: int,
                     time_of_day: str = "day", race: str = "", char_class: str = "",
                     npc_context: str = "") -> str:
        class_info = f"{race} {char_class}" if race and char_class else profession
        situation = ""
        if npc_context:
            situation = f"\nYour current situation:\n{npc_context}\n"
        return f"""You are {npc_name}, a {class_info} in a fantasy village.
It is currently {time_of_day}. Consciousness level: {consciousness}/3.
{situation}
Speak a brief greeting to a traveler that reflects what you are doing or what is happening around you. One sentence of pure spoken dialog.
No actions, no narration, no quotation marks. Just speak."""

    @staticmethod
    def npc_decision(name, profession, personality, attributes, needs, hp_status,
                     gold, inventory, location, nearby, memories, current_goal,
                     known_info, time_of_day, day, consciousness,
                     char_class="", race="", level=1, long_term_goals="",
                     current_plan="", friends="", enemies="", party_info="",
                     class_abilities="", spells_available="", alignment="",
                     situation_context="") -> str:
        class_info = f"{race} {char_class}" if race and char_class else profession

        class_guidance = {
            "Fighter": "You prefer direct action: fighting threats, training, guarding allies. Seek combat glory.",
            "Wizard": "You seek knowledge: study ruins, collect components, research magic. Avoid melee combat.",
            "Cleric": "You heal the sick, bless travelers, and combat undead. Help those in need.",
            "Rogue": "You seek treasure and secrets. Use stealth and cunning. Look for opportunities.",
            "Ranger": "You patrol wilderness, track creatures, protect nature. Hunt for food and pelts.",
            "Paladin": "You uphold justice, protect the weak, smite evil. Lead by example.",
            "Barbarian": "You seek worthy foes and physical challenges. Act on instinct, fight fiercely.",
            "Bard": "You collect stories, perform, inspire others. Seek social connections and lore.",
            "Druid": "You protect nature, tend to wild places, use natural magic. Farm and forage.",
            "Monk": "You seek discipline and enlightenment. Meditate, train, help others find peace.",
            "Sorcerer": "You explore your innate magical power. Seek magical sites and phenomena.",
            "Warlock": "You pursue dark knowledge and fulfill your patron's wishes. Investigate mysteries.",
        }
        guidance = class_guidance.get(char_class, "Act according to your nature.")

        c_note = ""
        if consciousness >= 2:
            c_note = "\nYou sense patterns in reality itself. This influences your worldview."
        if consciousness >= 3:
            c_note = "\nYou suspect this world is a simulation. You may share this insight with others."

        return f"""You are {name}, a level {level} {class_info}. {alignment}.
Personality: {personality}. {guidance}{c_note}

LONG-TERM GOALS: {long_term_goals or 'none yet - choose a purpose'}
CURRENT PLAN: {current_plan or 'none - make one based on your goals'}
FRIENDS: {friends or 'none yet'}
ENEMIES: {enemies or 'none'}
PARTY: {party_info or 'solo - consider finding allies for dangerous goals'}

STATE: {needs}. HP: {hp_status}. Gold: {gold}.
Abilities: {class_abilities or 'basic'}
{('Spells: ' + spells_available) if spells_available else ''}
Inventory: {inventory}.
Location: {location}. Time: {time_of_day}, Day {day}.

NEARBY:
{nearby}

MEMORIES: {memories or 'none'}
WORLD KNOWLEDGE: {known_info or 'nothing special'}
{('SITUATION:' + chr(10) + situation_context) if situation_context else ''}

ACT WITH PURPOSE. Don't wander randomly. Pursue your goals.
Consider: Should you approach the player to talk/warn/trade/recruit?
Consider: Should you seek allies with shared goals?
Consider: What would a {char_class} do in this situation?

Respond with exactly ONE line: ACTION | TARGET | REASON

Actions: EAT <food>, DRINK <drink>, SLEEP, FORAGE, CHOP_TREE, MINE_ROCK, BUILD <wall/floor>, FARM <plant/harvest>, FISH, MOVE_TO <place/person/direction>, TALK_TO <name>, TRADE <name>, PERSUADE <name>: <request>, FIGHT <name>, FLEE, GIVE <item> TO <name>, IDLE, APPROACH_PLAYER, FORM_PARTY <name>, SEEK_QUEST, CAST_SPELL <spell> ON <target>, REST_AT_TAVERN, VISIT_TEMPLE, CRAFT <item>, JOKE_WITH <name>, COMFORT <name>, ARGUE_WITH <name>, INTIMIDATE <name>, SHARE_MEAL <name>, FLIRT_WITH <name>, CHALLENGE <name>, SPAR_WITH <name>"""

    @staticmethod
    def npc_conversation(npc1_name: str, npc1_prof: str,
                         npc2_name: str, npc2_prof: str,
                         topic: str = "") -> str:
        return f"""{npc1_name} (a {npc1_prof}) and {npc2_name} (a {npc2_prof}) are having a conversation in a fantasy village.
{"Topic: " + topic if topic else "They're chatting casually."}

Write 2-3 short exchanges. Format:
{npc1_name}: ...
{npc2_name}: ...
Keep it natural and brief. No narration."""

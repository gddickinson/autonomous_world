"""
Social Dynamics & Joy Spreading — emotion-driven NPC interactions.

Two major subsystems:

1. Social Dynamics (Love, Contempt, Betrayal)
   - Love-driven behaviors: gift giving, self-sacrifice, partnership, loyalty, grief amplification
   - Contempt-driven behaviors: bullying, exclusion, sabotage, betrayal, gossip
   - Betrayal mechanics: trust loss, revenge seeking, community witness response

2. Joy Spreading & Morale Cascades
   - Happy NPCs passively boost nearby NPCs' joy
   - Bards/performers spread joy at 2x range and intensity
   - Settlement morale aggregation with production/crime/birth modifiers
   - Celebration triggers: victory, harvest, wedding, building, birth
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# CONSTANTS
# ================================================================

# Love threshold: joy + trust toward someone
LOVE_THRESHOLD = 0.6
# Contempt threshold: disgust + anger toward someone
CONTEMPT_THRESHOLD = 0.5

# Gift giving chance per check (30s interval ~ 48 checks/day)
GIFT_CHANCE_PER_CHECK = 0.0002  # ~1% per day at 48 checks

# Sabotage chance per check
SABOTAGE_CHANCE_PER_CHECK = 0.0001  # ~0.5% per day

# Joy spreading
JOY_SPREAD_RANGE = 5.0  # tiles
JOY_SPREAD_AMOUNT = 0.05  # per tick for normal NPCs
BARD_JOY_RANGE = 10.0
BARD_JOY_AMOUNT = 0.10
TAVERN_JOY_BONUS = 0.10  # bonus for NPCs inside a tavern

# Morale thresholds
HIGH_MORALE = 0.3
LOW_MORALE = -0.3
VERY_LOW_MORALE = -0.5

# Morale effects
HIGH_MORALE_WORK_BONUS = 0.10
HIGH_MORALE_CRIME_REDUCTION = 0.20
HIGH_MORALE_BIRTH_BONUS = 0.10
LOW_MORALE_WORK_PENALTY = 0.20
LOW_MORALE_CRIME_INCREASE = 0.30
LOW_MORALE_REBELLION_RISK = 0.20
VERY_LOW_MORALE_EXODUS_RISK = 0.002  # per NPC per day-check

# Grief amplification for loved ones
GRIEF_LOVE_MULTIPLIER = 2.0

# Gossip: contempt contagion amount
GOSSIP_CONTEMPT_SPREAD = 0.08

# Betrayal revenge threshold
REVENGE_ANGER_THRESHOLD = 0.6


# ================================================================
# SOCIAL DYNAMICS SYSTEM
# ================================================================

class SocialDynamicsSystem:
    """Manages love, contempt, betrayal interactions between NPCs."""

    def __init__(self):
        self.event_log: List[str] = []
        self._social_timer = 0.0
        self._social_interval = 30.0  # seconds between social checks
        self._joy_timer = 0.0
        self._joy_interval = 15.0  # seconds between joy spread checks

    def update_social(self, dt: float, npcs: list, npc_grid,
                      game_time: float):
        """Run social dynamics checks (call every tick, internally throttled)."""
        self._social_timer += dt
        if self._social_timer < self._social_interval:
            return
        self._social_timer = 0.0

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            es = getattr(npc, 'emotion_state', None)
            if es is None:
                continue

            # Check love-driven behaviors
            self._check_love_behaviors(npc, es, npcs, npc_grid, game_time)

            # Check contempt-driven behaviors
            self._check_contempt_behaviors(npc, es, npcs, npc_grid, game_time)

    def update_joy_spreading(self, dt: float, npcs: list, npc_grid,
                             player_x: float, player_y: float,
                             structures: list):
        """Spread joy from happy NPCs to nearby ones (near player only)."""
        self._joy_timer += dt
        if self._joy_timer < self._joy_interval:
            return
        self._joy_timer = 0.0

        # Only process NPCs near the player (performance)
        nearby_npcs = npc_grid.get_nearby(player_x, player_y, 80)
        if not nearby_npcs:
            return

        # Build a set of tavern positions for bonus checks
        tavern_positions = []
        for s in structures:
            if getattr(s, 'kind', '') == 'tavern':
                tavern_positions.append((s.x, s.y, getattr(s, 'w', 10),
                                         getattr(s, 'h', 10)))

        for npc in nearby_npcs:
            if not getattr(npc, 'alive', True):
                continue
            es = getattr(npc, 'emotion_state', None)
            if es is None:
                continue

            joy = es.primary.get('joy', 0.0)
            if joy <= 0.5:
                continue

            # Determine spread range and amount
            is_bard = getattr(npc, 'char_class', '') == 'Bard' or \
                      getattr(npc, 'profession', '') == 'Bard'
            spread_range = BARD_JOY_RANGE if is_bard else JOY_SPREAD_RANGE
            spread_amount = BARD_JOY_AMOUNT if is_bard else JOY_SPREAD_AMOUNT

            # Find nearby NPCs to spread joy to
            targets = npc_grid.get_nearby(npc.x, npc.y, spread_range)
            for target in targets:
                if target is npc:
                    continue
                if not getattr(target, 'alive', True):
                    continue
                tes = getattr(target, 'emotion_state', None)
                if tes is None:
                    continue

                # Apply joy boost
                amount = spread_amount

                # Tavern bonus: check if target is inside a tavern
                for tx, ty, tw, th in tavern_positions:
                    if (tx <= target.x <= tx + tw and
                            ty <= target.y <= ty + th):
                        amount += TAVERN_JOY_BONUS
                        break

                old_joy = tes.primary.get('joy', 0.0)
                headroom = 1.0 - old_joy
                tes.primary['joy'] = min(1.0, old_joy + amount * headroom)

    def update_morale(self, npcs: list, population_system,
                      game_time: float):
        """Update settlement morale and apply cascading effects.

        Should be called once per game day.
        """
        if population_system is None:
            return

        settlements = getattr(population_system, 'settlements', {})
        if not settlements:
            return

        # Group NPCs by settlement
        settlement_npcs: Dict[str, List] = {name: [] for name in settlements}
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            nearest = population_system._nearest_settlement(npc.x, npc.y)
            if nearest and nearest in settlement_npcs:
                settlement_npcs[nearest].append(npc)

        for name, stats in settlements.items():
            local_npcs = settlement_npcs.get(name, [])
            if not local_npcs:
                continue

            # Calculate average mood
            total_mood = 0.0
            count = 0
            for npc in local_npcs:
                es = getattr(npc, 'emotion_state', None)
                if es is not None:
                    total_mood += es.mood
                    count += 1

            if count == 0:
                continue

            avg_mood = total_mood / count

            # Store morale on the settlement stats for other systems
            stats.morale = avg_mood

            # Apply morale effects
            if avg_mood > HIGH_MORALE:
                self._apply_high_morale(name, local_npcs, stats)
            elif avg_mood < VERY_LOW_MORALE:
                self._apply_very_low_morale(name, local_npcs, stats, npcs,
                                            population_system)
            elif avg_mood < LOW_MORALE:
                self._apply_low_morale(name, local_npcs, stats)

    def trigger_celebration(self, event_type: str, npcs: list,
                            x: float = 0.0, y: float = 0.0,
                            radius: float = 50.0,
                            npc_grid=None,
                            family_names: list = None):
        """Trigger a celebration event that boosts joy for affected NPCs.

        Args:
            event_type: One of 'victory', 'harvest', 'wedding', 'building',
                        'birth', 'coronation'
            npcs: All NPCs (used for kingdom-wide events)
            x, y: Center of the celebration
            radius: Affected radius
            npc_grid: Spatial grid for efficient lookups
            family_names: List of family member names (for birth events)
        """
        from game.systems.emotions import trigger_emotion

        joy_intensity = {
            'victory': 0.6,
            'harvest': 0.4,
            'wedding': 0.5,
            'building': 0.3,
            'birth': 0.5,
            'coronation': 0.4,
        }.get(event_type, 0.3)

        event_name = {
            'victory': 'festival',
            'harvest': 'festival',
            'wedding': 'festival',
            'building': 'festival',
            'birth': 'festival',
            'coronation': 'festival',
        }.get(event_type, 'festival')

        cause = f"celebration:{event_type}"

        if event_type == 'birth' and family_names:
            # Only affect family members
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                if npc.name in family_names:
                    trigger_emotion(npc, event_name, intensity=joy_intensity,
                                    cause=cause)
            self.event_log.append(
                f"A family celebrates a new birth!")
            return

        if event_type == 'coronation':
            # Kingdom-wide: affect all NPCs
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                trigger_emotion(npc, event_name,
                                intensity=joy_intensity * 0.5,
                                cause=cause)
            self.event_log.append(
                f"The kingdom celebrates a coronation!")
            return

        # Local celebration: use grid if available
        if npc_grid is not None:
            affected = npc_grid.get_nearby(x, y, radius)
        else:
            affected = [n for n in npcs
                        if math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2)
                        <= radius]

        for npc in affected:
            if not getattr(npc, 'alive', True):
                continue
            trigger_emotion(npc, event_name, intensity=joy_intensity,
                            cause=cause)

        label = event_type.replace('_', ' ')
        self.event_log.append(
            f"A {label} celebration lifts spirits! "
            f"({len(affected)} NPCs affected)")

    def on_npc_death(self, dead_npc, npcs: list, npc_grid=None):
        """Handle grief amplification when a loved one dies."""
        from game.systems.emotions import trigger_emotion

        dead_name = getattr(dead_npc, 'name', '')
        if not dead_name:
            return

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            if npc is dead_npc:
                continue
            es = getattr(npc, 'emotion_state', None)
            if es is None:
                continue

            bond = es.bonds.get(dead_name)
            if bond and bond.get('intensity', 0) > 0.3:
                # This NPC had a bond with the deceased
                love_level = self._get_love_toward(es, dead_name)
                if love_level > LOVE_THRESHOLD:
                    # Loved one died - amplified grief
                    trigger_emotion(npc, 'lost_loved_one',
                                    intensity=GRIEF_LOVE_MULTIPLIER,
                                    target=dead_name,
                                    cause=f"{dead_name} died")
                    self.event_log.append(
                        f"{npc.name} is devastated by the death of "
                        f"beloved {dead_name}.")
                else:
                    # Regular grief for bonded NPC
                    trigger_emotion(npc, 'lost_loved_one',
                                    intensity=0.8, target=dead_name,
                                    cause=f"{dead_name} died")

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self.event_log)
        self.event_log.clear()
        return log

    # ================================================================
    # LOVE BEHAVIORS
    # ================================================================

    def _check_love_behaviors(self, npc, es, npcs, npc_grid, game_time):
        """Check for love-driven interactions."""
        for target_name, bond in es.bonds.items():
            if bond.get('intensity', 0) < 0.3:
                continue

            love = self._get_love_toward(es, target_name)
            if love < LOVE_THRESHOLD:
                continue

            # Find the target NPC
            target = self._find_npc_by_name(target_name, npcs)
            if target is None or not getattr(target, 'alive', True):
                continue

            # Gift giving (small chance per check)
            if random.random() < GIFT_CHANCE_PER_CHECK:
                self._try_gift_giving(npc, target, game_time)

            # Partnership: prefer working near loved one
            # (sets a hint that the schedule/work system can use)
            npc._preferred_work_partner = target_name

            # Loyalty: if loved one has enemies, adopt them
            tes = getattr(target, 'emotion_state', None)
            if tes:
                for enemy_name, grudge in tes.grudges.items():
                    if grudge.get('intensity', 0) > 0.5:
                        if enemy_name not in es.grudges:
                            es.grudges[enemy_name] = {
                                'emotion': 'anger',
                                'intensity': grudge['intensity'] * 0.3,
                                'cause': f"loyalty to {target_name}",
                                'timestamp': game_time,
                            }

    def _try_gift_giving(self, giver, receiver, game_time):
        """Attempt to give a gift (gold or item) to a loved one."""
        giver_gold = getattr(giver, 'npc_gold', 0)
        if giver_gold > 5:
            gift_amount = max(1, int(giver_gold * 0.1))
            giver.npc_gold -= gift_amount
            receiver.npc_gold = getattr(receiver, 'npc_gold', 0) + gift_amount

            from game.systems.emotions import trigger_emotion
            trigger_emotion(receiver, 'received_gift', intensity=0.5,
                            target=giver.name,
                            cause=f"gift of {gift_amount} gold from {giver.name}",
                            game_time=game_time)

            self.event_log.append(
                f"{giver.name} gave {gift_amount} gold to "
                f"beloved {receiver.name}.")
            return

        # Try giving an item instead
        inventory = getattr(giver, 'npc_inventory', [])
        if len(inventory) > 2:
            # Don't give away last items
            item = random.choice(inventory)
            if item.name not in ('Bread', 'Water Flask'):
                from game.systems.emotions import trigger_emotion
                giver.npc_remove_item(item.name)
                receiver.npc_add_item(item)
                trigger_emotion(receiver, 'received_gift', intensity=0.5,
                                target=giver.name,
                                cause=f"gift of {item.name} from {giver.name}",
                                game_time=game_time)
                self.event_log.append(
                    f"{giver.name} gave {item.name} to "
                    f"beloved {receiver.name}.")

    # ================================================================
    # CONTEMPT BEHAVIORS
    # ================================================================

    def _check_contempt_behaviors(self, npc, es, npcs, npc_grid, game_time):
        """Check for contempt-driven interactions."""
        for target_name, grudge in list(es.grudges.items()):
            if grudge.get('intensity', 0) < 0.3:
                continue

            contempt = self._get_contempt_toward(es, target_name)
            if contempt < CONTEMPT_THRESHOLD:
                continue

            target = self._find_npc_by_name(target_name, npcs)
            if target is None or not getattr(target, 'alive', True):
                continue

            # Check proximity for some behaviors
            dist = math.sqrt((npc.x - target.x) ** 2 +
                             (npc.y - target.y) ** 2)
            is_nearby = dist < 10.0

            # Bullying: insult the target when nearby
            if is_nearby and random.random() < 0.05:
                self._do_bullying(npc, target, game_time)

            # Exclusion: mark target as excluded from trade
            if not hasattr(npc, '_trade_exclusions'):
                npc._trade_exclusions = set()
            npc._trade_exclusions.add(target_name)

            # Sabotage: small chance to reduce target's work output
            if random.random() < SABOTAGE_CHANCE_PER_CHECK:
                self._do_sabotage(npc, target, game_time)

            # Betrayal: steal from target if opportunity
            if (contempt > 0.7 and is_nearby and
                    random.random() < 0.001):
                self._do_betrayal(npc, target, npcs, npc_grid, game_time)

            # Gossip: spread negative opinion to nearby NPCs
            if random.random() < 0.02:
                self._do_gossip(npc, target_name, contempt,
                                npc_grid, game_time)

    def _do_bullying(self, bully, target, game_time):
        """Bully insults the target, triggering sadness."""
        from game.systems.emotions import trigger_emotion
        trigger_emotion(target, 'insulted', intensity=0.5,
                        target=bully.name,
                        cause=f"bullied by {bully.name}",
                        game_time=game_time)
        self.event_log.append(
            f"{bully.name} bullied {target.name}.")

    def _do_sabotage(self, saboteur, target, game_time):
        """Sabotage the target's work output."""
        # Apply a temporary work penalty
        if not hasattr(target, '_sabotage_penalty'):
            target._sabotage_penalty = 0.0
        target._sabotage_penalty = min(0.3,
                                        target._sabotage_penalty + 0.1)
        self.event_log.append(
            f"{saboteur.name} sabotaged {target.name}'s work.")

    def _do_betrayal(self, betrayer, target, npcs, npc_grid, game_time):
        """Steal from or betray the target."""
        from game.systems.emotions import trigger_emotion

        # Steal gold
        target_gold = getattr(target, 'npc_gold', 0)
        if target_gold > 2:
            stolen = max(1, int(target_gold * 0.2))
            target.npc_gold -= stolen
            betrayer.npc_gold = getattr(betrayer, 'npc_gold', 0) + stolen

            # Target reacts
            trigger_emotion(target, 'was_betrayed', intensity=1.0,
                            target=betrayer.name,
                            cause=f"robbed by {betrayer.name}",
                            game_time=game_time)

            # Permanent trust loss
            tes = getattr(target, 'emotion_state', None)
            if tes:
                tes.primary['trust'] = max(0.0,
                                            tes.primary.get('trust', 0.5) - 0.3)

            # Revenge desire if angry enough
            if tes and tes.primary.get('anger', 0) > REVENGE_ANGER_THRESHOLD:
                if not hasattr(target, '_revenge_targets'):
                    target._revenge_targets = []
                if betrayer.name not in target._revenge_targets:
                    target._revenge_targets.append(betrayer.name)

            # Witnesses lose trust in betrayer
            if npc_grid:
                witnesses = npc_grid.get_nearby(betrayer.x, betrayer.y, 8)
                for witness in witnesses:
                    if witness is betrayer or witness is target:
                        continue
                    if not getattr(witness, 'alive', True):
                        continue
                    wes = getattr(witness, 'emotion_state', None)
                    if wes is None:
                        continue
                    # Witness loses trust in betrayer
                    if betrayer.name in wes.bonds:
                        wes.bonds[betrayer.name]['intensity'] = max(
                            0.0, wes.bonds[betrayer.name]['intensity'] - 0.3)
                    if betrayer.name not in wes.grudges:
                        wes.grudges[betrayer.name] = {
                            'emotion': 'disgust',
                            'intensity': 0.3,
                            'cause': f"witnessed {betrayer.name} betray {target.name}",
                            'timestamp': game_time,
                        }
                    else:
                        wes.grudges[betrayer.name]['intensity'] = min(
                            1.0, wes.grudges[betrayer.name]['intensity'] + 0.2)

            self.event_log.append(
                f"{betrayer.name} betrayed {target.name}, "
                f"stealing {stolen} gold!")

    def _do_gossip(self, gossiper, target_name, contempt_level,
                   npc_grid, game_time):
        """Spread negative opinion of target to nearby NPCs."""
        if npc_grid is None:
            return

        nearby = npc_grid.get_nearby(gossiper.x, gossiper.y, 8)
        spread_count = 0
        for listener in nearby:
            if listener is gossiper:
                continue
            if not getattr(listener, 'alive', True):
                continue
            if listener.name == target_name:
                continue

            les = getattr(listener, 'emotion_state', None)
            if les is None:
                continue

            # Personality check: agreeable NPCs are less susceptible
            susceptibility = 1.0
            if hasattr(les, 'personality'):
                susceptibility -= (les.personality.agreeableness - 0.5) * 0.4

            if susceptibility < 0.3:
                continue

            # Apply contempt contagion
            spread_amount = GOSSIP_CONTEMPT_SPREAD * susceptibility
            if target_name in les.grudges:
                les.grudges[target_name]['intensity'] = min(
                    1.0, les.grudges[target_name]['intensity'] + spread_amount)
            else:
                les.grudges[target_name] = {
                    'emotion': 'disgust',
                    'intensity': spread_amount,
                    'cause': f"gossip from {gossiper.name}",
                    'timestamp': game_time,
                }
            spread_count += 1

        if spread_count > 0:
            self.event_log.append(
                f"{gossiper.name} gossiped about {target_name} to "
                f"{spread_count} NPCs.")

    # ================================================================
    # SELF-SACRIFICE (called from combat system)
    # ================================================================

    @staticmethod
    def check_self_sacrifice(defender, attacker, npcs, npc_grid) -> Optional:
        """Check if any nearby NPC loves the target enough to take the hit.

        Returns the NPC who will take the hit, or None.
        Called from combat when an NPC is about to be damaged.
        """
        if npc_grid is None:
            return None

        nearby = npc_grid.get_nearby(defender.x, defender.y, 3)
        for npc in nearby:
            if npc is defender or npc is attacker:
                continue
            if not getattr(npc, 'alive', True):
                continue
            es = getattr(npc, 'emotion_state', None)
            if es is None:
                continue

            defender_name = getattr(defender, 'name', '')
            bond = es.bonds.get(defender_name)
            if not bond or bond.get('intensity', 0) < 0.5:
                continue

            # Check love level
            joy = es.primary.get('joy', 0.0)
            trust = es.primary.get('trust', 0.0)
            if joy + trust > LOVE_THRESHOLD:
                # Bravery check
                bravery = getattr(npc, 'bravery', 0.5)
                if random.random() < bravery * 0.5:
                    return npc

        return None

    # ================================================================
    # MORALE EFFECTS
    # ================================================================

    def _apply_high_morale(self, settlement_name, local_npcs, stats):
        """Apply positive effects of high settlement morale."""
        for npc in local_npcs:
            # Work output bonus stored as attribute
            if not hasattr(npc, '_morale_work_bonus'):
                npc._morale_work_bonus = 0.0
            npc._morale_work_bonus = HIGH_MORALE_WORK_BONUS

        # Record on stats for other systems to read
        stats._crime_modifier = -HIGH_MORALE_CRIME_REDUCTION
        stats._birth_modifier = HIGH_MORALE_BIRTH_BONUS

    def _apply_low_morale(self, settlement_name, local_npcs, stats):
        """Apply negative effects of low settlement morale."""
        for npc in local_npcs:
            if not hasattr(npc, '_morale_work_bonus'):
                npc._morale_work_bonus = 0.0
            npc._morale_work_bonus = -LOW_MORALE_WORK_PENALTY

        stats._crime_modifier = LOW_MORALE_CRIME_INCREASE
        stats._birth_modifier = -LOW_MORALE_REBELLION_RISK

    def _apply_very_low_morale(self, settlement_name, local_npcs, stats,
                                all_npcs, population_system):
        """Apply severe effects of very low morale including exodus risk."""
        self._apply_low_morale(settlement_name, local_npcs, stats)

        # Mass exodus risk: NPCs may leave
        for npc in local_npcs:
            if random.random() < VERY_LOW_MORALE_EXODUS_RISK:
                # Find a better settlement to migrate to
                best_name = None
                best_morale = stats.morale if hasattr(stats, 'morale') else -1.0
                for other_name, other_stats in population_system.settlements.items():
                    if other_name == settlement_name:
                        continue
                    other_morale = getattr(other_stats, 'morale', 0.0)
                    if other_morale > best_morale:
                        best_morale = other_morale
                        best_name = other_name

                if best_name:
                    target_stats = population_system.settlements[best_name]
                    npc.home_x = target_stats.x + random.uniform(-5, 5)
                    npc.home_y = target_stats.y + random.uniform(-5, 5)
                    npc.target_x = npc.home_x
                    npc.target_y = npc.home_y
                    npc.state = 'walking'
                    self.event_log.append(
                        f"{npc.name} fled {settlement_name} due to "
                        f"terrible morale, heading to {best_name}.")

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _get_love_toward(es, target_name: str) -> float:
        """Calculate love level toward a target from bond + primary emotions."""
        bond = es.bonds.get(target_name)
        if not bond:
            return 0.0
        # Love = joy + trust weighted by bond intensity
        joy = es.primary.get('joy', 0.0)
        trust = es.primary.get('trust', 0.0)
        bond_weight = bond.get('intensity', 0.0)
        return (joy + trust) * bond_weight

    @staticmethod
    def _get_contempt_toward(es, target_name: str) -> float:
        """Calculate contempt level toward a target from grudge + emotions."""
        grudge = es.grudges.get(target_name)
        if not grudge:
            return 0.0
        disgust = es.primary.get('disgust', 0.0)
        anger = es.primary.get('anger', 0.0)
        grudge_weight = grudge.get('intensity', 0.0)
        return (disgust + anger) * grudge_weight

    @staticmethod
    def _find_npc_by_name(name: str, npcs: list):
        """Find an NPC by name. Returns None if not found."""
        for npc in npcs:
            if getattr(npc, 'name', '') == name:
                return npc
        return None

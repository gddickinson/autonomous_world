"""
Hierarchical Command & Decision-Making System.

Every settlement operates within a chain of command:

    Kingdom Ruler (King/Queen/Warchief)
      +-- Settlement Leader (Lord/Mayor/Elder)
            +-- Steward (domestic affairs)
            |     +-- Tax Collector
            |     +-- Merchants / Traders
            |     +-- Labourers / Workers
            +-- Captain of Guard (military)
            |     +-- Guards
            |     +-- Soldiers
            +-- Other titled NPCs (Priest, Wizard, etc.)

Leaders issue Commands; subordinates execute them during their work day.
Merchants make independent economic decisions (buy/sell/trade).
Any NPC can carry goods (not just porters).  Armed escorts protect
valuable shipments.  Bandits intercept unescorted caravans.
"""

import math
import random
from typing import Dict, List, Optional, Tuple, Any

# ================================================================
# COMMAND
# ================================================================

class Command:
    """An order from a superior to a subordinate."""

    _next_id = 0

    def __init__(self, issuer: str, target: str, command_type: str,
                 params: Optional[Dict[str, Any]] = None, priority: int = 5):
        Command._next_id += 1
        self.id = Command._next_id
        self.issuer = issuer          # NPC name (or kingdom ruler name)
        self.target = target          # NPC name, role, or "any_laborer"
        self.command_type = command_type
        self.params = params or {}
        self.priority = priority      # 1 = urgent, 10 = low
        self.status = "pending"       # pending, accepted, in_progress, completed, failed
        self.issued_day: int = 0
        self.assigned_to: Optional[str] = None  # NPC name once accepted

    def __repr__(self):
        return (f"<Command #{self.id} {self.command_type} "
                f"from={self.issuer} to={self.target} "
                f"status={self.status}>")


# ================================================================
# TRADE / ECONOMIC DECISIONS
# ================================================================

class TradeDecision:
    """A merchant's plan to buy goods in one place and sell in another."""

    def __init__(self, good: str, buy_qty: int,
                 from_settlement: str, sell_to_settlement: str,
                 expected_profit: float = 0.0):
        self.good = good
        self.buy_qty = buy_qty
        self.from_settlement = from_settlement
        self.sell_to_settlement = sell_to_settlement
        self.expected_profit = expected_profit
        self.status = "planned"  # planned, buying, travelling, selling, done


# ================================================================
# ESCORT / CARAVAN
# ================================================================

class Caravan:
    """A trade shipment that may need armed escort."""

    _next_id = 0

    def __init__(self, owner_name: str, from_settlement: str,
                 to_settlement: str, goods: Dict[str, int],
                 x: float, y: float):
        Caravan._next_id += 1
        self.id = Caravan._next_id
        self.owner_name = owner_name
        self.from_settlement = from_settlement
        self.to_settlement = to_settlement
        self.goods = goods            # {good_name: quantity}
        self.x = x
        self.y = y
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None
        self.escort_names: List[str] = []
        self.goods_value: float = sum(goods.values()) * 3  # rough estimate
        self.alive = True
        self.arrived = False

    @property
    def has_escort(self) -> bool:
        return len(self.escort_names) > 0


# ================================================================
# HIERARCHY HELPERS
# ================================================================

# Titles that count as settlement leaders
LEADER_TITLES = {"lord", "mayor", "elder", "chief"}

# Titles that count as stewards / domestic administrators
STEWARD_TITLES = {"steward"}

# Titles that count as military leaders
MILITARY_LEADER_TITLES = {"captain", "knight", "sergeant"}

# Roles that can receive labour commands
LABOR_ROLES = {"Laborer", "Porter", "Farmer", "Miner", "Woodcutter",
               "Builder", "Mason", "Carpenter"}

# Roles that can receive military commands
MILITARY_ROLES = {"Guard", "Fighter", "Paladin", "Barbarian", "Ranger",
                  "Captain", "Soldier"}

# Universal carry capacity by profession / strength
UNIVERSAL_CARRY = {
    "base": 5,
    "strong": 8,       # STR > 14
    "porter": 10,      # Porter / Laborer profession
}


def _distance(x1, y1, x2, y2) -> float:
    dx = x1 - x2
    dy = y1 - y2
    return math.sqrt(dx * dx + dy * dy)


def _get_npc_settlement(npc) -> Optional[str]:
    """Find the settlement name an NPC belongs to."""
    home = getattr(npc, 'home_settlement', None)
    if home:
        return home
    return getattr(npc, 'faction', None) or None


def _npc_carry_capacity(npc) -> int:
    """Any NPC can carry goods.  Capacity depends on STR and profession."""
    profession = getattr(npc, 'profession', '')
    if profession in ("Porter", "Laborer"):
        cap = UNIVERSAL_CARRY["porter"]
    else:
        cap = UNIVERSAL_CARRY["base"]

    scores = getattr(npc, 'ability_scores', {})
    strength = scores.get('strength', 10)
    if isinstance(strength, (int, float)) and strength > 14:
        cap = max(cap, UNIVERSAL_CARRY["strong"])
    return cap


# ================================================================
# COMMAND SYSTEM
# ================================================================

class CommandSystem:
    """Manages hierarchical command flow from rulers to workers."""

    def __init__(self):
        self.pending_commands: List[Command] = []
        self.active_commands: Dict[str, Command] = {}   # npc_name -> Command
        self.caravans: List[Caravan] = []
        self.event_log: List[str] = []
        self._daily_timer: float = 0.0
        self._bandit_timer: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, dt: float, npcs: list, world_effects, governance,
               time_sys, world=None, creatures=None):
        """Called every simulation tick.  Leaders decide once per game-day;
        command assignment and caravan checks run every tick."""

        day = getattr(time_sys, 'day', 1)

        # --- Daily: leader decision-making ---
        self._daily_timer += dt
        if self._daily_timer >= 600.0:  # once per game-day (DAY_LENGTH)
            self._daily_timer = 0.0
            self._ruler_decisions(governance, world_effects, time_sys, day)
            self._settlement_leader_decisions(npcs, world_effects, day)
            self._merchant_decisions(npcs, world_effects, world)
            self._expire_old_commands(day)

        # --- Per-tick: assign pending commands ---
        self._assign_commands(npcs)

        # --- Per-tick: update caravans (movement, escort, banditry) ---
        self._update_caravans(dt, npcs, world, world_effects, creatures)

        # --- Bandit checks (every ~30 seconds) ---
        self._bandit_timer += dt
        if self._bandit_timer >= 30.0 and creatures:
            self._bandit_timer = 0.0
            self._check_bandit_attacks(npcs, creatures)

    def get_command(self, npc_name: str) -> Optional[Command]:
        """Get the active command for an NPC (if any)."""
        return self.active_commands.get(npc_name)

    def complete_command(self, npc_name: str):
        """Mark a command as completed and remove it."""
        cmd = self.active_commands.pop(npc_name, None)
        if cmd:
            cmd.status = "completed"

    def fail_command(self, npc_name: str, reason: str = ""):
        """Mark a command as failed."""
        cmd = self.active_commands.pop(npc_name, None)
        if cmd:
            cmd.status = "failed"

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs

    # ------------------------------------------------------------------
    # Ruler-level strategic decisions
    # ------------------------------------------------------------------

    def _ruler_decisions(self, governance, world_effects, time_sys, day: int):
        """Kingdom rulers make strategic decisions about taxes, food, military."""
        if not governance:
            return
        for kingdom_name, kingdom in governance.kingdoms.items():
            ruler_name = kingdom.ruler_name
            if not ruler_name:
                continue

            # --- Treasury low: demand extra tax collection ---
            if kingdom.treasury < 100:
                self.pending_commands.append(Command(
                    issuer=ruler_name,
                    target="Tax Collector",
                    command_type="collect_extra_tax",
                    params={"rate_bonus": 0.05, "kingdom": kingdom_name},
                    priority=3,
                ))

            # --- Food shortage across settlements ---
            for settlement_name in kingdom.settlements:
                if not world_effects:
                    continue
                stores = world_effects.get_settlement_stores(settlement_name)
                food = stores.get("food", 0)

                if food < 10:
                    self.pending_commands.append(Command(
                        issuer=ruler_name,
                        target="Steward",
                        command_type="increase_food_production",
                        params={"settlement": settlement_name},
                        priority=2,
                    ))
                    self.event_log.append(
                        f"{ruler_name} orders more food for {settlement_name} (stores={food:.0f})")

                # --- Low on weapons when at war ---
                weapons = stores.get("weapons", 0)
                at_war = False
                if governance:
                    for rel in governance.diplomacy.values():
                        if getattr(rel, 'status', '') == 'at_war':
                            at_war = True
                            break
                if at_war and weapons < 5:
                    self.pending_commands.append(Command(
                        issuer=ruler_name,
                        target="Blacksmith",
                        command_type="forge_weapons",
                        params={"settlement": settlement_name, "quantity": 10},
                        priority=2,
                    ))

            # --- Military: recruit if army is small ---
            if kingdom.army_size < len(kingdom.settlements) * 2:
                self.pending_commands.append(Command(
                    issuer=ruler_name,
                    target="any_combat",
                    command_type="enlist_military",
                    params={"kingdom": kingdom_name},
                    priority=4,
                ))

            # --- Trade surplus: send caravans using price boards ---
            if kingdom.treasury > 200 and len(kingdom.settlements) >= 2:
                best_trade_margin = 0
                best_good = None
                best_from = None
                best_to = None
                best_qty = 0

                settlement_names = list(kingdom.settlements)
                for i, sname_a in enumerate(settlement_names):
                    board_a = world_effects.get_price_board(sname_a)
                    stores_a = world_effects.get_settlement_stores(sname_a) if world_effects else {}
                    for sname_b in settlement_names[i + 1:]:
                        board_b = world_effects.get_price_board(sname_b)
                        transport = world_effects.get_transport_cost(
                            sname_a, sname_b, quantity=1)

                        # A->B opportunities
                        for good, buy_p, sell_p, margin in \
                                board_b.get_profitable_imports(board_a):
                            net = margin - transport
                            avail = stores_a.get(good, 0)
                            if net > best_trade_margin and avail >= 5:
                                best_trade_margin = net
                                best_good = good
                                best_from = sname_a
                                best_to = sname_b
                                best_qty = min(15, avail // 2)

                        # B->A opportunities
                        stores_b = world_effects.get_settlement_stores(sname_b) if world_effects else {}
                        for good, buy_p, sell_p, margin in \
                                board_a.get_profitable_imports(board_b):
                            net = margin - transport
                            avail = stores_b.get(good, 0)
                            if net > best_trade_margin and avail >= 5:
                                best_trade_margin = net
                                best_good = good
                                best_from = sname_b
                                best_to = sname_a
                                best_qty = min(15, avail // 2)

                if best_good and best_from and best_to and best_qty > 0:
                    self.pending_commands.append(Command(
                        issuer=ruler_name,
                        target="Merchant",
                        command_type="trade_caravan",
                        params={
                            "good": best_good,
                            "quantity": best_qty,
                            "from": best_from,
                            "to": best_to,
                        },
                        priority=5,
                    ))

    # ------------------------------------------------------------------
    # Settlement leader decisions
    # ------------------------------------------------------------------

    def _settlement_leader_decisions(self, npcs: list, world_effects, day: int):
        """Local lords / mayors / elders make settlement-level decisions."""
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            title = getattr(npc, 'title', 'commoner')
            if title not in LEADER_TITLES:
                continue

            settlement = _get_npc_settlement(npc)
            if not settlement or not world_effects:
                continue

            stores = world_effects.get_settlement_stores(settlement)
            local_npcs = [n for n in npcs
                          if getattr(n, 'alive', True)
                          and _get_npc_settlement(n) == settlement]

            # Count workers by profession
            prof_counts: Dict[str, int] = {}
            for n in local_npcs:
                p = getattr(n, 'profession', '') or "Laborer"
                prof_counts[p] = prof_counts.get(p, 0) + 1

            # --- Need blacksmith but have ore ---
            if prof_counts.get("Blacksmith", 0) == 0 and stores.get("ore", 0) > 5:
                self.pending_commands.append(Command(
                    issuer=npc.name,
                    target="any_laborer",
                    command_type="change_profession",
                    params={"new_profession": "Blacksmith", "settlement": settlement},
                    priority=4,
                ))

            # --- Food low: need more farmers ---
            if stores.get("food", 0) < 20 and prof_counts.get("Farmer", 0) < 3:
                self.pending_commands.append(Command(
                    issuer=npc.name,
                    target="any_laborer",
                    command_type="change_profession",
                    params={"new_profession": "Farmer", "settlement": settlement},
                    priority=2,
                ))
                self.event_log.append(
                    f"{npc.name} orders more farmers in {settlement}")

            # --- Wood low: need woodcutters ---
            if stores.get("wood", 0) < 10 and prof_counts.get("Woodcutter", 0) < 2:
                self.pending_commands.append(Command(
                    issuer=npc.name,
                    target="any_laborer",
                    command_type="change_profession",
                    params={"new_profession": "Woodcutter", "settlement": settlement},
                    priority=5,
                ))

            # --- Ore low: need miners ---
            if stores.get("ore", 0) < 5 and prof_counts.get("Miner", 0) < 2:
                self.pending_commands.append(Command(
                    issuer=npc.name,
                    target="any_laborer",
                    command_type="change_profession",
                    params={"new_profession": "Miner", "settlement": settlement},
                    priority=5,
                ))

            # --- No guards: assign fighters ---
            guard_count = sum(1 for n in local_npcs
                              if getattr(n, 'title', '') in ('guard', 'sergeant', 'captain'))
            if guard_count == 0 and len(local_npcs) > 5:
                self.pending_commands.append(Command(
                    issuer=npc.name,
                    target="any_combat",
                    command_type="assign_guard_duty",
                    params={"settlement": settlement},
                    priority=3,
                ))

            # --- Trade caravan escort request ---
            # If there is an active caravan departing, assign guards
            for caravan in self.caravans:
                if (caravan.alive and not caravan.arrived
                        and caravan.from_settlement == settlement
                        and not caravan.has_escort
                        and caravan.goods_value > 30):
                    self.pending_commands.append(Command(
                        issuer=npc.name,
                        target="any_guard",
                        command_type="escort_caravan",
                        params={"caravan_id": caravan.id, "settlement": settlement},
                        priority=3,
                    ))

    # ------------------------------------------------------------------
    # Merchant economic decisions
    # ------------------------------------------------------------------

    def _merchant_decisions(self, npcs: list, world_effects, world):
        """Merchants find the most profitable trade route using price boards.

        Uses per-settlement price boards to compare buy/sell prices and
        picks the single most profitable good to trade (accounting for
        transport costs).
        """
        if not world_effects:
            return

        plan = getattr(world, 'plan', None) if world else None
        if plan is None:
            plan = getattr(world_effects, 'world', None)
            if plan:
                plan = getattr(plan, 'plan', None)

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            profession = getattr(npc, 'profession', '')
            if profession not in ("Merchant", "Trader"):
                continue
            # Skip merchants already on a command
            if npc.name in self.active_commands:
                continue

            home = _get_npc_settlement(npc)
            if not home:
                continue

            trade = self._find_best_trade(
                npc, home, world_effects, plan)
            if trade is None:
                continue

            self.pending_commands.append(Command(
                issuer=npc.name,
                target=npc.name,  # self-issued
                command_type="merchant_trade",
                params={
                    "good": trade["buy_good"],
                    "quantity": trade["quantity"],
                    "from": trade["buy_at"],
                    "to": trade["sell_at"],
                    "buy_price": trade["buy_price"],
                    "sell_price": trade["sell_price"],
                    "net_profit": trade["net_profit"],
                },
                priority=5,
            ))

    # ------------------------------------------------------------------
    # Price-board merchant AI
    # ------------------------------------------------------------------

    @staticmethod
    def _find_best_trade(npc, home: str, world_effects, plan) -> Optional[Dict]:
        """Find the single most profitable trade route for *npc*.

        Checks both import opportunities (buy elsewhere, sell at home)
        and export opportunities (buy at home, sell elsewhere).
        Returns a dict describing the trade or None.
        """
        if plan is None:
            return None

        settlements = getattr(plan, 'settlements', [])
        if not settlements:
            return None

        home_prices = world_effects.get_price_board(home)
        home_sp = None
        for sp in settlements:
            if sp.name == home:
                home_sp = sp
                break
        if home_sp is None:
            return None

        best_trade = None
        best_profit = 2  # minimum 2 gold net profit to bother

        for sp in settlements:
            if sp.name == home:
                continue

            transport_cost = world_effects.get_transport_cost(
                home, sp.name, quantity=1)

            other_prices = world_effects.get_price_board(sp.name)

            # --- Import: buy there cheap, sell here expensive ---
            for good, buy_price, sell_price, margin in \
                    home_prices.get_profitable_imports(other_prices):
                net = margin - transport_cost
                if net > best_profit:
                    # Check that the other settlement has stock
                    other_stores = world_effects.get_settlement_stores(sp.name)
                    avail = other_stores.get(good, 0)
                    if avail < 2:
                        continue
                    qty = min(10, avail // 2)
                    if qty < 1:
                        continue
                    best_profit = net
                    best_trade = {
                        "buy_good": good,
                        "buy_at": sp.name,
                        "sell_at": home,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "net_profit": net,
                        "quantity": qty,
                    }

            # --- Export: buy here cheap, sell there expensive ---
            for good, buy_price, sell_price, margin in \
                    other_prices.get_profitable_imports(home_prices):
                net = margin - transport_cost
                if net > best_profit:
                    home_stores = world_effects.get_settlement_stores(home)
                    avail = home_stores.get(good, 0)
                    if avail < 2:
                        continue
                    qty = min(10, avail // 2)
                    if qty < 1:
                        continue
                    best_profit = net
                    best_trade = {
                        "buy_good": good,
                        "buy_at": home,
                        "sell_at": sp.name,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "net_profit": net,
                        "quantity": qty,
                    }

        # Add a memory about the trade decision
        if best_trade:
            npc.add_memory(
                "trade",
                f"Decided to trade {best_trade['buy_good']} from "
                f"{best_trade['buy_at']} to {best_trade['sell_at']} "
                f"(profit ~{best_trade['net_profit']}g per unit)", 2)

        return best_trade

    # ------------------------------------------------------------------
    # Command assignment
    # ------------------------------------------------------------------

    def _assign_commands(self, npcs: list):
        """Match pending commands to appropriate NPCs."""
        if not self.pending_commands:
            return

        # Sort by priority (lower = more urgent)
        self.pending_commands.sort(key=lambda c: c.priority)

        for cmd in list(self.pending_commands):
            assigned = False
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                # Don't assign a second command
                if npc.name in self.active_commands:
                    continue

                if self._npc_matches_target(npc, cmd):
                    self.active_commands[npc.name] = cmd
                    cmd.status = "accepted"
                    cmd.assigned_to = npc.name
                    assigned = True
                    break

            if assigned:
                self.pending_commands.remove(cmd)

    def _npc_matches_target(self, npc, cmd: Command) -> bool:
        """Check if an NPC matches the command target."""
        target = cmd.target
        profession = getattr(npc, 'profession', '')
        title = getattr(npc, 'title', 'commoner')

        # Exact name match
        if target == npc.name:
            return True

        # Role / profession match
        if target == profession or target == title:
            return True

        # "any_laborer" - match laborers, porters, or unemployed
        if target == "any_laborer":
            if profession in ("Laborer", "Porter", ""):
                return True
            # Also match NPCs without a strong profession
            if not profession or profession == "Fighter":
                if title in ("commoner", "servant", "serf"):
                    return True

        # "any_combat" - match combat-capable NPCs
        if target == "any_combat":
            char_class = getattr(npc, 'char_class', '')
            if char_class in ("Fighter", "Ranger", "Paladin", "Barbarian"):
                if title in ("commoner", "guard", "sergeant"):
                    return True

        # "any_guard" - match guards for escort
        if target == "any_guard":
            if title in ("guard", "sergeant", "captain"):
                return True

        # Settlement match check for location-specific commands
        cmd_settlement = cmd.params.get("settlement")
        if cmd_settlement:
            npc_settlement = _get_npc_settlement(npc)
            if npc_settlement != cmd_settlement:
                return False

        return False

    # ------------------------------------------------------------------
    # Command execution helpers (called from npc_work integration)
    # ------------------------------------------------------------------

    @staticmethod
    def execute_command(npc, cmd: Command, world_effects=None,
                        world=None) -> bool:
        """Execute a command on an NPC.  Returns True if the NPC should
        skip its normal work routine this cycle.

        This is called from the NPC work system at the start of the work day.
        """
        ct = cmd.command_type
        cmd.status = "in_progress"

        if ct == "collect_extra_tax":
            npc.current_action = "collecting"
            npc.state = "working"
            npc.action_timer = random.uniform(20.0, 40.0)
            # The actual tax collection math is handled by governance
            return True

        if ct == "increase_food_production":
            # Steward oversees food production - acts as a supervisor
            npc.current_action = "administering"
            npc.state = "working"
            npc.action_timer = random.uniform(20.0, 35.0)
            # Boost food output in target settlement
            settlement = cmd.params.get("settlement")
            if settlement and world_effects:
                stores = world_effects.get_stores_ref(settlement)
                # Steward bonus: direct small food injection (organizing rationing)
                stores["food"] = stores.get("food", 0) + 2
            return True

        if ct == "forge_weapons":
            npc.current_action = "smithing"
            npc.state = "working"
            npc.action_timer = random.uniform(25.0, 45.0)
            settlement = cmd.params.get("settlement")
            if settlement and world_effects:
                stores = world_effects.get_stores_ref(settlement)
                ore = stores.get("ore", 0)
                if ore >= 3:
                    stores["ore"] = ore - 3
                    stores["weapons"] = stores.get("weapons", 0) + 2
            return True

        if ct == "change_profession":
            new_prof = cmd.params.get("new_profession", "Farmer")
            old_prof = getattr(npc, 'profession', '')
            npc.profession = new_prof
            npc.add_memory("career",
                           f"Assigned to become {new_prof} by {cmd.issuer}", 3)
            cmd.status = "completed"
            return False  # NPC can immediately start new profession work

        if ct == "enlist_military":
            if getattr(npc, 'title', '') == "commoner":
                npc.title = "guard"
                npc.add_memory("military",
                               f"Enlisted as guard by order of {cmd.issuer}", 4)
            cmd.status = "completed"
            return False

        if ct == "assign_guard_duty":
            if getattr(npc, 'title', '') in ("commoner", "guard"):
                npc.title = "guard"
                npc.current_action = "guarding"
                npc.state = "working"
                npc.action_timer = random.uniform(25.0, 50.0)
                npc.add_memory("military",
                               f"Assigned to guard duty by {cmd.issuer}", 3)
            cmd.status = "completed"
            return True

        if ct == "escort_caravan":
            npc.current_action = "escorting"
            npc.state = "walking"
            # The caravan update loop handles the escort movement
            return True

        if ct == "merchant_trade":
            # Merchant initiates a trade run using price boards
            good = cmd.params.get("good", "food")
            quantity = cmd.params.get("quantity", 5)
            from_s = cmd.params.get("from", "")
            to_s = cmd.params.get("to", "")

            if from_s and to_s and world_effects:
                # Buy goods from the source settlement market
                bought = world_effects.market_buy(
                    from_s, npc, good, quantity)
                if bought > 0:
                    # NPC now "carries" the goods as a caravan
                    npc._trade_goods = {good: bought}
                    npc._trade_destination = to_s
                    npc._trade_sell_price = cmd.params.get("sell_price", 0)
                    npc.current_action = "trading"
                    npc.state = "walking"
                    buy_price = cmd.params.get("buy_price", "?")
                    sell_price = cmd.params.get("sell_price", "?")
                    npc.add_memory(
                        "trade",
                        f"Bought {bought} {good} at {from_s} "
                        f"(price {buy_price}g) to sell at {to_s} "
                        f"(price {sell_price}g)", 2)
                    return True
            cmd.status = "failed"
            return False

        if ct == "trade_caravan":
            # Ruler-ordered trade caravan
            good = cmd.params.get("good", "food")
            quantity = cmd.params.get("quantity", 5)
            from_s = cmd.params.get("from", "")
            to_s = cmd.params.get("to", "")

            if from_s and to_s and world_effects:
                stores = world_effects.get_stores_ref(from_s)
                available = stores.get(good, 0)
                actual_qty = min(quantity, available)
                if actual_qty > 0:
                    stores[good] = stores.get(good, 0) - actual_qty
                    npc._trade_goods = {good: actual_qty}
                    npc._trade_destination = to_s
                    npc.current_action = "trading"
                    npc.state = "walking"
                    return True
            cmd.status = "failed"
            return False

        # Unknown command type - skip
        cmd.status = "failed"
        return False

    # ------------------------------------------------------------------
    # Caravan management
    # ------------------------------------------------------------------

    def _update_caravans(self, dt: float, npcs: list, world,
                         world_effects, creatures):
        """Update active caravans: move them, check escorts, handle arrivals."""
        for caravan in list(self.caravans):
            if not caravan.alive or caravan.arrived:
                continue

            # Move caravan towards target
            if caravan.target_x is not None and caravan.target_y is not None:
                dx = caravan.target_x - caravan.x
                dy = caravan.target_y - caravan.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < 3.0:
                    # Arrived
                    caravan.arrived = True
                    if world_effects:
                        stores = world_effects.get_stores_ref(caravan.to_settlement)
                        board = world_effects.get_price_board(caravan.to_settlement)
                        total_value = 0
                        for good, qty in caravan.goods.items():
                            stores[good] = stores.get(good, 0) + qty
                            total_value += board.get_price(good) * qty
                            board.record_sale(good)
                    else:
                        total_value = sum(caravan.goods.values()) * 3
                    self.event_log.append(
                        f"Caravan from {caravan.from_settlement} arrived at "
                        f"{caravan.to_settlement} ({total_value}g in goods)")
                    # Release escorts
                    for ename in caravan.escort_names:
                        self.complete_command(ename)
                else:
                    speed = 2.0 * dt
                    caravan.x += (dx / dist) * speed
                    caravan.y += (dy / dist) * speed

            # Move escort NPCs with caravan
            for ename in caravan.escort_names:
                for npc in npcs:
                    if npc.name == ename and npc.alive:
                        npc.target_x = caravan.x + random.uniform(-2, 2)
                        npc.target_y = caravan.y + random.uniform(-2, 2)
                        break

        # Cleanup finished caravans
        self.caravans = [c for c in self.caravans
                         if c.alive and not c.arrived]

    # ------------------------------------------------------------------
    # Escort system
    # ------------------------------------------------------------------

    def needs_escort(self, cargo_value: float, route_safety: float = 0.7) -> bool:
        """Determine if a shipment needs armed guards."""
        if cargo_value > 50:
            return True
        if route_safety < 0.5:
            return True
        if cargo_value > 25 and route_safety < 0.7:
            return True
        return False

    def assign_escort(self, caravan: Caravan, guard_npcs: list):
        """Assign guards to protect a trade caravan."""
        for guard in guard_npcs:
            if not guard.alive:
                continue
            if guard.name in self.active_commands:
                continue
            title = getattr(guard, 'title', 'commoner')
            if title not in ('guard', 'sergeant', 'captain', 'knight'):
                continue
            # Check proximity
            if _distance(guard.x, guard.y, caravan.x, caravan.y) < 30:
                caravan.escort_names.append(guard.name)
                guard.current_action = "escorting"
                guard.state = "walking"
                guard._escort_target = caravan
                cmd = Command(
                    issuer="auto",
                    target=guard.name,
                    command_type="escort_caravan",
                    params={"caravan_id": caravan.id},
                    priority=2,
                )
                cmd.status = "in_progress"
                self.active_commands[guard.name] = cmd
                if len(caravan.escort_names) >= 2:
                    break  # 2 guards max per caravan

    # ------------------------------------------------------------------
    # Banditry
    # ------------------------------------------------------------------

    def _check_bandit_attacks(self, npcs: list, creatures: list):
        """Check if bandits attack unescorted merchants / caravans."""
        if not creatures:
            return

        # Find bandits
        bandits = [c for c in creatures
                   if getattr(c, 'alive', True)
                   and getattr(c, 'kind', '') in ('bandit', 'bandit_leader',
                                                    'highwayman', 'thief')]
        if not bandits:
            # Also check NPCs with bandit-like traits (rogues in the wild)
            pass

        # Check caravans
        for caravan in self.caravans:
            if not caravan.alive or caravan.arrived or caravan.has_escort:
                continue
            for bandit in bandits:
                dist = _distance(bandit.x, bandit.y, caravan.x, caravan.y)
                if dist < 15:
                    # Bandit intercepts caravan!
                    stolen_value = min(caravan.goods_value // 2, 20)
                    if stolen_value <= 0:
                        continue
                    # Reduce goods
                    for good in list(caravan.goods.keys()):
                        take = min(caravan.goods[good],
                                   max(1, caravan.goods[good] // 2))
                        caravan.goods[good] -= take
                        if caravan.goods[good] <= 0:
                            del caravan.goods[good]
                    caravan.goods_value -= stolen_value

                    # Bandit gains gold
                    if hasattr(bandit, 'npc_gold'):
                        bandit.npc_gold = getattr(bandit, 'npc_gold', 0) + stolen_value

                    self.event_log.append(
                        f"Bandits robbed a caravan from {caravan.from_settlement}! "
                        f"({stolen_value}g worth of goods stolen)")
                    break  # one attack per caravan per check

        # Check merchant NPCs carrying trade goods
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            trade_goods = getattr(npc, '_trade_goods', None)
            if not trade_goods:
                continue
            # Check if NPC has an escort command (is being escorted)
            has_escort = getattr(npc, '_has_escort', False)
            if has_escort:
                continue

            for bandit in bandits:
                dist = _distance(bandit.x, bandit.y, npc.x, npc.y)
                if dist < 12:
                    # Rob the merchant!
                    total_goods = sum(trade_goods.values())
                    stolen = min(total_goods // 2, 10)
                    if stolen <= 0:
                        continue
                    # Remove goods
                    for good in list(trade_goods.keys()):
                        take = min(trade_goods[good],
                                   max(1, trade_goods[good] // 3))
                        trade_goods[good] -= take
                        if trade_goods[good] <= 0:
                            del trade_goods[good]

                    if hasattr(bandit, 'npc_gold'):
                        bandit.npc_gold = getattr(bandit, 'npc_gold', 0) + stolen * 2

                    npc.add_memory("crime",
                                   f"Robbed by bandits! Lost goods worth ~{stolen * 2}g", 4)
                    self.event_log.append(
                        f"{npc.name} robbed by bandits on the road!")
                    break

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def _expire_old_commands(self, current_day: int):
        """Remove stale commands that were never assigned."""
        cutoff = current_day - 3  # expire after 3 days
        self.pending_commands = [
            c for c in self.pending_commands
            if c.issued_day >= cutoff or c.issued_day == 0
        ]
        # Expire active commands that have been running too long
        for npc_name in list(self.active_commands.keys()):
            cmd = self.active_commands[npc_name]
            if cmd.status == "in_progress" and cmd.issued_day > 0:
                if current_day - cmd.issued_day > 5:
                    cmd.status = "failed"
                    del self.active_commands[npc_name]

"""
Banking and Financial System.

A full money-lending economy with:
- Banks that accept deposits and make loans
- Moneylenders and loansharks with different rates
- Revenue collectors who gather taxes
- Insurance against loss (theft, fire, death)
- Investments and bonds
- Credit scoring based on alignment, history, and assets
- Kingdom-specific financial regulations

Financial institutions:
- Royal Bank: low rates, strict regulations, requires good credit
- Merchant Guild Bank: moderate rates, trade-focused lending
- Moneylender: higher rates, accepts riskier borrowers
- Loanshark: very high rates, no questions asked, violent collection

Financial products:
- Savings deposits (earn interest)
- Personal loans (for NPCs in need)
- Business loans (for crafting/trade ventures)
- Property bonds (invest in settlement development)
- Cargo insurance (protect trade caravans)
- Life insurance (payout on death to family)

Kingdom financial policies:
- Usury laws (max interest rates)
- Banking regulations (reserve requirements)
- Debt slavery laws (what happens on default)
- Currency controls
"""

import random
import math
import time as _time
from typing import Dict, List, Optional, Tuple
from game.systems.alignment import get_tendency, ALIGNMENTS


# ================================================================
# FINANCIAL CONSTANTS
# ================================================================

# Interest rates (per game day)
INTEREST_RATES = {
    "royal_bank":      {"deposit": 0.001, "loan": 0.005, "name": "Royal Bank"},
    "merchant_guild":  {"deposit": 0.002, "loan": 0.008, "name": "Merchant Guild Bank"},
    "moneylender":     {"deposit": 0.003, "loan": 0.015, "name": "Moneylender"},
    "loanshark":       {"deposit": 0.000, "loan": 0.030, "name": "Loanshark"},
}

# Loan terms
MAX_LOAN_DURATION = 90   # game days
MIN_LOAN_AMOUNT = 5
MAX_LOAN_MULTIPLIER = 10  # max loan = credit_score * multiplier

# Insurance premiums (fraction of insured value per day)
INSURANCE_RATES = {
    "cargo":    0.002,  # 0.2% per day of cargo value
    "property": 0.001,  # 0.1% per day of property value
    "life":     0.003,  # 0.3% per day, pays out on death
}

# Bond yields (return per day on investment)
BOND_YIELDS = {
    "settlement_bond": 0.004,  # 0.4% per day — invest in settlement growth
    "war_bond":        0.006,  # 0.6% per day — higher risk, funds military
    "trade_bond":      0.005,  # 0.5% per day — funds trade caravans
}


# ================================================================
# KINGDOM FINANCIAL POLICIES
# ================================================================

FINANCIAL_POLICIES = {
    "feudalism": {
        "max_interest": 0.020,    # 2% per day cap (usury law)
        "banking_allowed": True,
        "loansharks_legal": False,
        "reserve_requirement": 0.2,  # banks must keep 20% in reserve
        "debt_slavery": False,     # debtors go to prison, not slavery
        "deposit_insurance": True, # kingdom guarantees deposits
        "tax_on_interest": 0.10,   # 10% tax on interest income
    },
    "republic": {
        "max_interest": 0.015,
        "banking_allowed": True,
        "loansharks_legal": False,
        "reserve_requirement": 0.3,
        "debt_slavery": False,
        "deposit_insurance": True,
        "tax_on_interest": 0.15,
    },
    "merchant_republic": {
        "max_interest": 0.025,     # higher cap — commerce-friendly
        "banking_allowed": True,
        "loansharks_legal": True,   # anything goes
        "reserve_requirement": 0.1,
        "debt_slavery": False,
        "deposit_insurance": False,  # caveat emptor
        "tax_on_interest": 0.05,    # low tax on finance
    },
    "theocracy": {
        "max_interest": 0.005,     # usury heavily restricted
        "banking_allowed": True,
        "loansharks_legal": False,
        "reserve_requirement": 0.4,
        "debt_slavery": False,
        "deposit_insurance": True,
        "tax_on_interest": 0.0,    # interest = charity, not taxed
    },
    "tyranny": {
        "max_interest": 0.040,     # no real cap
        "banking_allowed": True,
        "loansharks_legal": True,
        "reserve_requirement": 0.0,  # no regulation
        "debt_slavery": True,       # debtors become servants
        "deposit_insurance": False,
        "tax_on_interest": 0.30,   # tyrant takes a big cut
    },
    "tribal": {
        "max_interest": 0.000,     # no formal interest — gift economy
        "banking_allowed": False,   # no formal banks
        "loansharks_legal": False,
        "reserve_requirement": 0.0,
        "debt_slavery": False,
        "deposit_insurance": False,
        "tax_on_interest": 0.0,
    },
    "autocracy": {
        "max_interest": 0.025,
        "banking_allowed": True,
        "loansharks_legal": False,
        "reserve_requirement": 0.15,
        "debt_slavery": True,
        "deposit_insurance": False,
        "tax_on_interest": 0.20,
    },
    "anarchy": {
        "max_interest": 999.0,     # no rules
        "banking_allowed": True,
        "loansharks_legal": True,
        "reserve_requirement": 0.0,
        "debt_slavery": False,      # no one to enforce it
        "deposit_insurance": False,
        "tax_on_interest": 0.0,
    },
}


# ================================================================
# CREDIT SCORING
# ================================================================

def calc_credit_score(npc) -> int:
    """Calculate credit score (0-100) based on alignment, wealth, and history.
    Higher = more creditworthy.
    """
    score = 50  # baseline

    # Alignment: honor_deal tendency is the strongest predictor
    honor = get_tendency(npc, "honor_deal")
    score += int(honor * 30)  # 0-30 points

    # Steal tendency reduces credit
    steal = get_tendency(npc, "steal")
    score -= int(steal * 20)

    # Wealth as collateral
    gold = getattr(npc, 'npc_gold', 0)
    if gold > 50:
        score += 10
    elif gold > 20:
        score += 5
    elif gold < 5:
        score -= 10

    # Inventory value as assets
    inv_value = sum(getattr(i, 'value', 0) * getattr(i, 'count', 1)
                   for i in getattr(npc, 'npc_inventory', []))
    score += min(10, inv_value // 20)

    # Skills: accountancy/trading skills improve credit
    skills = getattr(npc, 'npc_skills', {})
    score += skills.get("trading", 0) * 2
    score += skills.get("literacy", 0)

    # Previous loan history (from life ledger)
    ledger = getattr(npc, 'life_ledger', None)
    if ledger:
        # Milestones for loan repayment
        for m in getattr(ledger, 'milestones', []):
            if "repaid" in m.get("description", "").lower():
                score += 5
            elif "defaulted" in m.get("description", "").lower():
                score -= 15

    return max(0, min(100, score))


# ================================================================
# LOAN
# ================================================================

class Loan:
    """A financial loan between a lender and borrower."""
    __slots__ = ('loan_id', 'lender_type', 'lender_name', 'borrower_name',
                 'principal', 'interest_rate', 'daily_payment',
                 'remaining', 'days_remaining', 'days_overdue',
                 'collateral', 'start_day', 'status')

    def __init__(self, loan_id: str, lender_type: str, lender_name: str,
                 borrower_name: str, principal: float, interest_rate: float,
                 duration: int, collateral: str = "", start_day: int = 0):
        self.loan_id = loan_id
        self.lender_type = lender_type  # royal_bank, merchant_guild, moneylender, loanshark
        self.lender_name = lender_name
        self.borrower_name = borrower_name
        self.principal = principal
        self.interest_rate = interest_rate
        self.daily_payment = (principal * (1 + interest_rate * duration)) / max(1, duration)
        self.remaining = principal * (1 + interest_rate * duration)
        self.days_remaining = duration
        self.days_overdue = 0
        self.collateral = collateral
        self.start_day = start_day
        self.status = "active"  # active, repaid, defaulted, seized

    @property
    def total_owed(self) -> float:
        return self.remaining

    def make_payment(self, amount: float) -> float:
        """Make a payment. Returns amount actually applied."""
        payment = min(amount, self.remaining)
        self.remaining -= payment
        if self.remaining <= 0.01:
            self.remaining = 0
            self.status = "repaid"
        return payment


# ================================================================
# DEPOSIT ACCOUNT
# ================================================================

class DepositAccount:
    """A savings deposit at a financial institution."""
    __slots__ = ('owner_name', 'institution_type', 'balance',
                 'interest_rate', 'opened_day')

    def __init__(self, owner_name: str, institution_type: str,
                 balance: float, interest_rate: float, opened_day: int):
        self.owner_name = owner_name
        self.institution_type = institution_type
        self.balance = balance
        self.interest_rate = interest_rate
        self.opened_day = opened_day


# ================================================================
# INSURANCE POLICY
# ================================================================

class InsurancePolicy:
    """An insurance policy protecting against specific losses."""
    __slots__ = ('owner_name', 'policy_type', 'insured_value',
                 'premium_per_day', 'start_day', 'active')

    def __init__(self, owner_name: str, policy_type: str,
                 insured_value: float, start_day: int):
        self.owner_name = owner_name
        self.policy_type = policy_type  # cargo, property, life
        self.insured_value = insured_value
        self.premium_per_day = insured_value * INSURANCE_RATES.get(policy_type, 0.002)
        self.start_day = start_day
        self.active = True


# ================================================================
# INVESTMENT BOND
# ================================================================

class Bond:
    """An investment bond that pays periodic returns."""
    __slots__ = ('owner_name', 'bond_type', 'invested', 'yield_rate',
                 'start_day', 'duration', 'settlement_name', 'active')

    def __init__(self, owner_name: str, bond_type: str, invested: float,
                 settlement_name: str, start_day: int, duration: int = 30):
        self.owner_name = owner_name
        self.bond_type = bond_type
        self.invested = invested
        self.yield_rate = BOND_YIELDS.get(bond_type, 0.004)
        self.start_day = start_day
        self.duration = duration
        self.settlement_name = settlement_name
        self.active = True


# ================================================================
# BANKING SYSTEM
# ================================================================

class BankingSystem:
    """Manages all financial institutions, loans, deposits, insurance, and bonds."""

    def __init__(self):
        self.loans: List[Loan] = []
        self.deposits: List[DepositAccount] = []
        self.insurance: List[InsurancePolicy] = []
        self.bonds: List[Bond] = []
        self.financial_log: List[str] = []
        self._next_loan_id = 1
        self._update_timer = 0.0
        # Bank's gold reserves — funded by loan interest, insurance premiums,
        # and initial capitalization.  Loans are issued FROM reserves,
        # repayments go TO reserves, bond yields are paid FROM reserves.
        self._bank_reserves = 500.0  # initial capitalization

    def get_financial_policy(self, governance_style: str) -> dict:
        """Get the financial regulations for a governance style."""
        return FINANCIAL_POLICIES.get(governance_style,
                                      FINANCIAL_POLICIES["feudalism"])

    def request_loan(self, npc, amount: float, lender_type: str,
                     governance_style: str, day: int,
                     duration: int = 30) -> Optional[Loan]:
        """NPC requests a loan. Returns Loan if approved, None if denied."""
        policy = self.get_financial_policy(governance_style)

        # Check if banking is even allowed
        if not policy["banking_allowed"] and lender_type in ("royal_bank", "merchant_guild"):
            return None
        if not policy["loansharks_legal"] and lender_type == "loanshark":
            return None

        # Get interest rate (capped by usury law)
        rate_data = INTEREST_RATES.get(lender_type, INTEREST_RATES["moneylender"])
        rate = min(rate_data["loan"], policy["max_interest"])
        if rate <= 0 and lender_type != "loanshark":
            return None  # interest-free lending not profitable

        # Credit check
        credit = calc_credit_score(npc)
        max_loan = credit * MAX_LOAN_MULTIPLIER

        # Different lenders have different minimum credit requirements
        min_credit = {
            "royal_bank": 60,
            "merchant_guild": 40,
            "moneylender": 20,
            "loanshark": 0,  # anyone qualifies
        }
        if credit < min_credit.get(lender_type, 30):
            return None

        # Cap loan amount
        approved_amount = min(amount, max_loan)
        if approved_amount < MIN_LOAN_AMOUNT:
            return None

        # Loansharks charge extra for bad credit
        if lender_type == "loanshark" and credit < 30:
            rate *= 1.5  # penalty rate

        # Check existing debt load
        existing_debt = sum(l.remaining for l in self.loans
                          if l.borrower_name == npc.name and l.status == "active")
        if existing_debt > max_loan * 0.5:
            if lender_type != "loanshark":
                return None  # too much existing debt

        # Create loan
        loan_id = f"LOAN-{self._next_loan_id:04d}"
        self._next_loan_id += 1

        loan = Loan(loan_id, lender_type, rate_data["name"],
                   npc.name, approved_amount, rate, duration,
                   start_day=day)

        self.loans.append(loan)

        # Give gold to borrower FROM bank reserves (real economy)
        actual_loan = min(approved_amount, self._bank_reserves)
        if actual_loan <= 0:
            return None  # bank is broke, cannot issue loan
        self._bank_reserves -= actual_loan
        loan.principal = actual_loan  # adjust if bank couldn't cover full amount
        npc.npc_gold += actual_loan

        # Record in memory
        npc.add_memory("finance", f"Took a loan of {approved_amount:.0f}g from {rate_data['name']}", 3)

        # Record in ledger
        from game.systems.memory import ensure_life_ledger
        ledger = ensure_life_ledger(npc)
        ledger.record_milestone("loan_taken",
            f"Borrowed {approved_amount:.0f}g from {rate_data['name']} at {rate*100:.1f}%/day",
            day)

        self.financial_log.append(
            f"{npc.name} borrowed {approved_amount:.0f}g from {rate_data['name']}")

        return loan

    def open_deposit(self, npc, amount: float, institution_type: str,
                     day: int) -> Optional[DepositAccount]:
        """NPC deposits gold into a savings account."""
        if amount <= 0 or getattr(npc, 'npc_gold', 0) < amount:
            return None

        rate_data = INTEREST_RATES.get(institution_type, INTEREST_RATES["royal_bank"])
        account = DepositAccount(npc.name, institution_type,
                                amount, rate_data["deposit"], day)
        self.deposits.append(account)
        npc.npc_gold -= amount

        npc.add_memory("finance", f"Deposited {amount:.0f}g at {rate_data['name']}", 2)
        return account

    def buy_bond(self, npc, bond_type: str, amount: float,
                 settlement_name: str, day: int) -> Optional[Bond]:
        """NPC invests in a bond."""
        if amount <= 0 or getattr(npc, 'npc_gold', 0) < amount:
            return None

        bond = Bond(npc.name, bond_type, amount, settlement_name, day)
        self.bonds.append(bond)
        npc.npc_gold -= amount

        npc.add_memory("finance", f"Invested {amount:.0f}g in {bond_type}", 2)
        return bond

    def buy_insurance(self, npc, policy_type: str, insured_value: float,
                      day: int) -> Optional[InsurancePolicy]:
        """NPC buys an insurance policy."""
        policy = InsurancePolicy(npc.name, policy_type, insured_value, day)
        self.insurance.append(policy)

        npc.add_memory("finance", f"Bought {policy_type} insurance for {insured_value:.0f}g value", 1)
        return policy

    def update(self, dt: float, npcs: list, day: int, governance_style: str = "feudalism"):
        """Process daily financial updates."""
        self._update_timer += dt
        if self._update_timer < 30.0:  # process every 30 game seconds
            return
        self._update_timer = 0.0

        day_fraction = 30.0 / 600.0  # fraction of a day

        # Process loan payments
        npc_map = {n.name: n for n in npcs if n.alive}
        for loan in self.loans:
            if loan.status != "active":
                continue

            borrower = npc_map.get(loan.borrower_name)
            if not borrower:
                loan.status = "defaulted"
                continue

            # Daily payment due — gold flows FROM borrower TO bank reserves
            payment_due = loan.daily_payment * day_fraction
            if borrower.npc_gold >= payment_due:
                borrower.npc_gold -= payment_due
                self._bank_reserves += payment_due
                loan.make_payment(payment_due)
            else:
                # Can't pay — overdue
                loan.days_overdue += day_fraction
                if loan.days_overdue > 7:
                    loan.status = "defaulted"
                    borrower.add_memory("finance",
                        f"Defaulted on loan from {loan.lender_name}!", 4)

                    from game.systems.memory import ensure_life_ledger
                    ledger = ensure_life_ledger(borrower)
                    ledger.record_milestone("loan_defaulted",
                        f"Defaulted on {loan.principal:.0f}g loan from {loan.lender_name}",
                        day)

                    # Loanshark consequences
                    if loan.lender_type == "loanshark":
                        borrower.add_memory("danger",
                            f"The {loan.lender_name} is looking for me!", 4)
                    self.financial_log.append(
                        f"{borrower.name} defaulted on loan from {loan.lender_name}")

            # Check if fully repaid
            if loan.status == "repaid":
                if borrower:
                    borrower.add_memory("finance",
                        f"Fully repaid loan from {loan.lender_name}!", 3)
                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(borrower).record_milestone("loan_repaid",
                        f"Repaid {loan.principal:.0f}g loan from {loan.lender_name}", day)
                self.financial_log.append(
                    f"{loan.borrower_name} repaid loan from {loan.lender_name}")

        # Process deposit interest — paid from bank reserves
        for account in self.deposits:
            interest = account.balance * account.interest_rate * day_fraction
            actual_interest = min(interest, self._bank_reserves)
            if actual_interest > 0:
                self._bank_reserves -= actual_interest
                account.balance += actual_interest

        # Process bond yields — paid from the bank's reserves (gold pool)
        # The bank earns from loan interest, so bond yields are funded by
        # real economic activity, not conjured from nothing.
        for bond in self.bonds:
            if not bond.active:
                continue
            yield_amount = bond.invested * bond.yield_rate * day_fraction
            owner = npc_map.get(bond.owner_name)
            if owner:
                # Pay yield from bank reserves
                actual_yield = min(yield_amount, self._bank_reserves)
                if actual_yield > 0:
                    self._bank_reserves -= actual_yield
                    owner.npc_gold += actual_yield

            # Bond maturation
            days_held = day - bond.start_day
            if days_held >= bond.duration:
                bond.active = False
                if owner:
                    # Return principal from bank reserves
                    actual_return = min(bond.invested, self._bank_reserves)
                    if actual_return > 0:
                        self._bank_reserves -= actual_return
                        owner.npc_gold += actual_return
                    owner.add_memory("finance",
                        f"Bond matured! Got back {actual_return:.0f}g investment", 3)

        # Process insurance premiums — gold flows to bank reserves
        for policy in self.insurance:
            if not policy.active:
                continue
            owner = npc_map.get(policy.owner_name)
            if owner and owner.npc_gold >= policy.premium_per_day * day_fraction:
                premium = policy.premium_per_day * day_fraction
                owner.npc_gold -= premium
                self._bank_reserves += premium
            elif owner:
                policy.active = False  # can't pay premium, policy lapses

        # Auto-banking for wealthy NPCs (they naturally seek financial services)
        if random.random() < 0.01 * day_fraction:
            for npc in npcs:
                if not npc.alive:
                    continue
                gold = getattr(npc, 'npc_gold', 0)

                # Wealthy NPCs deposit excess gold
                if gold > 80 and not any(d.owner_name == npc.name for d in self.deposits):
                    if random.random() < get_tendency(npc, "fair_trade") * 0.3:
                        deposit_amount = gold * 0.3
                        self.open_deposit(npc, deposit_amount, "royal_bank", day)

                # Broke NPCs seek loans
                if gold < 3 and npc.needs.get("hunger", 100) < 40:
                    if not any(l.borrower_name == npc.name and l.status == "active"
                              for l in self.loans):
                        # Try legitimate lender first, then loanshark
                        for ltype in ["moneylender", "loanshark"]:
                            loan = self.request_loan(npc, 20, ltype,
                                                     governance_style, day, 14)
                            if loan:
                                break

    def get_npc_financial_summary(self, npc_name: str) -> dict:
        """Get financial summary for an NPC."""
        active_loans = [l for l in self.loans
                       if l.borrower_name == npc_name and l.status == "active"]
        deposits = [d for d in self.deposits if d.owner_name == npc_name]
        active_bonds = [b for b in self.bonds
                       if b.owner_name == npc_name and b.active]
        active_insurance = [p for p in self.insurance
                           if p.owner_name == npc_name and p.active]

        total_debt = sum(l.remaining for l in active_loans)
        total_deposits = sum(d.balance for d in deposits)
        total_invested = sum(b.invested for b in active_bonds)

        return {
            "loans": len(active_loans),
            "total_debt": total_debt,
            "deposits": total_deposits,
            "investments": total_invested,
            "insurance_policies": len(active_insurance),
            "net_worth_financial": total_deposits + total_invested - total_debt,
        }

    def get_financial_log(self) -> List[str]:
        log = list(self.financial_log)
        self.financial_log.clear()
        return log

    def get_system_report(self) -> str:
        """Get summary of the entire banking system."""
        active_loans = sum(1 for l in self.loans if l.status == "active")
        total_lending = sum(l.remaining for l in self.loans if l.status == "active")
        total_deposits = sum(d.balance for d in self.deposits)
        total_invested = sum(b.invested for b in self.bonds if b.active)
        defaults = sum(1 for l in self.loans if l.status == "defaulted")

        return (f"Banking: {active_loans} active loans ({total_lending:.0f}g outstanding), "
                f"{len(self.deposits)} deposits ({total_deposits:.0f}g), "
                f"{sum(1 for b in self.bonds if b.active)} bonds ({total_invested:.0f}g), "
                f"{defaults} defaults")

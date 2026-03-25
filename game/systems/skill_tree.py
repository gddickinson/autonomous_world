"""
Skill tree system -- specialization paths for the player.

Four trees: Combat, Magic, Survival, Social.
Each tree has two branches of 3 nodes each.
Nodes cost 1 skill point (earned every 2 levels).
Prerequisites: must unlock parent node first.

Opened with O key (shown in character sheet area).
"""

import pygame
from typing import Dict, List, Optional, Tuple
from game.settings import *


# ================================================================
# SKILL TREE DEFINITIONS
# ================================================================

class SkillNode:
    """A single node in the skill tree."""
    __slots__ = ("name", "tree", "branch", "tier", "parent",
                 "description", "bonus_type", "bonus_value")

    def __init__(self, name: str, tree: str, branch: int, tier: int,
                 parent: Optional[str], description: str,
                 bonus_type: str, bonus_value):
        self.name = name
        self.tree = tree          # "combat", "magic", "survival", "social"
        self.branch = branch      # 0 = left branch, 1 = right branch
        self.tier = tier          # 0, 1, 2 (depth)
        self.parent = parent      # name of prerequisite node or None
        self.description = description
        self.bonus_type = bonus_type   # "passive", "ability", "stat"
        self.bonus_value = bonus_value # dict of effects


# All nodes keyed by name
SKILL_NODES: Dict[str, SkillNode] = {}


def _register(name, tree, branch, tier, parent, desc, btype, bval):
    SKILL_NODES[name] = SkillNode(name, tree, branch, tier, parent,
                                   desc, btype, bval)


# ======================== COMBAT TREE ========================
# Branch 0: Offensive
_register("Power Attack", "combat", 0, 0, None,
          "+15% melee damage",
          "passive", {"damage_mult": 0.15})
_register("Cleave", "combat", 0, 1, "Power Attack",
          "Attacks hit one adjacent enemy too",
          "ability", {"ability": "cleave", "cooldown": 8.0})
_register("Whirlwind Strike", "combat", 0, 2, "Cleave",
          "AoE spin attack hitting all nearby foes",
          "ability", {"ability": "whirlwind_strike", "cooldown": 15.0})

# Branch 1: Defensive
_register("Parry", "combat", 1, 0, None,
          "+10% chance to block melee attacks",
          "passive", {"block_chance": 0.10})
_register("Riposte", "combat", 1, 1, "Parry",
          "Counter-attack after a successful block",
          "ability", {"ability": "riposte", "cooldown": 6.0})
_register("Counter-strike", "combat", 1, 2, "Riposte",
          "Riposte deals double damage and stuns",
          "passive", {"riposte_damage_mult": 2.0, "riposte_stun": 1.5})

# ======================== MAGIC TREE ========================
# Branch 0: Spell Power
_register("Spell Focus", "magic", 0, 0, None,
          "+15% spell damage",
          "passive", {"spell_damage_mult": 0.15})
_register("Metamagic", "magic", 0, 1, "Spell Focus",
          "Spells cost 20% less mana",
          "passive", {"mana_cost_reduction": 0.20})
_register("Arcane Mastery", "magic", 0, 2, "Metamagic",
          "Unlock 2 extra spell slots and +25% spell damage",
          "passive", {"extra_spell_slots": 2, "spell_damage_mult": 0.25})

# Branch 1: Mana & Recovery
_register("Mana Regen", "magic", 1, 0, None,
          "+30% mana regeneration rate",
          "passive", {"mana_regen_mult": 0.30})
_register("Deep Reserves", "magic", 1, 1, "Mana Regen",
          "+50 maximum mana",
          "passive", {"max_mana_bonus": 50})
_register("Arcane Shield", "magic", 1, 2, "Deep Reserves",
          "Spend mana to absorb damage (1 mana = 2 HP)",
          "ability", {"ability": "arcane_shield", "cooldown": 20.0})

# ======================== SURVIVAL TREE ========================
# Branch 0: Hunting
_register("Tracking", "survival", 0, 0, None,
          "See creature footprints and trails",
          "passive", {"tracking_vision": True})
_register("Hunter's Mark", "survival", 0, 1, "Tracking",
          "Mark a target for +20% damage against it",
          "ability", {"ability": "hunters_mark", "cooldown": 10.0})
_register("Beast Mastery", "survival", 0, 2, "Hunter's Mark",
          "Tame wild creatures as companions",
          "ability", {"ability": "beast_tame", "cooldown": 30.0})

# Branch 1: Herbalism
_register("Herbalism", "survival", 1, 0, None,
          "Gather 50% more herbs and identify plants",
          "passive", {"herb_gather_bonus": 0.50})
_register("Alchemy Adept", "survival", 1, 1, "Herbalism",
          "Potions are 30% more effective",
          "passive", {"potion_effectiveness": 0.30})
_register("Poison Craft", "survival", 1, 2, "Alchemy Adept",
          "Coat weapons with poison (DoT on hit)",
          "ability", {"ability": "poison_weapon", "cooldown": 25.0})

# ======================== SOCIAL TREE ========================
# Branch 0: Trade
_register("Haggle", "social", 0, 0, None,
          "10% better buy/sell prices",
          "passive", {"trade_price_bonus": 0.10})
_register("Trade Routes", "social", 0, 1, "Haggle",
          "Unlock regional trade goods and 15% more gold from quests",
          "passive", {"quest_gold_bonus": 0.15, "trade_routes": True})
_register("Merchant Prince", "social", 0, 2, "Trade Routes",
          "25% better prices, can open a shop",
          "passive", {"trade_price_bonus": 0.25, "can_own_shop": True})

# Branch 1: Influence
_register("Intimidation", "social", 1, 0, None,
          "+15% intimidation success, enemies may flee",
          "passive", {"intimidation_bonus": 0.15})
_register("Command", "social", 1, 1, "Intimidation",
          "Order NPCs to perform actions",
          "ability", {"ability": "command_npc", "cooldown": 15.0})
_register("Leadership", "social", 1, 2, "Command",
          "Lead up to 4 companions; party gains +10% stats",
          "passive", {"max_companions": 4, "party_stat_bonus": 0.10})


# ================================================================
# TREE NAMES AND LAYOUT
# ================================================================

TREE_NAMES = ["combat", "magic", "survival", "social"]
TREE_DISPLAY = {
    "combat":   "Combat",
    "magic":    "Magic",
    "survival": "Survival",
    "social":   "Social",
}

TREE_COLORS = {
    "combat":   (200, 80, 80),
    "magic":    (80, 120, 220),
    "survival": (80, 180, 80),
    "social":   (200, 180, 60),
}


def get_tree_nodes(tree: str) -> List[SkillNode]:
    """Return all nodes for a given tree, sorted by branch then tier."""
    nodes = [n for n in SKILL_NODES.values() if n.tree == tree]
    nodes.sort(key=lambda n: (n.branch, n.tier))
    return nodes


# ================================================================
# PLAYER SKILL TREE STATE
# ================================================================

class PlayerSkillTree:
    """Tracks which nodes a player has unlocked and manages skill points."""

    def __init__(self):
        self.unlocked: set = set()     # set of node names
        self.skill_points: int = 0     # available points to spend

    def points_for_level(self, level: int) -> int:
        """Total skill points earned by this level (1 per 2 levels)."""
        return level // 2

    def sync_points(self, player_level: int):
        """Ensure skill_points reflects the player's level minus spent."""
        total_earned = self.points_for_level(player_level)
        spent = len(self.unlocked)
        self.skill_points = max(0, total_earned - spent)

    def can_unlock(self, node_name: str) -> Tuple[bool, str]:
        """Check if a node can be unlocked."""
        if node_name in self.unlocked:
            return False, "Already unlocked"
        if self.skill_points <= 0:
            return False, "No skill points available"
        node = SKILL_NODES.get(node_name)
        if not node:
            return False, "Unknown node"
        if node.parent and node.parent not in self.unlocked:
            return False, f"Requires {node.parent}"
        return True, "OK"

    def unlock(self, node_name: str, player) -> Tuple[bool, str]:
        """Unlock a node and apply its bonuses."""
        can, reason = self.can_unlock(node_name)
        if not can:
            return False, reason

        self.unlocked.add(node_name)
        self.skill_points -= 1
        _apply_node_bonus(node_name, player)
        return True, f"Unlocked {node_name}!"

    def get_all_bonuses(self) -> Dict[str, float]:
        """Aggregate all passive bonuses from unlocked nodes."""
        bonuses = {}
        for name in self.unlocked:
            node = SKILL_NODES.get(name)
            if node and node.bonus_type in ("passive", "stat"):
                for k, v in node.bonus_value.items():
                    if isinstance(v, (int, float)):
                        bonuses[k] = bonuses.get(k, 0) + v
                    else:
                        bonuses[k] = v  # bool or string
        return bonuses


def _apply_node_bonus(node_name: str, player):
    """Apply immediate effects when a node is unlocked."""
    node = SKILL_NODES.get(node_name)
    if not node:
        return

    bv = node.bonus_value

    # Stat bonuses
    if "max_mana_bonus" in bv and hasattr(player, 'max_mana'):
        player.max_mana += bv["max_mana_bonus"]
        player.mana = min(player.mana + bv["max_mana_bonus"], player.max_mana)

    if "extra_spell_slots" in bv and hasattr(player, 'spell_slots'):
        for i in range(len(player.spell_slots)):
            player.spell_slots[i] += bv["extra_spell_slots"]


def init_player_skill_tree(player):
    """Attach a PlayerSkillTree to the player if not present."""
    if not hasattr(player, 'skill_tree'):
        player.skill_tree = PlayerSkillTree()
    player.skill_tree.sync_points(player.level)


# ================================================================
# SKILL TREE UI
# ================================================================

class SkillTreeUI:
    """Visual skill tree panel. Opened with O key."""

    def __init__(self):
        self.active = False
        self.tree_idx = 0      # which tree tab is selected
        self.node_idx = 0      # which node in current tree is highlighted
        self.message = ""
        self.msg_timer = 0.0

    def toggle(self):
        self.active = not self.active
        if self.active:
            self.node_idx = 0
            self.message = ""

    def close(self):
        self.active = False

    def update(self, dt: float):
        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0:
                self.message = ""

    def handle_key(self, key: int, player) -> bool:
        """Handle input. Returns True if consumed."""
        if not self.active:
            return False

        if key == pygame.K_ESCAPE:
            self.close()
            return True

        # Tab switching
        if key == pygame.K_LEFT:
            self.tree_idx = (self.tree_idx - 1) % len(TREE_NAMES)
            self.node_idx = 0
            return True
        if key == pygame.K_RIGHT:
            self.tree_idx = (self.tree_idx + 1) % len(TREE_NAMES)
            self.node_idx = 0
            return True

        tree = TREE_NAMES[self.tree_idx]
        nodes = get_tree_nodes(tree)
        if not nodes:
            return True

        # Node navigation
        if key in (pygame.K_UP, pygame.K_w):
            self.node_idx = max(0, self.node_idx - 1)
            return True
        if key in (pygame.K_DOWN, pygame.K_s):
            self.node_idx = min(len(nodes) - 1, self.node_idx + 1)
            return True

        # Unlock node
        if key in (pygame.K_RETURN, pygame.K_e):
            if not hasattr(player, 'skill_tree'):
                init_player_skill_tree(player)
            player.skill_tree.sync_points(player.level)
            if 0 <= self.node_idx < len(nodes):
                node = nodes[self.node_idx]
                ok, msg = player.skill_tree.unlock(node.name, player)
                self.message = msg
                self.msg_timer = 3.0
            return True

        return True

    def draw(self, screen: pygame.Surface, player):
        """Draw the skill tree panel."""
        if not self.active:
            return

        if not hasattr(player, 'skill_tree'):
            init_player_skill_tree(player)
        player.skill_tree.sync_points(player.level)
        st = player.skill_tree

        font_sm = pygame.font.SysFont("monospace", 13)
        font_md = pygame.font.SysFont("monospace", 16)
        font_lg = pygame.font.SysFont("monospace", 22)

        pw, ph = 650, 480
        px = SCREEN_WIDTH // 2 - pw // 2
        py = SCREEN_HEIGHT // 2 - ph // 2

        # Background
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 230))
        screen.blit(bg, (px, py))
        pygame.draw.rect(screen, (80, 120, 180), (px, py, pw, ph), 2)

        # Title
        title = font_lg.render(
            f"Skill Tree  [O to close]   Points: {st.skill_points}", True, (200, 220, 255))
        screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 8))

        # Tree tabs
        tab_y = py + 38
        tab_x = px + 40
        for i, tname in enumerate(TREE_NAMES):
            color = TREE_COLORS[tname] if i == self.tree_idx else (100, 100, 120)
            label = font_md.render(TREE_DISPLAY[tname], True, color)
            screen.blit(label, (tab_x, tab_y))
            if i == self.tree_idx:
                pygame.draw.line(screen, color,
                                 (tab_x, tab_y + 18), (tab_x + label.get_width(), tab_y + 18))
            tab_x += label.get_width() + 40

        # Divider
        div_y = tab_y + 26
        pygame.draw.line(screen, (60, 60, 80), (px + 5, div_y), (px + pw - 5, div_y))

        # Draw tree
        tree = TREE_NAMES[self.tree_idx]
        tree_color = TREE_COLORS[tree]
        nodes = get_tree_nodes(tree)

        # Layout: two branches side by side, 3 tiers each
        branch_x = {0: px + 80, 1: px + pw // 2 + 30}
        node_w, node_h = 200, 50
        start_y = div_y + 20
        tier_spacing = 70

        # Draw connecting lines first
        for node in nodes:
            if node.parent:
                parent_node = SKILL_NODES.get(node.parent)
                if parent_node:
                    p_cx = branch_x[parent_node.branch] + node_w // 2
                    p_cy = start_y + parent_node.tier * tier_spacing + node_h
                    c_cx = branch_x[node.branch] + node_w // 2
                    c_cy = start_y + node.tier * tier_spacing
                    line_color = (60, 80, 60) if node.name not in st.unlocked else tree_color
                    pygame.draw.line(screen, line_color, (p_cx, p_cy), (c_cx, c_cy), 2)

        # Branch labels
        for b, label_text in enumerate(["Branch A", "Branch B"]):
            lbl = font_sm.render(label_text, True, (100, 100, 130))
            screen.blit(lbl, (branch_x[b] + node_w // 2 - lbl.get_width() // 2,
                              start_y - 16))

        # Draw nodes
        for idx, node in enumerate(nodes):
            nx = branch_x[node.branch]
            ny = start_y + node.tier * tier_spacing

            unlocked = node.name in st.unlocked
            can_unlock, _ = st.can_unlock(node.name)
            selected = idx == self.node_idx

            # Node box colors
            if unlocked:
                box_color = tree_color
                text_color = (255, 255, 255)
            elif can_unlock:
                box_color = (60, 70, 90)
                text_color = (200, 210, 230)
            else:
                box_color = (35, 35, 50)
                text_color = (100, 100, 120)

            # Selection highlight
            if selected:
                sel_rect = (nx - 3, ny - 3, node_w + 6, node_h + 6)
                pygame.draw.rect(screen, (200, 200, 255), sel_rect, 2)

            # Box
            pygame.draw.rect(screen, box_color, (nx, ny, node_w, node_h))
            pygame.draw.rect(screen, (80, 90, 110), (nx, ny, node_w, node_h), 1)

            # Node name
            name_surf = font_sm.render(node.name, True, text_color)
            screen.blit(name_surf, (nx + node_w // 2 - name_surf.get_width() // 2, ny + 5))

            # Brief description (truncated)
            desc = node.description
            if len(desc) > 28:
                desc = desc[:26] + ".."
            desc_surf = font_sm.render(desc, True,
                                        (180, 180, 180) if unlocked else (80, 80, 100))
            screen.blit(desc_surf, (nx + node_w // 2 - desc_surf.get_width() // 2, ny + 22))

            # Status icon
            if unlocked:
                icon = font_sm.render("[*]", True, (100, 255, 100))
            elif can_unlock:
                icon = font_sm.render("[+]", True, (200, 200, 100))
            else:
                icon = font_sm.render("[-]", True, (80, 80, 80))
            screen.blit(icon, (nx + node_w // 2 - icon.get_width() // 2, ny + 36))

        # Detail panel for selected node (bottom area)
        detail_y = start_y + 3 * tier_spacing + 15
        if nodes and 0 <= self.node_idx < len(nodes):
            sel_node = nodes[self.node_idx]
            pygame.draw.line(screen, (60, 60, 80),
                             (px + 5, detail_y - 5), (px + pw - 5, detail_y - 5))

            # Full description
            desc_surf = font_md.render(sel_node.name, True, tree_color)
            screen.blit(desc_surf, (px + 15, detail_y))
            detail_y += 20
            screen.blit(font_sm.render(sel_node.description, True, (190, 200, 210)),
                         (px + 15, detail_y))
            detail_y += 16

            # Bonus details
            bonus_parts = []
            for k, v in sel_node.bonus_value.items():
                if isinstance(v, bool):
                    bonus_parts.append(k.replace("_", " ").title())
                elif isinstance(v, float):
                    bonus_parts.append(f"{k}: +{int(v*100)}%")
                elif isinstance(v, int):
                    bonus_parts.append(f"{k}: +{v}")
                else:
                    bonus_parts.append(f"{k}: {v}")
            if bonus_parts:
                bonus_text = "  |  ".join(bonus_parts)
                screen.blit(font_sm.render(bonus_text, True, (160, 180, 160)),
                             (px + 15, detail_y))
            detail_y += 16

            # Prerequisite info
            if sel_node.parent:
                met = sel_node.parent in st.unlocked
                pre_color = (100, 220, 100) if met else (220, 100, 100)
                screen.blit(font_sm.render(f"Requires: {sel_node.parent}", True, pre_color),
                             (px + 15, detail_y))

        # Status message
        if self.message:
            msg_color = (140, 220, 140) if "Unlocked" in self.message else (220, 140, 140)
            msg_surf = font_md.render(self.message, True, msg_color)
            screen.blit(msg_surf, (px + pw // 2 - msg_surf.get_width() // 2, py + ph - 30))

        # Controls
        hints = font_sm.render("W/S: select  Enter: unlock  <-/->: tree  Esc: close",
                                True, (90, 90, 110))
        screen.blit(hints, (px + 10, py + ph - 14))

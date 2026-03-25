"""Co-op quest synchronization over multiplayer.

When the host accepts a quest, a GAME_EVENT with event_type="quest_accept"
is broadcast so all connected players see the same quest objective.
Kill progress and completion are synced the same way.

Usage (from main game loop):
    from game.network.coop_quests import broadcast_quest_accept, handle_quest_event

    # On host accepting a quest:
    broadcast_quest_accept(server, quest)

    # In _handle_net_message for GAME_EVENT:
    handle_quest_event(game, data)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.network.server import GameServer
    from game.systems.quests import Quest


# ── Broadcast helpers (called by host) ────────────────────────────

def broadcast_quest_accept(server: "GameServer", quest: "Quest"):
    """Notify all clients that a quest was accepted."""
    server.send_event(
        "quest_accept",
        f"Quest accepted: {quest.title} — {quest.description}",
    )


def broadcast_quest_progress(server: "GameServer", quest: "Quest",
                             killer_name: str = ""):
    """Notify all clients of quest kill/progress update."""
    desc = f"Quest progress: {quest.title} ({quest.progress}/{quest.target_count})"
    if killer_name:
        desc = f"{killer_name} advanced quest — {desc}"
    server.send_event("quest_progress", desc)


def broadcast_quest_complete(server: "GameServer", quest: "Quest"):
    """Notify all clients that a quest was completed."""
    server.send_event(
        "quest_complete",
        f"Quest complete: {quest.title}!",
    )


# ── Client-side handler ──────────────────────────────────────────

def handle_quest_event(game, data: dict):
    """Handle a quest-related GAME_EVENT on the receiving side.

    Called from _handle_net_message when event_type starts with 'quest_'.
    Updates the local quest system so both players share progress.

    Args:
        game: The Game instance.
        data: GAME_EVENT data dict with 'event_type' and 'description'.
    """
    event_type = data.get("event_type", "")

    if event_type == "quest_accept":
        desc = data.get("description", "")
        game.notifications.add(desc, 5.0, (100, 220, 180))

    elif event_type == "quest_progress":
        desc = data.get("description", "")
        game.notifications.add(desc, 3.0, (200, 200, 100))
        # If we have matching active quests, bump their progress too
        _sync_quest_progress(game, data)

    elif event_type == "quest_complete":
        desc = data.get("description", "")
        game.notifications.add(desc, 5.0, (100, 255, 100))


def _sync_quest_progress(game, data: dict):
    """Try to bump local quest progress to match the broadcast.

    Parses the description for quest title and progress numbers, then
    updates the matching active quest if found.
    """
    desc = data.get("description", "")
    # Description format: "... Quest progress: TITLE (N/M)"
    if "Quest progress:" not in desc:
        return
    try:
        after = desc.split("Quest progress:")[-1].strip()
        # "TITLE (N/M)"
        paren_start = after.rfind("(")
        if paren_start < 0:
            return
        title = after[:paren_start].strip()
        nums = after[paren_start + 1:].rstrip(")")
        progress_str, _ = nums.split("/")
        new_progress = int(progress_str)

        if not hasattr(game, "quest_sys"):
            return
        for q in game.quest_sys.active_quests:
            if q.title == title and new_progress > q.progress:
                q.progress = new_progress
                break
    except (ValueError, IndexError):
        pass

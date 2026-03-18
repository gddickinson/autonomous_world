"""Simulation System Interface — maps where functionality lives.

The SimulationManager (simulation.py) was split into focused modules:

simulation.py        — SimulationManager class, __init__, update() loop (~500 lines)
sim_combat.py        — _threat_response, _npc_combat_tick (~350 lines)
sim_conversations.py — Conversation, _update_conversations, _spread_information,
                       _start_talk, _start_trade, _start_persuade,
                       _npc_teach, _npc_barter (~400 lines)
sim_needs.py         — _decay_needs, _check_critical_needs,
                       _get_sleep_quality, _get_sleep_safety (~300 lines)
sim_actions.py       — _execute_action, _move_to_forage, _move_npc,
                       _start_fight, _give_item, _find_npc, _find_zone_for_npc,
                       _update_action_progress, _update_player_tasks,
                       _complete_action (~900 lines)
sim_decisions.py     — _request_decisions, _poll_decisions,
                       _apply_decision, _parse_decision (~200 lines)
sim_events.py        — WorldEvent, _update_events, _spawn_event (~100 lines)
sim_daily.py         — _update_daily_life, _update_npc_economic_awareness,
                       _handle_npc_death, _handle_npc_death_from_disease (~400 lines)

Each module defines a mixin class (e.g., SimCombatMixin) that SimulationManager
inherits from. All state lives on `self` (the SimulationManager instance).

To find a method, check this file or use:
    grep -rn "def method_name" game/systems/sim_*.py
"""

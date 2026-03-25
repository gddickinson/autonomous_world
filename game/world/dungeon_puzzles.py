"""Puzzle room generation and state management for dungeons.

Three puzzle types:
  - Lever Puzzle: pull 3 levers in the correct order to unlock a door.
  - Pressure Plate Puzzle: step on plates in sequence to open a chest.
  - Riddle Door: answer a multiple-choice riddle to proceed.

Each puzzle room stores its state in a PuzzleState dataclass so the
game can track progress per-room.
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import numpy as np

from game.settings import (
    FLOOR, WALL, DOOR, CHEST, LOCKED_DOOR,
    LEVER, PRESSURE_PLATE, RIDDLE_DOOR,
)
from game.world.dungeon_bsp import Rect

# ================================================================
# PUZZLE TYPES
# ================================================================

PUZZLE_LEVER = "lever"
PUZZLE_PRESSURE_PLATE = "pressure_plate"
PUZZLE_RIDDLE = "riddle"

PUZZLE_TYPES = [PUZZLE_LEVER, PUZZLE_PRESSURE_PLATE, PUZZLE_RIDDLE]

# ================================================================
# RIDDLE DATABASE
# ================================================================

RIDDLES = [
    {
        "text": "I have cities but no houses, forests but no trees, "
                "water but no fish. What am I?",
        "choices": ["A map", "A painting", "A dream", "A ghost"],
        "answer": 0,
    },
    {
        "text": "The more you take, the more you leave behind. "
                "What am I?",
        "choices": ["Footsteps", "Shadows", "Memories", "Gold"],
        "answer": 0,
    },
    {
        "text": "I speak without a mouth and hear without ears. "
                "I have no body, but I come alive with the wind.",
        "choices": ["A flag", "An echo", "A ghost", "Fire"],
        "answer": 1,
    },
    {
        "text": "What has keys but can't open locks?",
        "choices": ["A locksmith", "A piano", "A jailer", "A map"],
        "answer": 1,
    },
    {
        "text": "I am not alive, but I grow; I don't have lungs, "
                "but I need air. What am I?",
        "choices": ["A crystal", "Mold", "Fire", "A shadow"],
        "answer": 2,
    },
    {
        "text": "What can travel around the world while staying "
                "in a corner?",
        "choices": ["A spider", "A stamp", "A snail", "Wind"],
        "answer": 1,
    },
]


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class PuzzleState:
    """Runtime state for a single puzzle room."""
    puzzle_type: str
    room_index: int
    solved: bool = False
    # Lever puzzle
    correct_order: List[int] = field(default_factory=list)
    levers_pulled: List[int] = field(default_factory=list)
    lever_positions: List[Tuple[int, int]] = field(default_factory=list)
    # Pressure plate puzzle
    plate_sequence: List[int] = field(default_factory=list)
    plates_stepped: List[int] = field(default_factory=list)
    plate_positions: List[Tuple[int, int]] = field(default_factory=list)
    # Riddle puzzle
    riddle: Optional[Dict] = None
    riddle_door_pos: Tuple[int, int] = (0, 0)
    # Rewards
    reward_pos: Tuple[int, int] = (0, 0)
    # Fail penalty
    fail_spawn_pos: Tuple[int, int] = (0, 0)

    def reset(self) -> None:
        """Reset interactive state (not the puzzle layout)."""
        self.levers_pulled.clear()
        self.plates_stepped.clear()


# ================================================================
# PUZZLE INTERACTION
# ================================================================

def interact_lever(state: PuzzleState, lever_index: int) -> Dict:
    """Player pulls a lever. Returns result dict."""
    if state.solved:
        return {"result": "already_solved"}

    state.levers_pulled.append(lever_index)

    if len(state.levers_pulled) == len(state.correct_order):
        if state.levers_pulled == state.correct_order:
            state.solved = True
            return {"result": "solved", "reward_pos": state.reward_pos}
        else:
            state.levers_pulled.clear()
            return {"result": "failed", "spawn_pos": state.fail_spawn_pos}

    return {"result": "partial",
            "pulled": len(state.levers_pulled),
            "total": len(state.correct_order)}


def interact_pressure_plate(state: PuzzleState,
                            plate_index: int) -> Dict:
    """Player steps on a pressure plate. Returns result dict."""
    if state.solved:
        return {"result": "already_solved"}

    expected_idx = len(state.plates_stepped)
    if expected_idx < len(state.plate_sequence):
        if state.plate_sequence[expected_idx] == plate_index:
            state.plates_stepped.append(plate_index)
            if len(state.plates_stepped) == len(state.plate_sequence):
                state.solved = True
                return {"result": "solved",
                        "reward_pos": state.reward_pos}
            return {"result": "partial",
                    "stepped": len(state.plates_stepped),
                    "total": len(state.plate_sequence)}
        else:
            state.plates_stepped.clear()
            return {"result": "wrong_plate"}

    return {"result": "error"}


def interact_riddle(state: PuzzleState, choice: int) -> Dict:
    """Player answers a riddle. Returns result dict."""
    if state.solved:
        return {"result": "already_solved"}

    if state.riddle is None:
        return {"result": "error"}

    if choice == state.riddle["answer"]:
        state.solved = True
        return {"result": "solved", "door_pos": state.riddle_door_pos}
    else:
        return {"result": "failed", "spawn_pos": state.fail_spawn_pos,
                "damage": 15}


# ================================================================
# ROOM GENERATION
# ================================================================

def place_lever_puzzle(tiles: np.ndarray, rect: Rect,
                       rng: random.Random,
                       room_index: int) -> PuzzleState:
    """Place a 3-lever puzzle in a room. Returns PuzzleState."""
    # Place 3 levers along the back wall
    lever_positions = []
    spacing = max(1, (rect.w - 4) // 4)
    for i in range(3):
        lx = rect.x + 2 + i * spacing
        ly = rect.y + 1
        if (0 <= ly < tiles.shape[0] and 0 <= lx < tiles.shape[1]
                and tiles[ly, lx] == FLOOR):
            tiles[ly, lx] = LEVER
            lever_positions.append((lx, ly))

    # Locked door at the opposite end
    dx = rect.cx
    dy = rect.y + rect.h - 1
    if 0 <= dy < tiles.shape[0] and 0 <= dx < tiles.shape[1]:
        tiles[dy, dx] = LOCKED_DOOR

    # Correct order is a random permutation of [0, 1, 2]
    order = list(range(len(lever_positions)))
    rng.shuffle(order)

    return PuzzleState(
        puzzle_type=PUZZLE_LEVER,
        room_index=room_index,
        correct_order=order,
        lever_positions=lever_positions,
        reward_pos=(dx, dy),
        fail_spawn_pos=(rect.cx, rect.cy),
    )


def place_pressure_plate_puzzle(tiles: np.ndarray, rect: Rect,
                                rng: random.Random,
                                room_index: int) -> PuzzleState:
    """Place a pressure plate sequence puzzle. Returns PuzzleState."""
    plate_positions = []
    # Place 4-5 plates in a pattern
    num_plates = min(5, max(3, (rect.w - 4) // 2))
    for i in range(num_plates):
        px = rect.x + 2 + (i * (rect.w - 4)) // max(1, num_plates - 1)
        py = rect.y + rect.h // 2 + (i % 2)
        if (0 <= py < tiles.shape[0] and 0 <= px < tiles.shape[1]
                and tiles[py, px] == FLOOR):
            tiles[py, px] = PRESSURE_PLATE
            plate_positions.append((px, py))

    # Chest reward at centre back
    cx, cy = rect.cx, rect.y + 1
    if 0 <= cy < tiles.shape[0] and 0 <= cx < tiles.shape[1]:
        tiles[cy, cx] = CHEST

    # Sequence is a random permutation
    seq = list(range(len(plate_positions)))
    rng.shuffle(seq)

    return PuzzleState(
        puzzle_type=PUZZLE_PRESSURE_PLATE,
        room_index=room_index,
        plate_sequence=seq,
        plate_positions=plate_positions,
        reward_pos=(cx, cy),
        fail_spawn_pos=(rect.cx, rect.cy),
    )


def place_riddle_door(tiles: np.ndarray, rect: Rect,
                      rng: random.Random,
                      room_index: int) -> PuzzleState:
    """Place a riddle door puzzle. Returns PuzzleState."""
    # Riddle door blocks the exit
    dx = rect.cx
    dy = rect.y + rect.h - 1
    if 0 <= dy < tiles.shape[0] and 0 <= dx < tiles.shape[1]:
        tiles[dy, dx] = RIDDLE_DOOR

    riddle = rng.choice(RIDDLES).copy()

    return PuzzleState(
        puzzle_type=PUZZLE_RIDDLE,
        room_index=room_index,
        riddle=riddle,
        riddle_door_pos=(dx, dy),
        reward_pos=(rect.cx, rect.y + 1),
        fail_spawn_pos=(rect.cx, rect.cy),
    )


def generate_puzzle_room(tiles: np.ndarray, rect: Rect,
                         rng: random.Random,
                         room_index: int) -> PuzzleState:
    """Pick a random puzzle type and generate it in the room."""
    puzzle_type = rng.choice(PUZZLE_TYPES)
    if puzzle_type == PUZZLE_LEVER:
        return place_lever_puzzle(tiles, rect, rng, room_index)
    elif puzzle_type == PUZZLE_PRESSURE_PLATE:
        return place_pressure_plate_puzzle(tiles, rect, rng, room_index)
    else:
        return place_riddle_door(tiles, rect, rng, room_index)

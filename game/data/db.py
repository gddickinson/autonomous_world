"""
SQLite persistence layer for game state, NPC memories, and relationships.
Memories survive game restarts so NPCs remember the player between sessions.
"""

import sqlite3
import json
import os
import time
from typing import List, Dict, Optional, Any, Tuple


class GameDB:
    """SQLite database for persistent game state."""

    def __init__(self, db_path: str = "data/gameworld.db"):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_name TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 1,
                timestamp REAL NOT NULL,
                game_day INTEGER DEFAULT 1,
                UNIQUE(npc_name, content)
            );
            CREATE INDEX IF NOT EXISTS idx_memories_npc ON memories(npc_name);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);

            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                trust INTEGER DEFAULT 0,
                last_interaction REAL,
                notes TEXT DEFAULT '',
                UNIQUE(npc_name, target_name)
            );
            CREATE INDEX IF NOT EXISTS idx_rel_npc ON relationships(npc_name);

            CREATE TABLE IF NOT EXISTS world_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_name TEXT NOT NULL,
                info TEXT NOT NULL,
                learned_at REAL,
                source TEXT DEFAULT '',
                UNIQUE(npc_name, info)
            );

            CREATE TABLE IF NOT EXISTS world_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS tile_modifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                old_type INTEGER,
                new_type INTEGER NOT NULL,
                modified_by TEXT DEFAULT '',
                timestamp REAL,
                UNIQUE(x, y)
            );

            CREATE TABLE IF NOT EXISTS player_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ---- MEMORIES ----

    def save_memory(self, npc_name: str, memory_type: str, content: str,
                    importance: int = 1, game_day: int = 1):
        try:
            self.conn.execute(
                """INSERT OR REPLACE INTO memories (npc_name, memory_type, content, importance, timestamp, game_day)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (npc_name, memory_type, content, importance, time.time(), game_day)
            )
            self.conn.commit()
        except sqlite3.Error:
            pass

    def get_memories(self, npc_name: str, limit: int = 20,
                     memory_type: str = None) -> List[Dict]:
        if memory_type:
            rows = self.conn.execute(
                """SELECT * FROM memories WHERE npc_name = ? AND memory_type = ?
                   ORDER BY importance DESC, timestamp DESC LIMIT ?""",
                (npc_name, memory_type, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT * FROM memories WHERE npc_name = ?
                   ORDER BY importance DESC, timestamp DESC LIMIT ?""",
                (npc_name, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def search_memories(self, npc_name: str, keyword: str, limit: int = 10) -> List[Dict]:
        rows = self.conn.execute(
            """SELECT * FROM memories WHERE npc_name = ? AND content LIKE ?
               ORDER BY importance DESC, timestamp DESC LIMIT ?""",
            (npc_name, f"%{keyword}%", limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_npc_memories_count(self) -> Dict[str, int]:
        rows = self.conn.execute(
            "SELECT npc_name, COUNT(*) as cnt FROM memories GROUP BY npc_name"
        ).fetchall()
        return {r["npc_name"]: r["cnt"] for r in rows}

    # ---- RELATIONSHIPS ----

    def save_relationship(self, npc_name: str, target_name: str,
                         trust: int, notes: str = ""):
        self.conn.execute(
            """INSERT OR REPLACE INTO relationships (npc_name, target_name, trust, last_interaction, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (npc_name, target_name, trust, time.time(), notes)
        )
        self.conn.commit()

    def get_relationships(self, npc_name: str) -> Dict[str, int]:
        rows = self.conn.execute(
            "SELECT target_name, trust FROM relationships WHERE npc_name = ?",
            (npc_name,)
        ).fetchall()
        return {r["target_name"]: r["trust"] for r in rows}

    def get_friends(self, npc_name: str, min_trust: int = 20) -> List[str]:
        rows = self.conn.execute(
            "SELECT target_name FROM relationships WHERE npc_name = ? AND trust >= ? ORDER BY trust DESC",
            (npc_name, min_trust)
        ).fetchall()
        return [r["target_name"] for r in rows]

    def get_enemies(self, npc_name: str, max_trust: int = -20) -> List[str]:
        rows = self.conn.execute(
            "SELECT target_name FROM relationships WHERE npc_name = ? AND trust <= ? ORDER BY trust ASC",
            (npc_name, max_trust)
        ).fetchall()
        return [r["target_name"] for r in rows]

    # ---- WORLD KNOWLEDGE ----

    def save_knowledge(self, npc_name: str, info: str, source: str = ""):
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO world_knowledge (npc_name, info, learned_at, source)
                   VALUES (?, ?, ?, ?)""",
                (npc_name, info, time.time(), source)
            )
            self.conn.commit()
        except sqlite3.Error:
            pass

    def get_knowledge(self, npc_name: str, limit: int = 20) -> List[str]:
        rows = self.conn.execute(
            "SELECT info FROM world_knowledge WHERE npc_name = ? ORDER BY learned_at DESC LIMIT ?",
            (npc_name, limit)
        ).fetchall()
        return [r["info"] for r in rows]

    # ---- WORLD STATE ----

    def save_world_state(self, key: str, value: Any):
        self.conn.execute(
            "INSERT OR REPLACE INTO world_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time())
        )
        self.conn.commit()

    def get_world_state(self, key: str, default=None) -> Any:
        row = self.conn.execute(
            "SELECT value FROM world_state WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row["value"])
        return default

    # ---- TILE MODIFICATIONS ----

    def save_tile_mod(self, x: int, y: int, old_type: int, new_type: int,
                      modified_by: str = ""):
        self.conn.execute(
            """INSERT OR REPLACE INTO tile_modifications (x, y, old_type, new_type, modified_by, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (x, y, old_type, new_type, modified_by, time.time())
        )
        self.conn.commit()

    def get_tile_mods(self) -> List[Dict]:
        rows = self.conn.execute("SELECT * FROM tile_modifications").fetchall()
        return [dict(r) for r in rows]

    # ---- PLAYER STATE ----

    def save_player(self, player_data: Dict):
        for key, value in player_data.items():
            self.conn.execute(
                "INSERT OR REPLACE INTO player_state (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
        self.conn.commit()

    def load_player(self) -> Dict:
        rows = self.conn.execute("SELECT key, value FROM player_state").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # ---- BULK OPERATIONS ----

    def save_all_npc_memories(self, npcs: list, game_day: int = 1):
        """Batch save all NPC memories and relationships."""
        for npc in npcs:
            if not npc.alive:
                continue
            # Save recent memories
            for mem in getattr(npc, 'memories', [])[-10:]:
                self.save_memory(npc.name, mem.get("type", "general"),
                                mem.get("text", ""), mem.get("importance", 1), game_day)
            # Save relationships
            for target, trust in getattr(npc, 'npc_relationships', {}).items():
                self.save_relationship(npc.name, target, trust)
            # Save player relationship
            player_rel = getattr(npc, 'player_relationship', 0)
            if player_rel != 0:
                self.save_relationship(npc.name, "Player", player_rel)
            # Save knowledge
            for info in getattr(npc, 'known_info', [])[-5:]:
                self.save_knowledge(npc.name, info)

    def load_npc_memories(self, npc) -> List[Dict]:
        """Load memories for a specific NPC from the database."""
        return self.get_memories(npc.name, limit=20)

    def load_npc_relationships(self, npc) -> Dict[str, int]:
        """Load relationships for a specific NPC."""
        return self.get_relationships(npc.name)

    # ---- LIFECYCLE ----

    def close(self):
        if self.conn:
            self.conn.close()

    def __del__(self):
        self.close()

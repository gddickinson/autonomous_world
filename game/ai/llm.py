"""
LLM integration for the game.

Supports Ollama (local), OpenAI, and Anthropic (Claude) providers.
Runs requests in a background thread so the game loop never blocks.
Falls back to static/template responses when no LLM is available.

Configuration is read from config.json or environment variables.
"""

import asyncio
import json
import os
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

# Use urllib for sync HTTP so we don't require aiohttp
import urllib.request
import urllib.error

from game.ai.prompts import Prompts, mock_npc_decision, _mock_response


# ================================
# CONFIGURATION
# ================================

class Provider(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


@dataclass
class LLMConfig:
    provider: Provider = Provider.MOCK
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 200
    temperature: float = 0.8
    enable_cache: bool = True
    cache_size: int = 500

    # Multi-model: use a fast model for NPC decisions, quality model for player dialog
    # If set, these override the main model for their respective use cases
    fast_model: str = ""      # e.g. "llama3" or "claude-haiku-4-5-20251001" - for NPC decisions
    quality_model: str = ""   # e.g. "llama3:70b" or "claude-sonnet-4-20250514" - for player dialog

    @classmethod
    def load(cls, config_path: str = "config.json") -> "LLMConfig":
        """Load config from config.json, then override from env vars."""
        cfg = cls()

        # Try config.json
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    data = json.load(f)
                llm = data.get("llm", {})
                if llm.get("provider"):
                    cfg.provider = Provider(llm["provider"])
                cfg.ollama_url = llm.get("ollama_url", cfg.ollama_url)
                cfg.ollama_model = llm.get("ollama_model", cfg.ollama_model)
                cfg.openai_api_key = llm.get("openai_api_key") or ""
                cfg.openai_model = llm.get("openai_model", cfg.openai_model)
                cfg.anthropic_api_key = llm.get("anthropic_api_key") or ""
                cfg.anthropic_model = llm.get("anthropic_model", cfg.anthropic_model)
                cfg.max_tokens = llm.get("max_tokens", cfg.max_tokens)
                cfg.temperature = llm.get("temperature", cfg.temperature)
                cfg.enable_cache = llm.get("enable_cache", cfg.enable_cache)
                cfg.cache_size = llm.get("cache_size", cfg.cache_size)
            except Exception as e:
                print(f"[LLM] Warning: could not read config.json: {e}")

        # Environment variable overrides
        if os.getenv("LLM_PROVIDER"):
            cfg.provider = Provider(os.getenv("LLM_PROVIDER"))
        if os.getenv("OLLAMA_URL"):
            cfg.ollama_url = os.getenv("OLLAMA_URL")
        if os.getenv("OLLAMA_MODEL"):
            cfg.ollama_model = os.getenv("OLLAMA_MODEL")
        if os.getenv("OPENAI_API_KEY"):
            cfg.openai_api_key = os.getenv("OPENAI_API_KEY")
        if os.getenv("OPENAI_MODEL"):
            cfg.openai_model = os.getenv("OPENAI_MODEL")
        if os.getenv("ANTHROPIC_API_KEY"):
            cfg.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if os.getenv("ANTHROPIC_MODEL"):
            cfg.anthropic_model = os.getenv("ANTHROPIC_MODEL")

        # Auto-detect provider if still mock
        if cfg.provider == Provider.MOCK:
            if cfg.anthropic_api_key:
                cfg.provider = Provider.ANTHROPIC
            elif cfg.openai_api_key:
                cfg.provider = Provider.OPENAI
            else:
                # Try Ollama
                try:
                    req = urllib.request.Request(cfg.ollama_url + "/api/tags", method="GET")
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        if resp.status == 200:
                            cfg.provider = Provider.OLLAMA
                except Exception:
                    pass  # Stay on mock

        return cfg


# ================================
# LLM REQUEST / RESPONSE
# ================================

@dataclass
class LLMRequest:
    """A pending LLM request."""
    request_id: str
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    callback: Optional[Callable[[str], None]] = None
    max_tokens: int = 200
    temperature: float = 0.8
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # higher = processed first


# ================================
# PROVIDER IMPLEMENTATIONS (synchronous)
# ================================

def _call_ollama(config: LLMConfig, prompt: str, max_tokens: int, temperature: float) -> str:
    """Call Ollama API (local)."""
    payload = json.dumps({
        "model": config.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }).encode()

    req = urllib.request.Request(
        config.ollama_url + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def _call_openai(config: LLMConfig, prompt: str, max_tokens: int, temperature: float) -> str:
    """Call OpenAI API."""
    payload = json.dumps({
        "model": config.openai_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.openai_api_key}",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()


def _call_anthropic(config: LLMConfig, prompt: str, max_tokens: int, temperature: float) -> str:
    """Call Anthropic Claude API."""
    payload = json.dumps({
        "model": config.anthropic_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        return result["content"][0]["text"].strip()


# ================================
# RESPONSE CACHE
# ================================

class _Cache:
    """Simple LRU cache for LLM responses."""
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._store: Dict[str, tuple] = {}  # key -> (response, timestamp)
        self._order: deque = deque()

    def get(self, key: str, ttl: float = 600.0) -> Optional[str]:
        if key in self._store:
            resp, ts = self._store[key]
            if time.time() - ts < ttl:
                return resp
            else:
                del self._store[key]
        return None

    def put(self, key: str, value: str):
        if key in self._store:
            self._order.remove(key)
        elif len(self._store) >= self.max_size:
            oldest = self._order.popleft()
            self._store.pop(oldest, None)
        self._store[key] = (value, time.time())
        self._order.append(key)


# ================================
# MAIN LLM MANAGER
# ================================

class LLMManager:
    """
    Non-blocking LLM manager for the game.

    - Runs a background thread processing a request queue
    - Game code calls request_*() methods which return immediately
    - Results arrive via callbacks or are polled from result dict
    - Falls back to mock responses if LLM is unavailable
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            config = LLMConfig.load()
        self.config = config
        self.enabled = config.provider != Provider.MOCK
        self.provider_name = config.provider.value

        self._cache = _Cache(config.cache_size) if config.enable_cache else None
        self._queue: deque = deque()
        self._results: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Stats
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.cache_hits = 0

    def start(self):
        """Start the background worker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        provider_str = f"{self.config.provider.value}"
        if self.config.provider == Provider.OLLAMA:
            provider_str += f" ({self.config.ollama_model})"
        elif self.config.provider == Provider.OPENAI:
            provider_str += f" ({self.config.openai_model})"
        elif self.config.provider == Provider.ANTHROPIC:
            provider_str += f" ({self.config.anthropic_model})"
        print(f"[LLM] Started with provider: {provider_str}")

    def stop(self):
        """Stop the background worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def request(self, request_id: str, prompt: str,
                callback: Optional[Callable[[str], None]] = None,
                max_tokens: int = 0, temperature: float = 0.0,
                priority: int = 0) -> str:
        """
        Submit an LLM request. Returns immediately.

        - request_id: unique ID to retrieve the result later
        - prompt: the full prompt text
        - callback: optional function called with the response when ready
        - Returns: cached response if available, else empty string
        """
        # Check cache
        if self._cache:
            cached = self._cache.get(prompt)
            if cached:
                self.cache_hits += 1
                if callback:
                    callback(cached)
                return cached

        # If LLM not enabled, return mock immediately
        if not self.enabled:
            mock = _mock_response(prompt)
            if callback:
                callback(mock)
            return mock

        # Queue the request
        req = LLMRequest(
            request_id=request_id,
            prompt=prompt,
            callback=callback,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            priority=priority,
        )
        with self._lock:
            self._queue.append(req)
        self.total_requests += 1
        return ""

    def get_result(self, request_id: str) -> Optional[str]:
        """Poll for a result by request ID. Returns None if not ready."""
        with self._lock:
            return self._results.pop(request_id, None)

    def request_sync(self, prompt: str, max_tokens: int = 0, temperature: float = 0.0) -> str:
        """
        Blocking LLM call. Use sparingly (e.g., during loading screens).
        Falls back to mock if call fails.
        """
        if self._cache:
            cached = self._cache.get(prompt)
            if cached:
                return cached

        if not self.enabled:
            return _mock_response(prompt)

        try:
            result = self._call_provider(
                prompt,
                max_tokens or self.config.max_tokens,
                temperature or self.config.temperature
            )
            if result and self._cache:
                self._cache.put(prompt, result)
            return result or _mock_response(prompt)
        except Exception:
            return _mock_response(prompt)

    def _worker(self):
        """Background thread that processes the request queue."""
        while self._running:
            req = None
            with self._lock:
                if self._queue:
                    # Pick highest priority request
                    best_idx = 0
                    best_pri = self._queue[0].priority
                    for i, r in enumerate(self._queue):
                        if r.priority > best_pri:
                            best_pri = r.priority
                            best_idx = i
                    req = self._queue[best_idx]
                    del self._queue[best_idx]

            if req is None:
                time.sleep(0.05)
                continue

            try:
                result = self._call_provider(req.prompt, req.max_tokens, req.temperature)
                if not result:
                    result = _mock_response(req.prompt)
                    self.failed_requests += 1
                else:
                    self.successful_requests += 1
                    if self._cache:
                        self._cache.put(req.prompt, result)
            except Exception as e:
                result = _mock_response(req.prompt)
                self.failed_requests += 1

            # Store result and fire callback
            with self._lock:
                self._results[req.request_id] = result
            if req.callback:
                try:
                    req.callback(result)
                except Exception:
                    pass

    def _call_provider(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call the configured LLM provider."""
        if self.config.provider == Provider.OLLAMA:
            return _call_ollama(self.config, prompt, max_tokens, temperature)
        elif self.config.provider == Provider.OPENAI:
            return _call_openai(self.config, prompt, max_tokens, temperature)
        elif self.config.provider == Provider.ANTHROPIC:
            return _call_anthropic(self.config, prompt, max_tokens, temperature)
        else:
            return _mock_response(prompt)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "provider": self.config.provider.value,
            "enabled": self.enabled,
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "cache_hits": self.cache_hits,
            "queue_size": len(self._queue),
        }

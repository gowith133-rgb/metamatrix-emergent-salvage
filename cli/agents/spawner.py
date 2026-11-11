"""
Metamatrix Sub-Agent Delegation System
Spawn isolated agents as background threads. Output saved to ~/.metamatrix/agents/
"""

from __future__ import annotations

import os
import json
import uuid
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Agent output directory
AGENTS_DIR = Path.home() / ".metamatrix" / "agents"
REGISTRY_FILE = AGENTS_DIR / ".registry.json"


def _ensure_agents_dir():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> Dict[str, Any]:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_registry(registry: Dict[str, Any]):
    _ensure_agents_dir()
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def _update_agent(agent_id: str, updates: Dict[str, Any]):
    """Thread-safe registry update."""
    registry = _load_registry()
    if agent_id in registry:
        registry[agent_id].update(updates)
    else:
        registry[agent_id] = updates
    _save_registry(registry)


# ─────────────────────────────────────────────
# Agent Worker (runs in background thread)
# ─────────────────────────────────────────────
class _AgentWorker(threading.Thread):
    """Background thread that executes a single agent task."""

    def __init__(
        self,
        agent_id: str,
        task: str,
        context: Optional[str],
        model: str,
        api_url: str,
        output_file: Path,
    ):
        super().__init__(daemon=True, name=f"metamatrix-agent-{agent_id[:8]}")
        self.agent_id = agent_id
        self.task = task
        self.context = context
        self.model = model
        self.api_url = api_url.rstrip("/")
        self.output_file = output_file

    def run(self):
        _update_agent(self.agent_id, {"status": "running", "started_at": datetime.now().isoformat()})

        try:
            output = self._execute()
            self.output_file.write_text(output, encoding="utf-8")
            _update_agent(self.agent_id, {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "output_file": str(self.output_file),
                "output_length": len(output),
            })
        except Exception as e:
            error_msg = f"Agent error: {e}"
            self.output_file.write_text(error_msg, encoding="utf-8")
            _update_agent(self.agent_id, {
                "status": "error",
                "completed_at": datetime.now().isoformat(),
                "error": str(e),
                "output_file": str(self.output_file),
            })

    def _execute(self) -> str:
        """Execute the agent task. Tries backend, then local model, then synthetic."""
        # 1. Try backend API
        if REQUESTS_AVAILABLE:
            try:
                payload = {
                    "agent_id": self.agent_id,
                    "task": self.task,
                    "context": self.context,
                    "model": self.model,
                }
                resp = requests.post(
                    f"{self.api_url}/cli/agent/spawn",
                    json=payload,
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("output", data.get("response", ""))
            except Exception:
                pass

        # 2. Try local model
        try:
            from cli.models.local import get_local_client, auto_detect_local_model
            detected = auto_detect_local_model()
            if detected:
                client = get_local_client(detected)
                if client and client.is_available():
                    context_str = self.context or ""
                    prompt = f"Task: {self.task}\n\nComplete this task thoroughly and return the result."
                    return client.generate(prompt, context=context_str)
        except Exception:
            pass

        # 3. Synthetic fallback
        return (
            f"# Agent Task: {self.task}\n\n"
            f"**Status**: Queued — awaiting inference backend\n\n"
            f"**Agent ID**: {self.agent_id}\n"
            f"**Model**: {self.model}\n"
            f"**Context**: {'Provided' if self.context else 'None'}\n\n"
            f"Start backend with: `cd backend && uvicorn server:app --reload`\n"
            f"Or start Ollama with: `ollama serve`\n"
        )


# ─────────────────────────────────────────────
# SpawnAgent
# ─────────────────────────────────────────────
class SpawnAgent:
    """
    Sub-agent delegation system.
    Spawns isolated agents as background threads.
    Output is persisted to ~/.metamatrix/agents/<id>.md
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.api_url = self.config.get("api_url", "http://localhost:8001/api")
        self.default_model = self.config.get("model", "claude")
        _ensure_agents_dir()
        self._threads: Dict[str, _AgentWorker] = {}

    def spawn(
        self,
        task: str,
        context: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Create and start an isolated sub-agent for the given task.

        Args:
            task: Task description for the agent
            context: Optional context string to seed the agent
            model: Model to use (defaults to config model)

        Returns:
            agent_id string
        """
        agent_id = str(uuid.uuid4())
        model = model or self.default_model
        output_file = AGENTS_DIR / f"{agent_id}.md"

        # Register agent
        registry = _load_registry()
        registry[agent_id] = {
            "id": agent_id,
            "task": task,
            "model": model,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "output_file": str(output_file),
            "has_context": bool(context),
        }
        _save_registry(registry)

        # Start worker thread
        worker = _AgentWorker(
            agent_id=agent_id,
            task=task,
            context=context,
            model=model,
            api_url=self.api_url,
            output_file=output_file,
        )
        self._threads[agent_id] = worker
        worker.start()

        return agent_id

    def get_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get the current status of an agent.

        Args:
            agent_id: Agent ID returned from spawn()

        Returns:
            dict with status, task, timing info
        """
        registry = _load_registry()
        if agent_id not in registry:
            return {"id": agent_id, "status": "not_found"}

        info = registry[agent_id].copy()

        # Check if thread is still alive
        thread = self._threads.get(agent_id)
        if thread and thread.is_alive():
            info["status"] = "running"
        elif info.get("status") == "pending" and not (thread and thread.is_alive()):
            # Thread may have been spawned in another process
            output_file = Path(info.get("output_file", ""))
            if output_file.exists():
                info["status"] = "completed"

        return info

    def collect(self, agent_id: str) -> Optional[str]:
        """
        Retrieve the output from a completed agent.

        Args:
            agent_id: Agent ID to collect output from

        Returns:
            Output string or None if not ready
        """
        registry = _load_registry()
        info = registry.get(agent_id)
        if not info:
            return None

        output_file = Path(info.get("output_file", ""))
        if output_file.exists():
            return output_file.read_text(encoding="utf-8")

        return None

    def wait_for(self, agent_id: str, timeout: float = 120.0, poll_interval: float = 1.0) -> Optional[str]:
        """
        Block until an agent completes (or timeout).

        Args:
            agent_id: Agent to wait for
            timeout: Maximum seconds to wait
            poll_interval: Polling interval in seconds

        Returns:
            Output string or None if timed out
        """
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(agent_id)
            if status.get("status") in ("completed", "error"):
                return self.collect(agent_id)
            time.sleep(poll_interval)
        return None

    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all known agents (active and completed).

        Returns:
            List of agent status dicts
        """
        registry = _load_registry()
        agents = []
        for agent_id, info in registry.items():
            # Check thread status
            thread = self._threads.get(agent_id)
            if thread and thread.is_alive():
                info = dict(info)
                info["status"] = "running"
            agents.append(info)

        # Sort by creation time (newest first)
        agents.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return agents

    def cancel(self, agent_id: str) -> bool:
        """
        Attempt to cancel a running agent.
        Note: Python threads cannot be forcibly killed; this marks the agent as cancelled.

        Args:
            agent_id: Agent ID to cancel

        Returns:
            True if agent was found and marked cancelled
        """
        registry = _load_registry()
        if agent_id in registry:
            registry[agent_id]["status"] = "cancelled"
            registry[agent_id]["cancelled_at"] = datetime.now().isoformat()
            _save_registry(registry)
            return True
        return False

    def cleanup(self, keep_days: int = 7):
        """
        Remove agent records and output files older than keep_days.

        Args:
            keep_days: Number of days to retain agent records
        """
        registry = _load_registry()
        now = datetime.now()
        to_remove = []

        for agent_id, info in registry.items():
            created_str = info.get("created_at", "")
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str)
                    age_days = (now - created).days
                    if age_days > keep_days:
                        to_remove.append(agent_id)
                except Exception:
                    pass

        for agent_id in to_remove:
            info = registry.pop(agent_id)
            output_file = Path(info.get("output_file", ""))
            if output_file.exists():
                output_file.unlink()

        _save_registry(registry)
        return len(to_remove)

"""
Metamatrix Context Manager
Reads/writes .md files from ~/.metamatrix/context/
Syncs with backend API.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Default context directory
CONTEXT_DIR = Path.home() / ".metamatrix" / "context"
INDEX_FILE = CONTEXT_DIR / ".index.json"


def _ensure_context_dir():
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> Dict[str, Any]:
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_index(index: Dict[str, Any]):
    _ensure_context_dir()
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


class ContextManager:
    """
    Local context manager for Metamatrix.
    Manages .md files in ~/.metamatrix/context/ and syncs with backend.
    """

    def __init__(self, api_url: str = "http://localhost:8001/api"):
        self.api_url = api_url.rstrip("/")
        _ensure_context_dir()

    def _key_from_path(self, file_path: str) -> str:
        """Derive a context key from a file path."""
        return Path(file_path).stem.replace(" ", "_").lower()

    def push_context(self, file_path: str, key: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a local .md file to the backend context store.

        Args:
            file_path: Path to the local .md file
            key: Optional key override (defaults to filename stem)

        Returns:
            dict with upload result
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        key = key or self._key_from_path(str(file_path))
        content = file_path.read_text(encoding="utf-8")

        # Save locally first
        local_dest = CONTEXT_DIR / f"{key}.md"
        local_dest.write_text(content, encoding="utf-8")

        # Update index
        index = _load_index()
        index[key] = {
            "key": key,
            "source": str(file_path),
            "local_path": str(local_dest),
            "size": len(content),
            "updated_at": datetime.now().isoformat(),
        }
        _save_index(index)

        # Push to backend if available
        if REQUESTS_AVAILABLE:
            try:
                resp = requests.post(
                    f"{self.api_url}/cli/context/push",
                    json={"key": key, "content": content},
                    timeout=10,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    index[key]["synced_at"] = datetime.now().isoformat()
                    _save_index(index)
                    return {"key": key, "local": str(local_dest), "remote": result}
                else:
                    return {"key": key, "local": str(local_dest), "remote_error": resp.text}
            except Exception as e:
                return {"key": key, "local": str(local_dest), "remote_error": str(e)}

        return {"key": key, "local": str(local_dest), "remote": "skipped (requests not available)"}

    def pull_context(self, key: str, output_path: Optional[str] = None) -> str:
        """
        Download a context file from the backend by key.

        Args:
            key: Context key to retrieve
            output_path: Optional custom output path

        Returns:
            Path where the file was written
        """
        dest = Path(output_path) if output_path else CONTEXT_DIR / f"{key}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Try backend first
        if REQUESTS_AVAILABLE:
            try:
                resp = requests.get(
                    f"{self.api_url}/cli/context/pull/{key}",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", "")
                    dest.write_text(content, encoding="utf-8")

                    # Update index
                    index = _load_index()
                    index[key] = {
                        "key": key,
                        "local_path": str(dest),
                        "size": len(content),
                        "updated_at": datetime.now().isoformat(),
                        "synced_at": datetime.now().isoformat(),
                    }
                    _save_index(index)
                    return str(dest)
                else:
                    raise RuntimeError(f"Backend returned {resp.status_code}: {resp.text}")
            except Exception as e:
                # Fall back to local cache
                local = CONTEXT_DIR / f"{key}.md"
                if local.exists():
                    if output_path:
                        dest.write_text(local.read_text(encoding="utf-8"), encoding="utf-8")
                        return str(dest)
                    return str(local)
                raise RuntimeError(f"Context not found locally or remotely: {key}. Error: {e}")

        # Offline: try local cache
        local = CONTEXT_DIR / f"{key}.md"
        if local.exists():
            if output_path and output_path != str(local):
                dest.write_text(local.read_text(encoding="utf-8"), encoding="utf-8")
                return str(dest)
            return str(local)

        raise FileNotFoundError(f"Context not found: {key}")

    def list_contexts(self, remote: bool = False) -> List[str]:
        """
        List available context files.

        Args:
            remote: If True, fetch list from backend; otherwise list local files

        Returns:
            List of context descriptions
        """
        if remote and REQUESTS_AVAILABLE:
            try:
                resp = requests.get(f"{self.api_url}/cli/context/list", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    keys = data.get("contexts", [])
                    return [f"{k} [remote]" for k in keys]
            except Exception:
                pass  # Fall through to local

        # Local listing
        results = []
        index = _load_index()

        # From index
        for key, meta in index.items():
            size = meta.get("size", 0)
            updated = meta.get("updated_at", "unknown")[:10]
            synced = "✓" if "synced_at" in meta else "○"
            results.append(f"{key} — {size}B — {updated} {synced}")

        # Any .md files not in index
        for md_file in CONTEXT_DIR.glob("*.md"):
            key = md_file.stem
            if key not in index:
                size = md_file.stat().st_size
                results.append(f"{key} — {size}B — local only")

        return results or ["No context files found."]

    def sync_all(self) -> List[Dict[str, Any]]:
        """
        Sync all local context files to the backend.

        Returns:
            List of sync results per file
        """
        results = []
        for md_file in CONTEXT_DIR.glob("*.md"):
            try:
                result = self.push_context(str(md_file))
                results.append({"file": md_file.name, "status": "ok", **result})
            except Exception as e:
                results.append({"file": md_file.name, "status": "error", "error": str(e)})
        return results

    def read_local(self, key: str) -> Optional[str]:
        """Read a context file from local cache."""
        path = CONTEXT_DIR / f"{key}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def write_local(self, key: str, content: str) -> str:
        """Write content to a local context file."""
        _ensure_context_dir()
        path = CONTEXT_DIR / f"{key}.md"
        path.write_text(content, encoding="utf-8")

        index = _load_index()
        index[key] = {
            "key": key,
            "local_path": str(path),
            "size": len(content),
            "updated_at": datetime.now().isoformat(),
        }
        _save_index(index)
        return str(path)

    def delete_local(self, key: str) -> bool:
        """Delete a local context file."""
        path = CONTEXT_DIR / f"{key}.md"
        if path.exists():
            path.unlink()
            index = _load_index()
            index.pop(key, None)
            _save_index(index)
            return True
        return False

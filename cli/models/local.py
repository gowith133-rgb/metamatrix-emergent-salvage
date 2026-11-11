"""
Metamatrix Local Model Integration
Connects to Ollama, LM Studio, and BitNet b1.58 local inference servers.
Auto-detects which local model is running.
"""

from __future__ import annotations

import json
from typing import Optional, Iterator, Dict, Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ─────────────────────────────────────────────
# Base client interface
# ─────────────────────────────────────────────
class BaseLocalClient:
    """Base class for local model clients."""

    name: str = "base"
    default_url: str = ""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or self.default_url).rstrip("/")
        self.model = model or self._default_model()
        self.timeout = 120

    def _default_model(self) -> str:
        return ""

    def is_available(self) -> bool:
        """Check if the local server is reachable."""
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.base_url}/", timeout=3)
            return resp.status_code < 500
        except Exception:
            return False

    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a completion. Returns the full response string."""
        raise NotImplementedError

    def stream(self, prompt: str, context: str = "") -> Iterator[str]:
        """Stream tokens as they are generated."""
        raise NotImplementedError

    def list_models(self) -> list:
        """List available models on this server."""
        return []

    def _build_messages(self, prompt: str, context: str = "") -> list:
        """Build message array from prompt + context."""
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        return messages


# ─────────────────────────────────────────────
# Ollama Client
# ─────────────────────────────────────────────
class OllamaClient(BaseLocalClient):
    """
    Connects to a local Ollama instance at localhost:11434.
    Supports any model pulled via `ollama pull <model>`.
    """

    name = "ollama"
    default_url = "http://localhost:11434"

    def _default_model(self) -> str:
        return "llama3"

    def is_available(self) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list:
        if not REQUESTS_AVAILABLE:
            return []
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def _auto_select_model(self) -> str:
        """Pick the first available model if the default isn't available."""
        models = self.list_models()
        if not models:
            return self.model
        if self.model in models:
            return self.model
        return models[0]

    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a completion using Ollama's /api/chat endpoint."""
        if not REQUESTS_AVAILABLE:
            return "[requests library not available]"

        model = self._auto_select_model()
        messages = self._build_messages(prompt, context)

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            return f"[Ollama error: HTTP {resp.status_code}: {resp.text[:200]}]"
        except requests.exceptions.Timeout:
            return "[Ollama timeout — model may be loading, try again]"
        except Exception as e:
            return f"[Ollama error: {e}]"

    def stream(self, prompt: str, context: str = "") -> Iterator[str]:
        """Stream tokens from Ollama."""
        if not REQUESTS_AVAILABLE:
            yield "[requests library not available]"
            return

        model = self._auto_select_model()
        messages = self._build_messages(prompt, context)

        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
                stream=True,
                timeout=self.timeout,
            ) as resp:
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"[Stream error: {e}]"

    def embeddings(self, text: str) -> list:
        """Get embeddings from Ollama."""
        if not REQUESTS_AVAILABLE:
            return []
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("embedding", [])
        except Exception:
            pass
        return []


# ─────────────────────────────────────────────
# LM Studio Client
# ─────────────────────────────────────────────
class LMStudioClient(BaseLocalClient):
    """
    Connects to LM Studio's OpenAI-compatible API at localhost:1234.
    LM Studio must be running with a model loaded.
    """

    name = "lmstudio"
    default_url = "http://localhost:1234"

    def _default_model(self) -> str:
        return "local-model"  # LM Studio uses whatever is loaded

    def is_available(self) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list:
        if not REQUESTS_AVAILABLE:
            return []
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            pass
        return []

    def generate(self, prompt: str, context: str = "") -> str:
        """Generate using LM Studio's OpenAI-compatible /v1/chat/completions."""
        if not REQUESTS_AVAILABLE:
            return "[requests library not available]"

        messages = self._build_messages(prompt, context)
        models = self.list_models()
        model = models[0] if models else self.model

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return "[No response generated]"
            return f"[LM Studio error: HTTP {resp.status_code}: {resp.text[:200]}]"
        except requests.exceptions.Timeout:
            return "[LM Studio timeout — model may be loading]"
        except Exception as e:
            return f"[LM Studio error: {e}]"

    def stream(self, prompt: str, context: str = "") -> Iterator[str]:
        """Stream from LM Studio."""
        if not REQUESTS_AVAILABLE:
            yield "[requests library not available]"
            return

        messages = self._build_messages(prompt, context)
        models = self.list_models()
        model = models[0] if models else self.model

        try:
            with requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "stream": True,
                },
                stream=True,
                timeout=self.timeout,
            ) as resp:
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"[Stream error: {e}]"


# ─────────────────────────────────────────────
# BitNet Client
# ─────────────────────────────────────────────
class BitNetClient(BaseLocalClient):
    """
    Connects to a llama.cpp server running BitNet b1.58.
    Start the server with: ./server -m bitnet-model.gguf --port 8080
    Exposes OpenAI-compatible endpoints.
    """

    name = "bitnet"
    default_url = "http://localhost:8080"

    def _default_model(self) -> str:
        return "bitnet-b1.58"

    def is_available(self) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            try:
                # llama.cpp server may not have /health but responds to /
                resp = requests.get(f"{self.base_url}/", timeout=3)
                return resp.status_code < 500
            except Exception:
                return False

    def generate(self, prompt: str, context: str = "") -> str:
        """Generate using llama.cpp server's /v1/chat/completions or /completion."""
        if not REQUESTS_AVAILABLE:
            return "[requests library not available]"

        # Try OpenAI-compatible endpoint first
        messages = self._build_messages(prompt, context)
        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
        except Exception:
            pass

        # Fall back to llama.cpp native /completion endpoint
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        try:
            resp = requests.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": full_prompt,
                    "n_predict": 2048,
                    "temperature": 0.7,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("content", "")
            return f"[BitNet error: HTTP {resp.status_code}: {resp.text[:200]}]"
        except requests.exceptions.Timeout:
            return "[BitNet timeout — model may be loading]"
        except Exception as e:
            return f"[BitNet error: {e}]"

    def stream(self, prompt: str, context: str = "") -> Iterator[str]:
        """Stream from BitNet/llama.cpp server."""
        if not REQUESTS_AVAILABLE:
            yield "[requests library not available]"
            return

        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        try:
            with requests.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": full_prompt,
                    "n_predict": 2048,
                    "temperature": 0.7,
                    "stream": True,
                },
                stream=True,
                timeout=self.timeout,
            ) as resp:
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                token = data.get("content", "")
                                if token:
                                    yield token
                                if data.get("stop"):
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"[Stream error: {e}]"

    def get_model_info(self) -> Dict[str, Any]:
        """Get model info from the llama.cpp server."""
        if not REQUESTS_AVAILABLE:
            return {}
        try:
            resp = requests.get(f"{self.base_url}/model.json", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}


# ─────────────────────────────────────────────
# Auto-detection
# ─────────────────────────────────────────────
_CLIENTS = {
    "ollama": OllamaClient,
    "lmstudio": LMStudioClient,
    "bitnet": BitNetClient,
}


def auto_detect_local_model() -> Optional[str]:
    """
    Detect which local model server is currently running.

    Returns:
        Name of the running server ("ollama", "lmstudio", "bitnet") or None
    """
    for name, cls in _CLIENTS.items():
        client = cls()
        if client.is_available():
            return name
    return None


def get_local_client(name: str, model: Optional[str] = None) -> Optional[BaseLocalClient]:
    """
    Get a configured local model client by name.

    Args:
        name: Client name ("ollama", "lmstudio", "bitnet")
        model: Optional model override

    Returns:
        Configured client instance or None
    """
    cls = _CLIENTS.get(name.lower())
    if cls is None:
        return None
    return cls(model=model)


def get_best_available_client() -> Optional[BaseLocalClient]:
    """
    Returns the first available local model client.
    Priority: ollama → lmstudio → bitnet
    """
    for name, cls in _CLIENTS.items():
        client = cls()
        if client.is_available():
            return client
    return None

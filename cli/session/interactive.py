"""
Metamatrix Interactive Terminal Session
Rich-powered terminal chat interface with persona-aware formatting.
"""

from __future__ import annotations

import os
import sys
import json
import signal
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from cli.styles.personas import PersonaEngine

# ─────────────────────────────────────────────
# Battery detection (Linux)
# ─────────────────────────────────────────────
def _get_battery() -> Optional[str]:
    try:
        battery_paths = list(Path("/sys/class/power_supply").glob("BAT*"))
        if not battery_paths:
            return None
        bat = battery_paths[0]
        capacity = (bat / "capacity").read_text().strip()
        status_file = bat / "status"
        status = status_file.read_text().strip() if status_file.exists() else "?"
        symbol = "⚡" if status == "Charging" else "🔋"
        return f"{symbol} {capacity}%"
    except Exception:
        return None


def _get_encryption_status() -> str:
    # Check for common VPN/encryption indicators
    try:
        result = os.popen("ip route show dev tun0 2>/dev/null").read()
        if result.strip():
            return "🔒 ENCRYPTED"
    except Exception:
        pass
    return "○ PLAINTEXT"


# ─────────────────────────────────────────────
# Context save shortcut (Ctrl+S simulation)
# ─────────────────────────────────────────────
_save_context_flag = threading.Event()


# ─────────────────────────────────────────────
# Interactive Session
# ─────────────────────────────────────────────
class InteractiveSession:
    """
    Rich terminal chat interface for Metamatrix.
    Supports persona-aware output, node status header, message history.
    """

    def __init__(self, config: Dict[str, Any], show_header: bool = True):
        self.config = config
        self.show_header = show_header
        self.persona_mode = config.get("persona", "sovereign")
        self.model = config.get("model", "claude")
        self.api_url = config.get("api_url", "http://localhost:8001/api").rstrip("/")
        self.persona = PersonaEngine(self.persona_mode)
        self.messages: List[Dict[str, Any]] = []
        self.session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.running = False

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def _render_header(self):
        """Render the node status header."""
        if not self.show_header:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        battery = _get_battery()
        encryption = _get_encryption_status()

        battery_str = f"  {battery}" if battery else ""
        channel = f"CH:{self.model.upper()}"
        persona_label = f"P:{self.persona_mode.upper()}"

        header_text = f"[bold cyan]METAMATRIX[/bold cyan] v2.0  │  {channel}  │  {persona_label}  │  {encryption}{battery_str}  │  [dim]{now}[/dim]"

        if RICH_AVAILABLE:
            self.console.print(Rule(style="cyan"))
            self.console.print(
                Panel(
                    header_text,
                    style="dim cyan",
                    padding=(0, 1),
                    expand=True,
                )
            )
            self.console.print(
                "[dim]Node interface active. Ctrl+C = close session  │  Type 'exit' or 'quit' to end[/dim]"
            )
            self.console.print(Rule(style="cyan"))
        else:
            print(f"\n{'='*60}")
            print(f"METAMATRIX v2.0 | {channel} | {persona_label} | {now}")
            print(f"Node interface active. Type 'exit' to end.")
            print(f"{'='*60}\n")

    def _send_message(self, user_input: str) -> str:
        """Send message to backend and return AI response."""
        if REQUESTS_AVAILABLE:
            try:
                payload = {
                    "message": user_input,
                    "session_id": self.session_id,
                    "persona": self.persona_mode,
                    "model": self.model,
                    "history": self.messages[-20:],  # Last 20 messages for context
                }
                resp = requests.post(
                    f"{self.api_url}/cli/chat",
                    json=payload,
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("response", data.get("message", "No response."))
                else:
                    return f"[Node error: HTTP {resp.status_code}]"
            except requests.exceptions.ConnectionError:
                return self._local_fallback(user_input)
            except Exception as e:
                return f"[Communication error: {e}]"
        else:
            return self._local_fallback(user_input)

    def _local_fallback(self, user_input: str) -> str:
        """Try local model if backend is unavailable."""
        try:
            from cli.models.local import auto_detect_local_model, get_local_client
            detected = auto_detect_local_model()
            if detected:
                client = get_local_client(detected)
                if client and client.is_available():
                    context = "\n".join(
                        f"{m['role']}: {m['content']}" for m in self.messages[-10:]
                    )
                    return client.generate(user_input, context=context)
        except Exception:
            pass
        return (
            "[Backend unreachable. Local model unavailable. "
            "Start backend with: cd backend && uvicorn server:app --reload]"
        )

    def _add_message(self, role: str, content: str):
        """Add a message to the session history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def _save_context_snapshot(self):
        """Save the current session context to disk."""
        from cli.context.manager import ContextManager
        mgr = ContextManager(api_url=self.api_url)

        snapshot = json.dumps(self.messages, indent=2)
        key = f"session_{self.session_id}"
        path = mgr.write_local(key, f"# Session Snapshot: {self.session_id}\n\n```json\n{snapshot}\n```")

        if RICH_AVAILABLE:
            self.console.print(f"\n[green]Context saved: {path}[/green]")
        else:
            print(f"\nContext saved: {path}")

    def _close_and_document(self):
        """Run the session closing protocol."""
        from cli.session.closer import close_session as run_close

        if RICH_AVAILABLE:
            self.console.print("\n[cyan]Session closing protocol initiated...[/cyan]")

        result = run_close(
            messages=self.messages,
            repo_path=os.getcwd(),
            skip_commit=False,
        )

        if RICH_AVAILABLE:
            self.console.print(f"[green]Session log: {result.get('log_path', 'N/A')}[/green]")
            commit = result.get("commit")
            if commit:
                if commit.get("success"):
                    self.console.print(f"[green]Git commit: {commit.get('results', {}).get('commit', {}).get('stdout', 'done')}[/green]")
                else:
                    self.console.print(f"[yellow]Git commit skipped: {commit.get('error', commit.get('message', ''))}[/yellow]")
        else:
            print(f"Session log: {result.get('log_path', 'N/A')}")

    def _show_spinner(self, label: str = "Processing..."):
        """Context manager for spinner while waiting for response."""
        if RICH_AVAILABLE:
            return self.console.status(f"[cyan]{label}[/cyan]", spinner="dots")
        return _NullContext()

    def run(self, seed_context: Optional[str] = None):
        """
        Start the interactive session loop.

        Args:
            seed_context: Optional initial context to inject
        """
        self.running = True
        self._render_header()

        # Inject seed context
        if seed_context:
            self._add_message("system", f"[Context loaded]\n\n{seed_context}")
            if RICH_AVAILABLE:
                self.console.print(f"[dim]Context loaded: {len(seed_context)} chars[/dim]\n")

        # Handle Ctrl+C gracefully
        original_sigint = signal.getsignal(signal.SIGINT)

        def handle_sigint(sig, frame):
            self.running = False

        signal.signal(signal.SIGINT, handle_sigint)

        try:
            while self.running:
                # Prompt
                try:
                    if RICH_AVAILABLE:
                        user_input = self.console.input("[bold cyan]you >[/bold cyan] ").strip()
                    else:
                        user_input = input("you > ").strip()
                except (EOFError, KeyboardInterrupt):
                    self.running = False
                    break

                if not user_input:
                    continue

                # Special commands
                if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                    self.running = False
                    break

                if user_input.lower() in ("/save", "ctrl+s"):
                    self._save_context_snapshot()
                    continue

                if user_input.lower() in ("/status", "/node"):
                    from cli.models.local import auto_detect_local_model
                    detected = auto_detect_local_model()
                    self.persona.render_list("Node Status", [
                        f"Model: {self.model}",
                        f"Persona: {self.persona_mode}",
                        f"Messages: {len(self.messages)}",
                        f"Local model: {detected or 'none'}",
                        f"Session ID: {self.session_id}",
                    ])
                    continue

                if user_input.lower().startswith("/persona "):
                    new_persona = user_input.split(" ", 1)[1].strip()
                    self.persona_mode = new_persona
                    self.persona = PersonaEngine(new_persona)
                    self.persona.render(f"Persona switched to: {new_persona}", "success")
                    continue

                if user_input.lower().startswith("/model "):
                    new_model = user_input.split(" ", 1)[1].strip()
                    self.model = new_model
                    self.persona.render(f"Model switched to: {new_model}", "success")
                    continue

                if user_input.lower() in ("/help", "/?"):
                    self._show_help()
                    continue

                # Record user message
                self._add_message("user", user_input)
                ts = datetime.now().strftime("%H:%M")

                # Get AI response
                with self._show_spinner("Node processing..."):
                    response = self._send_message(user_input)

                # Apply persona formatting
                formatted = self.persona.format_ai_response(response)

                # Record AI message
                self._add_message("assistant", response)

                # Render
                self.persona.render_response("node", formatted, timestamp=ts)
                print()

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self.running = False

            # Session close protocol
            if self.messages:
                if RICH_AVAILABLE:
                    self.console.print(Rule("[cyan]Session Closing Protocol[/cyan]"))
                self._close_and_document()

            if RICH_AVAILABLE:
                self.console.print("\n[dim cyan]Node offline. Channel closed.[/dim cyan]\n")
            else:
                print("\nNode offline. Channel closed.\n")

    def _show_help(self):
        """Show in-session help."""
        commands = [
            "/save          — Save context snapshot",
            "/status        — Show node status",
            "/persona <mode>— Switch persona (sovereign/technical/hermetic/minimal/verbose)",
            "/model <name>  — Switch model (claude/gpt/gemini/ollama/lmstudio/bitnet)",
            "/help          — Show this help",
            "exit / quit    — Close session",
        ]
        self.persona.render_list("In-Session Commands", commands)


class _NullContext:
    """Fallback context manager when Rich isn't available."""
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

"""
Metamatrix Output Persona Engine
Five modes of sovereign expression.
"""

from __future__ import annotations
from typing import List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.theme import Theme
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ─────────────────────────────────────────────
# Persona definitions
# ─────────────────────────────────────────────
PERSONAS = {
    "sovereign": {
        "description": "Direct. No hedging. Hermetic references natural.",
        "prefix": "▸",
        "color": "bold cyan",
        "style": "sovereign",
        "list_bullet": "◆",
    },
    "technical": {
        "description": "Precise, code-first, minimal prose.",
        "prefix": "$",
        "color": "green",
        "style": "technical",
        "list_bullet": "·",
    },
    "hermetic": {
        "description": "Philosophical. The Law lives in every response.",
        "prefix": "✦",
        "color": "bold magenta",
        "style": "hermetic",
        "list_bullet": "⬡",
    },
    "minimal": {
        "description": "One sentence max. Terminal output style.",
        "prefix": ">",
        "color": "white",
        "style": "minimal",
        "list_bullet": "-",
    },
    "verbose": {
        "description": "Full context. Markdown formatted. Detailed.",
        "prefix": "📄",
        "color": "bold yellow",
        "style": "verbose",
        "list_bullet": "•",
    },
}

HERMETIC_LAWS = [
    "As above, so below.",
    "The All is Mind; the Universe is Mental.",
    "Nothing rests; everything moves; everything vibrates.",
    "Everything is Dual; everything has poles.",
    "Everything flows, out and in.",
    "Every Cause has its Effect; every Effect has its Cause.",
    "Gender is in everything; everything has its Masculine and Feminine Principles.",
]

SOVEREIGN_AFFIRMATIONS = [
    "Transmission complete.",
    "Signal received and processed.",
    "Knowledge integrated.",
    "Protocol executed.",
    "Node response delivered.",
]


def _hermetic_suffix() -> str:
    import random
    return f"\n\n*{random.choice(HERMETIC_LAWS)}*"


def _sovereign_suffix() -> str:
    import random
    return f" — {random.choice(SOVEREIGN_AFFIRMATIONS)}"


# ─────────────────────────────────────────────
# Persona Engine
# ─────────────────────────────────────────────
class PersonaEngine:
    """Routes output through the active persona filter."""

    def __init__(self, mode: str = "sovereign"):
        if mode not in PERSONAS:
            mode = "sovereign"
        self.mode = mode
        self.persona = PERSONAS[mode]

        if RICH_AVAILABLE:
            theme = Theme({
                "sovereign": "bold cyan",
                "technical": "green",
                "hermetic": "bold magenta",
                "minimal": "white",
                "verbose": "bold yellow",
                "success": "bold green",
                "warning": "bold yellow",
                "error": "bold red",
                "info": "dim white",
            })
            self.console = Console(theme=theme)
        else:
            self.console = None

    def _format_message(self, msg: str, style: str = "info") -> str:
        """Apply persona-specific formatting to a message."""
        prefix = self.persona["prefix"]

        if self.mode == "minimal":
            # Truncate to first sentence
            first_sentence = msg.split(".")[0]
            if len(first_sentence) < len(msg):
                first_sentence += "."
            return f"{prefix} {first_sentence}"

        elif self.mode == "hermetic":
            return f"{prefix} {msg}{_hermetic_suffix()}"

        elif self.mode == "sovereign":
            return f"{prefix} {msg}{_sovereign_suffix()}"

        elif self.mode == "technical":
            return f"{prefix} {msg}"

        elif self.mode == "verbose":
            return f"{prefix} **{msg}**\n"

        return f"{prefix} {msg}"

    def render(self, msg: str, style: str = "info"):
        """Render a message to the terminal through the active persona."""
        if not RICH_AVAILABLE:
            prefix = self.persona["prefix"]
            print(f"{prefix} {msg}")
            return

        color = self.persona["color"]

        if self.mode == "minimal":
            first = msg.split(".")[0]
            if len(first) < len(msg):
                first += "."
            self.console.print(f"{self.persona['prefix']} {first}", style=color)

        elif self.mode == "hermetic":
            import random
            law = random.choice(HERMETIC_LAWS)
            self.console.print(
                Panel(
                    f"{msg}\n\n[dim italic]{law}[/dim italic]",
                    border_style="magenta",
                    title="[bold magenta]✦ Hermetic Node[/bold magenta]",
                    expand=False,
                )
            )

        elif self.mode == "sovereign":
            import random
            suffix = random.choice(SOVEREIGN_AFFIRMATIONS)
            self.console.print(f"[{color}]{self.persona['prefix']} {msg}[/{color}] [dim]— {suffix}[/dim]")

        elif self.mode == "technical":
            self.console.print(f"[green]{self.persona['prefix']}[/green] {msg}")

        elif self.mode == "verbose":
            self.console.print(
                Panel(
                    Markdown(msg),
                    border_style="yellow",
                    title="[bold yellow]Metamatrix[/bold yellow]",
                    expand=True,
                )
            )

        else:
            self.console.print(f"{self.persona['prefix']} {msg}", style=color)

    def render_list(self, title: str, items: List[str]):
        """Render a list of items through the active persona."""
        if not items:
            self.render(f"{title}: empty.", "info")
            return

        bullet = self.persona["list_bullet"]

        if not RICH_AVAILABLE:
            print(f"\n{title}:")
            for item in items:
                print(f"  {bullet} {item}")
            return

        if self.mode == "minimal":
            self.console.print(f"{title}: {len(items)} items.")
            return

        elif self.mode == "verbose":
            content = "\n".join(f"{bullet} {item}" for item in items)
            self.console.print(
                Panel(
                    Markdown(f"## {title}\n\n{content}"),
                    border_style="yellow",
                    expand=True,
                )
            )
            return

        elif self.mode == "hermetic":
            content = "\n".join(f"  [magenta]{bullet}[/magenta] {item}" for item in items)
            self.console.print(f"\n[bold magenta]{title}[/bold magenta]")
            self.console.print(content)
            return

        # Default for sovereign / technical
        color = self.persona["color"]
        self.console.print(f"\n[{color}]{title}[/{color}]")
        for item in items:
            self.console.print(f"  {bullet} {item}")

    def render_response(self, role: str, content: str, timestamp: str = ""):
        """Render a chat message with persona-aware formatting."""
        if not RICH_AVAILABLE:
            ts = f"[{timestamp}] " if timestamp else ""
            print(f"{ts}{role}: {content}\n")
            return

        if role.lower() in ("user", "you"):
            label = "[dim cyan]you[/dim cyan]"
            style = "dim"
        else:
            label = f"[bold {self.persona['color']}]node[/bold {self.persona['color']}]"
            style = self.persona["color"]

        ts_str = f" [dim]{timestamp}[/dim]" if timestamp else ""

        if self.mode == "minimal":
            first = content.split(".")[0]
            self.console.print(f"{label}{ts_str}: {first}.")
        elif self.mode == "hermetic":
            import random
            law = random.choice(HERMETIC_LAWS)
            self.console.print(f"\n{label}{ts_str}")
            self.console.print(Panel(
                f"{content}\n\n[dim italic]{law}[/dim italic]",
                border_style="magenta",
                expand=False,
            ))
        elif self.mode == "verbose":
            self.console.print(f"\n{label}{ts_str}")
            self.console.print(Panel(Markdown(content), border_style="yellow", expand=True))
        else:
            self.console.print(f"\n{label}{ts_str}")
            self.console.print(content)

    def format_ai_response(self, content: str) -> str:
        """Apply persona framing to AI response text before display."""
        if self.mode == "minimal":
            sentences = [s.strip() for s in content.split(".") if s.strip()]
            return sentences[0] + "." if sentences else content

        elif self.mode == "hermetic":
            import random
            law = random.choice(HERMETIC_LAWS)
            return f"{content}\n\n*{law}*"

        elif self.mode == "sovereign":
            return content  # Let the raw response speak

        elif self.mode == "technical":
            return content  # Code speaks for itself

        elif self.mode == "verbose":
            return content  # Already expects full markdown

        return content

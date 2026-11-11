#!/usr/bin/env python3
"""
Metamatrix CLI — Terminal-First Sovereign AI Interface
Node interface active. Local-first. No central server required.
"""

import sys
import os
import click
from pathlib import Path

# Ensure cli package is importable from any working directory
CLI_DIR = Path(__file__).parent
sys.path.insert(0, str(CLI_DIR.parent))

from cli.styles.personas import PersonaEngine, PERSONAS
from cli.context.manager import ContextManager
from cli.session.closer import close_session
from cli.agents.spawner import SpawnAgent

# ─────────────────────────────────────────────
# Config path
# ─────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".metamatrix"
CONFIG_FILE = CONFIG_DIR / "config.json"

import json

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"persona": "sovereign", "model": "claude", "api_url": "http://localhost:8001/api"}


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ─────────────────────────────────────────────
# Click context object
# ─────────────────────────────────────────────
class MetaCtx:
    def __init__(self):
        self.config = load_config()
        self.persona = PersonaEngine(self.config.get("persona", "sovereign"))

    def echo(self, msg: str, style: str = "info"):
        self.persona.render(msg, style)


pass_meta = click.make_pass_decorator(MetaCtx, ensure=True)


# ─────────────────────────────────────────────
# Root group
# ─────────────────────────────────────────────
@click.group()
@click.version_option(version="2.0.0", prog_name="Metamatrix")
@click.pass_context
def cli(ctx):
    """
    \b
    ╔══════════════════════════════════════════╗
    ║   METAMATRIX  v2.0  — Node Interface     ║
    ║   Terminal-First Sovereign AI Substrate  ║
    ║   Local-first. Encrypted. Autonomous.    ║
    ╚══════════════════════════════════════════╝

    \b
    Node interface active.
    All channels available. Context loaded.
    Run a command or type --help for options.
    """
    ctx.ensure_object(MetaCtx)


# ─────────────────────────────────────────────
# CHAT command
# ─────────────────────────────────────────────
@cli.command()
@click.option("--persona", "-p", default=None,
              help="Output persona override [sovereign|technical|hermetic|minimal|verbose]")
@click.option("--model", "-m", default=None,
              help="Model override [claude|gpt|gemini|ollama|lmstudio|bitnet]")
@click.option("--context-file", "-c", default=None, type=click.Path(exists=True),
              help="Seed the session with a local .md context file")
@click.option("--no-header", is_flag=True, default=False,
              help="Suppress the node status header")
@pass_meta
def chat(meta, persona, model, context_file, no_header):
    """
    \b
    Open the interactive terminal channel.

    \b
    Node interface active. Secure channel established.
    Ctrl+C  — close session and run auto-documentation protocol
    Ctrl+S  — save current context snapshot to disk

    \b
    Examples:
      metamatrix chat
      metamatrix chat --persona hermetic --model ollama
      metamatrix chat --context-file briefing.md
    """
    from cli.session.interactive import InteractiveSession

    cfg = meta.config.copy()
    if persona:
        cfg["persona"] = persona
    if model:
        cfg["model"] = model

    seed_context = None
    if context_file:
        with open(context_file) as f:
            seed_context = f.read()

    session = InteractiveSession(config=cfg, show_header=not no_header)
    session.run(seed_context=seed_context)


# ─────────────────────────────────────────────
# CONTEXT group
# ─────────────────────────────────────────────
@cli.group()
@pass_meta
def context(meta):
    """
    \b
    Context channel — synchronize local .md knowledge files with the node.

    \b
    Node interface active. Context store online.
    Local path: ~/.metamatrix/context/
    """


@context.command("push")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--key", "-k", default=None,
              help="Override context key (defaults to filename without extension)")
@pass_meta
def context_push(meta, file_path, key):
    """
    \b
    Upload a local .md file to the node context store.

    \b
    Transmission initiated. Context file will be available
    across all sessions after upload.

    \b
    Examples:
      metamatrix context push briefing.md
      metamatrix context push mission.md --key current_mission
    """
    mgr = ContextManager(api_url=meta.config.get("api_url"))
    result = mgr.push_context(file_path, key=key)
    meta.persona.render(f"Context uploaded: {result}", "success")


@context.command("pull")
@click.argument("key")
@click.option("--output", "-o", default=None,
              help="Output file path (defaults to ~/.metamatrix/context/<key>.md)")
@pass_meta
def context_pull(meta, key, output):
    """
    \b
    Download a context file from the node by key.

    \b
    Initiating retrieval from node context store.
    File will be written to local context directory.

    \b
    Examples:
      metamatrix context pull current_mission
      metamatrix context pull briefing --output ./local_briefing.md
    """
    mgr = ContextManager(api_url=meta.config.get("api_url"))
    path = mgr.pull_context(key, output_path=output)
    meta.persona.render(f"Context received: {path}", "success")


@context.command("list")
@click.option("--remote", is_flag=True, default=False,
              help="List contexts on node rather than local store")
@pass_meta
def context_list(meta, remote):
    """
    \b
    Display all context files in the local store.

    \b
    Scanning context store...
    Each entry represents a loaded knowledge fragment.

    \b
    Examples:
      metamatrix context list
      metamatrix context list --remote
    """
    mgr = ContextManager(api_url=meta.config.get("api_url"))
    if remote:
        contexts = mgr.list_contexts(remote=True)
    else:
        contexts = mgr.list_contexts()
    meta.persona.render_list("Context Store", contexts)


@context.command("sync")
@pass_meta
def context_sync(meta):
    """
    \b
    Synchronize all local context files with the node.

    \b
    Full sync protocol initiated.
    All fragments will be uploaded and verified.

    \b
    Examples:
      metamatrix context sync
    """
    mgr = ContextManager(api_url=meta.config.get("api_url"))
    results = mgr.sync_all()
    meta.persona.render(f"Sync complete. {len(results)} files processed.", "success")


# ─────────────────────────────────────────────
# SESSION group
# ─────────────────────────────────────────────
@cli.group()
@pass_meta
def session(meta):
    """
    \b
    Session management — documentation, logging, and closing protocols.

    \b
    Node interface active. Session manager online.
    """


@session.command("close")
@click.option("--repo", "-r", default=None, type=click.Path(),
              help="Git repo path for auto-commit (defaults to current directory)")
@click.option("--no-commit", is_flag=True, default=False,
              help="Write session log but skip the git commit step")
@click.option("--session-file", "-f", default=None, type=click.Path(exists=True),
              help="Load messages from a JSON session file instead of stdin")
@pass_meta
def session_close(meta, repo, no_commit, session_file):
    """
    \b
    Run the session closing protocol.

    \b
    Initiating auto-documentation sequence:
      1. Summarize session messages
      2. Write log to ~/.metamatrix/sessions/YYYY-MM-DD.md
      3. Git commit the session log (unless --no-commit)

    \b
    Examples:
      metamatrix session close
      metamatrix session close --repo ~/projects/myrepo
      metamatrix session close --no-commit
    """
    import json as _json

    messages = []
    if session_file:
        with open(session_file) as f:
            messages = _json.load(f)
    else:
        meta.persona.render("No session file provided. Generating empty session log.", "warning")

    repo_path = repo or os.getcwd()
    skip_commit = no_commit

    result = close_session(
        messages=messages,
        repo_path=repo_path,
        skip_commit=skip_commit,
    )
    meta.persona.render(f"Session closed: {result}", "success")


# ─────────────────────────────────────────────
# AGENT command
# ─────────────────────────────────────────────
@cli.group()
@pass_meta
def agent(meta):
    """
    \b
    Agent delegation — spawn, monitor, and collect sub-agent outputs.

    \b
    Node interface active. Agent spawner online.
    Agents run as isolated background threads.
    Output saved to ~/.metamatrix/agents/
    """


@agent.command("spawn")
@click.argument("task")
@click.option("--model", "-m", default=None,
              help="Model for this agent [claude|gpt|gemini|ollama|lmstudio|bitnet]")
@click.option("--context-file", "-c", default=None, type=click.Path(exists=True),
              help="Context .md file to seed this agent")
@click.option("--wait", "-w", is_flag=True, default=False,
              help="Block until agent completes and print output")
@pass_meta
def agent_spawn(meta, task, model, context_file, wait):
    """
    \b
    Delegate a task to an isolated sub-agent.

    \b
    Sub-agent initialized. Fresh context loaded.
    Agent ID will be returned for status tracking.

    \b
    Examples:
      metamatrix agent spawn "summarize the hermetic_law_map.md"
      metamatrix agent spawn "write a Python script for X" --model ollama
      metamatrix agent spawn "research topic Y" --wait
    """
    config = meta.config.copy()
    if model:
        config["model"] = model

    context_data = None
    if context_file:
        with open(context_file) as f:
            context_data = f.read()

    spawner = SpawnAgent(config=config)
    agent_id = spawner.spawn(task=task, context=context_data, model=config.get("model"))
    meta.persona.render(f"Agent spawned. ID: {agent_id}", "success")

    if wait:
        import time
        meta.persona.render("Waiting for agent completion...", "info")
        while True:
            status = spawner.get_status(agent_id)
            if status.get("status") in ("completed", "error"):
                break
            time.sleep(1)
        output = spawner.collect(agent_id)
        meta.persona.render("Agent output:", "info")
        click.echo(output)


@agent.command("list")
@pass_meta
def agent_list(meta):
    """
    \b
    Display all active and completed sub-agents.

    \b
    Scanning agent registry...

    \b
    Examples:
      metamatrix agent list
    """
    spawner = SpawnAgent(config=meta.config)
    agents = spawner.list_agents()
    meta.persona.render_list("Active Agents", [f"{a['id']}: {a['status']} — {a['task'][:60]}" for a in agents])


@agent.command("collect")
@click.argument("agent_id")
@pass_meta
def agent_collect(meta, agent_id):
    """
    \b
    Retrieve output from a completed sub-agent.

    \b
    Collecting agent payload...

    \b
    Examples:
      metamatrix agent collect abc123
    """
    spawner = SpawnAgent(config=meta.config)
    output = spawner.collect(agent_id)
    if output:
        click.echo(output)
    else:
        meta.persona.render(f"No output found for agent {agent_id}", "warning")


# ─────────────────────────────────────────────
# PERSONA command
# ─────────────────────────────────────────────
@cli.command()
@click.argument("mode", type=click.Choice(list(PERSONAS.keys())))
@pass_meta
def persona(meta, mode):
    """
    \b
    Switch the active output persona.

    \b
    Persona recalibration initiated.
    All subsequent output will reflect the selected mode.

    \b
    Available modes:
      sovereign  — Direct, no hedging, Hermetic references natural
      technical  — Precise, code-first, minimal prose
      hermetic   — Philosophical, Law references in every response
      minimal    — One sentence max, terminal output style
      verbose    — Full context, markdown formatted, detailed

    \b
    Examples:
      metamatrix persona sovereign
      metamatrix persona hermetic
      metamatrix persona minimal
    """
    cfg = load_config()
    cfg["persona"] = mode
    save_config(cfg)
    meta.persona = PersonaEngine(mode)
    meta.persona.render(f"Persona set to: {mode}", "success")


# ─────────────────────────────────────────────
# MODEL command
# ─────────────────────────────────────────────
@cli.command()
@click.argument("name", type=click.Choice(["claude", "gpt", "gemini", "ollama", "lmstudio", "bitnet"]))
@pass_meta
def model(meta, name):
    """
    \b
    Switch the active inference model.

    \b
    Model routing updated. New inference path activated.
    Local models (ollama/lmstudio/bitnet) require local server.

    \b
    Available models:
      claude    — Anthropic Claude (via API)
      gpt       — OpenAI GPT-4 (via API)
      gemini    — Google Gemini (via API)
      ollama    — Local Ollama instance at localhost:11434
      lmstudio  — LM Studio API at localhost:1234
      bitnet    — llama.cpp BitNet b1.58 at localhost:8080

    \b
    Examples:
      metamatrix model set claude
      metamatrix model set ollama
      metamatrix model set bitnet
    """
    cfg = load_config()
    cfg["model"] = name
    save_config(cfg)
    meta.persona.render(f"Model routing updated: {name}", "success")


# ─────────────────────────────────────────────
# STATUS command
# ─────────────────────────────────────────────
@cli.command()
@pass_meta
def status(meta):
    """
    \b
    Display current node configuration and channel status.

    \b
    Node status report initiated.

    \b
    Examples:
      metamatrix status
    """
    from cli.models.local import auto_detect_local_model

    cfg = meta.config
    detected = auto_detect_local_model()

    lines = [
        f"Persona    : {cfg.get('persona', 'sovereign')}",
        f"Model      : {cfg.get('model', 'claude')}",
        f"API URL    : {cfg.get('api_url', 'http://localhost:8001/api')}",
        f"Config     : {CONFIG_FILE}",
        f"Context    : {Path.home() / '.metamatrix' / 'context'}",
        f"Sessions   : {Path.home() / '.metamatrix' / 'sessions'}",
        f"Local model: {detected or 'none detected'}",
    ]
    meta.persona.render_list("Node Status", lines)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    cli(obj=MetaCtx())

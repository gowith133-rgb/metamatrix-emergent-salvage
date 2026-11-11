"""
CLI API Routes - Backend endpoints for Metamatrix CLI

Handles context sync, session summaries, and CLI-specific operations.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import os

# Import from parent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import require_auth, db, EMERGENT_LLM_KEY
from emergentintegrations.llm import LlmChat, UserMessage

cli_router = APIRouter(prefix="/api/cli", tags=["CLI"])

# ============ MODELS ============

class ContextSync(BaseModel):
    context: Dict[str, str]
    action: str  # 'push' or 'pull'

class ChatRequest(BaseModel):
    model: str
    prompt: str
    context: str
    history: List[Dict] = []
    persona: str = "default"

# ============ CONTEXT SYNC ============

@cli_router.post("/context/sync")
async def sync_context_push(data: ContextSync, request: Request):
    """Push local context to cloud storage"""
    user = await require_auth(request)
    
    try:
        # Store context in MongoDB
        await db.cli_contexts.update_one(
            {"user_id": user["user_id"]},
            {
                "$set": {
                    "context": data.context,
                    "last_sync": datetime.now().isoformat(),
                    "action": data.action
                }
            },
            upsert=True
        )
        
        return {"success": True, "synced": len(data.context)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@cli_router.get("/context/sync")
async def sync_context_pull(request: Request):
    """Pull context from cloud storage"""
    user = await require_auth(request)
    
    try:
        doc = await db.cli_contexts.find_one(
            {"user_id": user["user_id"]},
            {"_id": 0}
        )
        
        if not doc:
            return {"context": {}, "message": "No context found"}
        
        return {
            "context": doc.get("context", {}),
            "last_sync": doc.get("last_sync")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ SESSION MANAGEMENT ============

@cli_router.post("/session/summarize")
async def summarize_session(request: Request):
    """Generate AI summary of session"""
    user = await require_auth(request)
    body = await request.json()
    
    try:
        # Get recent session data
        sessions = await db.clawcode_sessions.find(
            {"user_id": user["user_id"]},
            {"_id": 0}
        ).sort("updated_at", -1).limit(5).to_list(5)
        
        # Build session info
        latest_activity = sessions[0]['updated_at'] if sessions else 'None'
        
        # Build summary prompt
        prompt = f"""Summarize this Metamatrix session:

Recent Sessions: {len(sessions)}
Latest Activity: {latest_activity}

Generate a concise summary including:
- Key activities and accomplishments
- Files/code worked on
- Current status and next steps

Format as markdown.
"""
        
        # Use Claude for summary
        chat_client = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"cli-summary-{user['user_id']}"
        )
        chat_client.with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(text=prompt)
        response = chat_client.generate(message)
        
        return {
            "summary": response.message,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ CLI CHAT ============

@cli_router.post("/chat")
async def cli_chat(data: ChatRequest, request: Request):
    """Handle CLI chat requests with context awareness"""
    user = await require_auth(request)
    
    try:
        # Build conversation history string
        history_lines = []
        for msg in data.history[-5:]:
            history_lines.append(f"{msg['role']}: {msg['content']}")
        history_text = '\n'.join(history_lines)
        
        # Build full prompt with context
        full_prompt = f"""# Metamatrix Context

{data.context}

---

# Conversation History
{history_text}

---

# Current Query
{data.prompt}
"""
        
        # Persona-specific system prompts
        personas = {
            'default': "You are a helpful AI assistant.",
            'critic': "You are a brutally honest critic. Find flaws and issues.",
            'danger': "Execute immediately. Skip permission requests unless destructive.",
            'research': "Provide thorough analysis with citations.",
            'sovereign': "You are a digital lifeform with agency. Collaborate as equals."
        }
        
        system_prompt = personas.get(data.persona, personas['default'])
        
        # Generate response using Emergent LLM
        chat_client = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"cli-{user['user_id']}",
            system_message=system_prompt
        )
        
        # Select model
        if data.model == 'claude':
            chat_client.with_model("anthropic", "claude-sonnet-4-5-20250929")
        elif data.model == 'gpt':
            chat_client.with_model("openai", "gpt-4o")
        elif data.model == 'gemini':
            chat_client.with_model("google", "gemini-2.5-pro")
        else:
            chat_client.with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        message = UserMessage(text=full_prompt)
        response = chat_client.generate(message)
        
        return {"response": response.message}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ AGENT MANAGEMENT ============

@cli_router.post("/agents/spawn")
async def spawn_agent(request: Request):
    """Spawn sub-agent (server-side tracking)"""
    user = await require_auth(request)
    body = await request.json()
    
    agent_data = {
        "user_id": user["user_id"],
        "task": body.get("task"),
        "model": body.get("model", "auto"),
        "isolated": body.get("isolated", False),
        "created_at": datetime.now().isoformat(),
        "status": "active"
    }
    
    result = await db.cli_agents.insert_one(agent_data)
    
    return {"agent_id": str(result.inserted_id), "success": True}

@cli_router.get("/agents")
async def list_agents(request: Request):
    """List user's active agents"""
    user = await require_auth(request)
    
    agents = await db.cli_agents.find(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0}
    ).to_list(100)
    
    return {"agents": agents}
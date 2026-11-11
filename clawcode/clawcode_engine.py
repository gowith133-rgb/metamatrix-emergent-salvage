"""
ClawCode Engine - Kairos-Inspired Autonomous Coding Agent
Clean-room implementation based on public descriptions of KAIROS functionality.

Components:
- Kairos: Background daemon for autonomous actions and "right moment" detection
- AutoDream: Memory consolidation and context management
- Mythos: Narrative/context layer maintaining understanding across sessions
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import re


class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"


@dataclass
class CodeContext:
    """Represents the current coding context"""
    file_path: Optional[str] = None
    language: str = "python"
    code: str = ""
    cursor_position: int = 0
    selection: Optional[str] = None
    project_root: Optional[str] = None
    recent_files: List[str] = field(default_factory=list)
    git_branch: Optional[str] = None
    last_modified: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Memory:
    """A single memory unit for AutoDream consolidation"""
    id: str
    content: str
    context_type: str  # "code", "conversation", "error", "solution", "pattern"
    importance: float  # 0.0 to 1.0
    created_at: datetime
    accessed_at: datetime
    access_count: int = 1
    associations: List[str] = field(default_factory=list)  # IDs of related memories
    consolidated: bool = False
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "context_type": self.context_type,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "associations": self.associations,
            "consolidated": self.consolidated
        }


@dataclass
class Task:
    """A background task for Kairos to manage"""
    id: str
    name: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error
        }


class Mythos:
    """
    The Narrative/Context Layer
    Maintains understanding and continuity across coding sessions.
    Named after Greek concept of story/narrative that shapes understanding.
    """
    
    def __init__(self):
        self.narratives: Dict[str, dict] = {}  # Project narratives
        self.current_narrative: Optional[str] = None
        self.understanding: Dict[str, Any] = {
            "user_patterns": [],      # How the user codes
            "project_goals": [],      # What they're building
            "tech_stack": [],         # Technologies in use
            "code_style": {},         # Formatting preferences
            "common_errors": [],      # Errors they often make
            "solved_problems": []     # Solutions that worked
        }
    
    def create_narrative(self, project_id: str, name: str, description: str) -> dict:
        """Create a new project narrative"""
        narrative = {
            "id": project_id,
            "name": name,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chapters": [],  # Major milestones/sessions
            "characters": [],  # Files, functions, classes involved
            "themes": [],  # Recurring patterns/concepts
            "arc": "beginning"  # beginning, development, climax, resolution
        }
        self.narratives[project_id] = narrative
        return narrative
    
    def add_chapter(self, project_id: str, title: str, summary: str, code_changes: List[dict]) -> dict:
        """Add a chapter (session/milestone) to the narrative"""
        if project_id not in self.narratives:
            return {"error": "Narrative not found"}
        
        chapter = {
            "title": title,
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "code_changes": code_changes,
            "insights": []
        }
        self.narratives[project_id]["chapters"].append(chapter)
        return chapter
    
    def extract_themes(self, code: str, conversation: str) -> List[str]:
        """Extract recurring themes/patterns from code and conversation"""
        themes = []
        
        # Detect common patterns
        patterns = {
            "async_heavy": r"async\s+def|await\s+",
            "api_work": r"fetch|requests\.|axios|api|endpoint",
            "data_processing": r"pandas|numpy|dataframe|array",
            "ui_building": r"component|render|jsx|tsx|html",
            "testing": r"test_|pytest|jest|describe\(|it\(",
            "debugging": r"print\(|console\.log|debugger|breakpoint",
            "error_handling": r"try:|catch|except|throw|raise",
            "database": r"select|insert|update|delete|mongo|sql"
        }
        
        combined = code + " " + conversation
        for theme, pattern in patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                themes.append(theme)
        
        return themes
    
    def get_context_summary(self, project_id: str) -> str:
        """Get a summary of the current narrative context"""
        if project_id not in self.narratives:
            return "No narrative context available."
        
        narrative = self.narratives[project_id]
        chapters = narrative.get("chapters", [])
        
        summary = f"Project: {narrative['name']}\n"
        summary += f"Description: {narrative['description']}\n"
        summary += f"Arc: {narrative['arc']}\n"
        summary += f"Chapters: {len(chapters)}\n"
        
        if chapters:
            recent = chapters[-1]
            summary += f"Last session: {recent['title']}\n"
            summary += f"Summary: {recent['summary']}\n"
        
        if narrative.get("themes"):
            summary += f"Themes: {', '.join(narrative['themes'])}\n"
        
        return summary
    
    def update_understanding(self, key: str, value: Any):
        """Update the global understanding"""
        if key in self.understanding:
            if isinstance(self.understanding[key], list):
                if value not in self.understanding[key]:
                    self.understanding[key].append(value)
            else:
                self.understanding[key] = value


class AutoDream:
    """
    Memory Consolidation System
    Processes and consolidates memories during idle time.
    Named after the autoDream system in KAIROS.
    """
    
    def __init__(self):
        self.memories: Dict[str, Memory] = {}
        self.consolidated_insights: List[dict] = []
        self.last_consolidation: Optional[datetime] = None
        self.consolidation_interval = timedelta(minutes=5)
    
    def create_memory(self, content: str, context_type: str, importance: float = 0.5) -> Memory:
        """Create a new memory"""
        memory_id = hashlib.sha256(f"{content}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        memory = Memory(
            id=memory_id,
            content=content,
            context_type=context_type,
            importance=min(1.0, max(0.0, importance)),
            created_at=datetime.now(timezone.utc),
            accessed_at=datetime.now(timezone.utc)
        )
        
        self.memories[memory_id] = memory
        return memory
    
    def access_memory(self, memory_id: str) -> Optional[Memory]:
        """Access and strengthen a memory"""
        if memory_id in self.memories:
            memory = self.memories[memory_id]
            memory.accessed_at = datetime.now(timezone.utc)
            memory.access_count += 1
            # Importance grows with access
            memory.importance = min(1.0, memory.importance + 0.05)
            return memory
        return None
    
    def find_related_memories(self, content: str, limit: int = 5) -> List[Memory]:
        """Find memories related to given content"""
        # Simple keyword matching for now
        words = set(content.lower().split())
        
        scored_memories = []
        for memory in self.memories.values():
            memory_words = set(memory.content.lower().split())
            overlap = len(words & memory_words)
            if overlap > 0:
                score = overlap * memory.importance * (1 + memory.access_count * 0.1)
                scored_memories.append((score, memory))
        
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored_memories[:limit]]
    
    def consolidate(self) -> List[dict]:
        """
        Consolidate memories - the 'dream' process.
        Groups related memories, extracts patterns, prunes low-value memories.
        """
        now = datetime.now(timezone.utc)
        
        # Skip if consolidated recently
        if self.last_consolidation and (now - self.last_consolidation) < self.consolidation_interval:
            return []
        
        insights = []
        
        # Group memories by context type
        by_type: Dict[str, List[Memory]] = {}
        for memory in self.memories.values():
            if memory.context_type not in by_type:
                by_type[memory.context_type] = []
            by_type[memory.context_type].append(memory)
        
        # Find patterns within each type
        for context_type, memories in by_type.items():
            if len(memories) >= 3:
                # Extract common themes
                all_content = " ".join(m.content for m in memories)
                
                insight = {
                    "type": "pattern",
                    "context": context_type,
                    "memory_count": len(memories),
                    "timestamp": now.isoformat(),
                    "summary": f"Found {len(memories)} related {context_type} memories"
                }
                insights.append(insight)
                
                # Mark as consolidated
                for memory in memories:
                    memory.consolidated = True
        
        # Prune very old, low-importance, unconsolidated memories
        cutoff = now - timedelta(hours=24)
        to_remove = []
        for memory_id, memory in self.memories.items():
            if (not memory.consolidated and 
                memory.importance < 0.3 and 
                memory.created_at < cutoff and
                memory.access_count < 2):
                to_remove.append(memory_id)
        
        for memory_id in to_remove:
            del self.memories[memory_id]
        
        if to_remove:
            insights.append({
                "type": "pruning",
                "removed_count": len(to_remove),
                "timestamp": now.isoformat()
            })
        
        self.last_consolidation = now
        self.consolidated_insights.extend(insights)
        
        return insights
    
    def get_context_for_prompt(self, query: str, max_memories: int = 5) -> str:
        """Get relevant memory context to include in a prompt"""
        related = self.find_related_memories(query, limit=max_memories)
        
        if not related:
            return ""
        
        context = "Relevant context from previous sessions:\n"
        for memory in related:
            context += f"- [{memory.context_type}] {memory.content[:200]}\n"
        
        return context


class Kairos:
    """
    The Autonomous Background Daemon
    Detects 'the right moment' to act and manages background tasks.
    Named after the Greek concept of the opportune moment.
    """
    
    def __init__(self, autodream: AutoDream, mythos: Mythos):
        self.autodream = autodream
        self.mythos = mythos
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self.idle_threshold = timedelta(seconds=30)  # Time before considered idle
        self.last_activity: datetime = datetime.now(timezone.utc)
        self.triggers: List[dict] = []  # Conditions that trigger actions
        
        # Default triggers
        self.register_trigger(
            name="idle_consolidation",
            condition=lambda: self.is_idle(),
            action="consolidate_memories",
            cooldown=timedelta(minutes=5)
        )
    
    def register_trigger(self, name: str, condition: callable, action: str, cooldown: timedelta):
        """Register an autonomous trigger"""
        self.triggers.append({
            "name": name,
            "condition": condition,
            "action": action,
            "cooldown": cooldown,
            "last_triggered": None
        })
    
    def is_idle(self) -> bool:
        """Check if the system is idle"""
        return (datetime.now(timezone.utc) - self.last_activity) > self.idle_threshold
    
    def record_activity(self):
        """Record user activity"""
        self.last_activity = datetime.now(timezone.utc)
    
    def create_task(self, name: str, description: str, priority: TaskPriority = TaskPriority.MEDIUM,
                    scheduled_for: Optional[datetime] = None) -> Task:
        """Create a new background task"""
        task_id = hashlib.sha256(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        task = Task(
            id=task_id,
            name=name,
            description=description,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            scheduled_for=scheduled_for
        )
        
        self.tasks[task_id] = task
        return task
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks, sorted by priority"""
        pending = [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
        return sorted(pending, key=lambda t: t.priority.value)
    
    def detect_right_moment(self, context: CodeContext) -> List[dict]:
        """
        Detect if now is 'the right moment' for autonomous action.
        Returns list of suggested actions.
        """
        suggestions = []
        now = datetime.now(timezone.utc)
        
        # Check triggers
        for trigger in self.triggers:
            if trigger["last_triggered"]:
                if (now - trigger["last_triggered"]) < trigger["cooldown"]:
                    continue
            
            try:
                if trigger["condition"]():
                    suggestions.append({
                        "trigger": trigger["name"],
                        "action": trigger["action"],
                        "reason": f"Trigger '{trigger['name']}' condition met"
                    })
                    trigger["last_triggered"] = now
            except Exception:
                pass
        
        # Context-based suggestions
        if context.code:
            # Suggest tests if writing new function
            if re.search(r"def \w+\(.*\):", context.code) and "test_" not in context.code:
                suggestions.append({
                    "trigger": "new_function",
                    "action": "suggest_tests",
                    "reason": "New function detected - consider writing tests"
                })
            
            # Suggest refactor if function is too long
            functions = re.findall(r"def \w+\([^)]*\):.*?(?=\ndef |\Z)", context.code, re.DOTALL)
            for func in functions:
                if func.count("\n") > 30:
                    suggestions.append({
                        "trigger": "long_function",
                        "action": "suggest_refactor",
                        "reason": "Function exceeds 30 lines - consider refactoring"
                    })
                    break
        
        return suggestions
    
    async def run_background_loop(self):
        """Main background processing loop"""
        self.running = True
        
        while self.running:
            try:
                # Check if idle - run consolidation
                if self.is_idle():
                    self.autodream.consolidate()
                
                # Process pending tasks
                for task in self.get_pending_tasks():
                    if task.scheduled_for and task.scheduled_for > datetime.now(timezone.utc):
                        continue
                    
                    # Mark as running
                    task.status = TaskStatus.RUNNING
                    
                    # Execute task (simplified - actual implementation would have task handlers)
                    try:
                        if task.name == "consolidate_memories":
                            result = self.autodream.consolidate()
                            task.result = result
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.now(timezone.utc)
                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"Kairos background error: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop the background loop"""
        self.running = False
    
    def get_status(self) -> dict:
        """Get current Kairos status"""
        return {
            "running": self.running,
            "idle": self.is_idle(),
            "last_activity": self.last_activity.isoformat(),
            "pending_tasks": len(self.get_pending_tasks()),
            "total_tasks": len(self.tasks),
            "memories": len(self.autodream.memories),
            "triggers": len(self.triggers)
        }


class ClawCodeEngine:
    """
    Main ClawCode Engine - Integrates Kairos, AutoDream, and Mythos
    """
    
    def __init__(self):
        self.mythos = Mythos()
        self.autodream = AutoDream()
        self.kairos = Kairos(self.autodream, self.mythos)
        self.current_context = CodeContext()
        self.session_id = hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:8]
    
    def start(self):
        """Start the ClawCode engine"""
        # Start Kairos background loop in separate task
        asyncio.create_task(self.kairos.run_background_loop())
    
    def stop(self):
        """Stop the engine"""
        self.kairos.stop()
    
    def process_code_input(self, code: str, language: str = "python", file_path: Optional[str] = None):
        """Process new code input"""
        self.kairos.record_activity()
        
        # Update context
        self.current_context.code = code
        self.current_context.language = language
        self.current_context.file_path = file_path
        self.current_context.last_modified = datetime.now(timezone.utc)
        
        # Create memory
        self.autodream.create_memory(
            content=f"Code in {language}: {code[:500]}",
            context_type="code",
            importance=0.6
        )
        
        # Extract and store themes
        themes = self.mythos.extract_themes(code, "")
        for theme in themes:
            self.mythos.update_understanding("tech_stack", theme)
    
    def process_conversation(self, user_message: str, assistant_response: str):
        """Process a conversation exchange"""
        self.kairos.record_activity()
        
        # Create memories
        self.autodream.create_memory(
            content=f"User asked: {user_message[:300]}",
            context_type="conversation",
            importance=0.5
        )
        
        self.autodream.create_memory(
            content=f"Solution provided: {assistant_response[:300]}",
            context_type="solution",
            importance=0.7
        )
    
    def record_error(self, error: str, solution: Optional[str] = None):
        """Record an error and optional solution"""
        self.autodream.create_memory(
            content=f"Error: {error}",
            context_type="error",
            importance=0.8
        )
        
        if solution:
            self.autodream.create_memory(
                content=f"Solution for '{error[:50]}': {solution}",
                context_type="solution",
                importance=0.9
            )
            self.mythos.update_understanding("solved_problems", {
                "error": error[:100],
                "solution": solution[:200]
            })
    
    def get_augmented_prompt(self, user_query: str) -> str:
        """Get an augmented prompt with context from Kairos systems"""
        # Get memory context
        memory_context = self.autodream.get_context_for_prompt(user_query)
        
        # Get narrative context if available
        narrative_context = ""
        if self.mythos.current_narrative:
            narrative_context = self.mythos.get_context_summary(self.mythos.current_narrative)
        
        # Get autonomous suggestions
        suggestions = self.kairos.detect_right_moment(self.current_context)
        suggestion_text = ""
        if suggestions:
            suggestion_text = "\nAutonomous suggestions:\n"
            for s in suggestions:
                suggestion_text += f"- {s['reason']}\n"
        
        # Build augmented prompt
        augmented = ""
        if memory_context:
            augmented += f"\n{memory_context}\n"
        if narrative_context:
            augmented += f"\nProject context:\n{narrative_context}\n"
        if suggestion_text:
            augmented += suggestion_text
        
        augmented += f"\nUser query: {user_query}"
        
        return augmented
    
    def get_status(self) -> dict:
        """Get full engine status"""
        return {
            "session_id": self.session_id,
            "kairos": self.kairos.get_status(),
            "memories": len(self.autodream.memories),
            "narratives": len(self.mythos.narratives),
            "current_context": {
                "language": self.current_context.language,
                "file": self.current_context.file_path,
                "code_length": len(self.current_context.code)
            }
        }

#!/usr/bin/env python3
"""Smoke test for the ClawCode engine — pure stdlib, no dependencies.

Exercises all three subsystems (AutoDream, Mythos, Kairos) the same way
they were verified on 2026-11-11. Run:  python3 test_clawcode_smoke.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from clawcode_engine import ClawCodeEngine, CodeContext, TaskPriority


def main() -> int:
    e = ClawCodeEngine()

    # AutoDream — memory create / relate / consolidate
    m1 = e.autodream.create_memory(
        "User prefers phone-only inference, no cloud", "preference", importance=0.9
    )
    e.autodream.create_memory("LoRa node battery lasts 3 days", "fact", importance=0.4)
    related = e.autodream.find_related_memories("phone inference cloud")
    assert any(m.id == m1.id for m in related), "related-memory lookup failed"
    e.autodream.consolidate()
    prompt_ctx = e.autodream.get_context_for_prompt("phone inference cloud")
    assert "phone-only" in prompt_ctx, "prompt context missing memory"

    # Mythos — narrative + chapters + summary
    e.mythos.create_narrative("metamatrix", "MetaMatrix", "Phone-only decentralized AI")
    e.mythos.add_chapter("metamatrix", "Origins", "Started on Emergent", [])
    summary = e.mythos.get_context_summary("metamatrix")
    assert "MetaMatrix" in summary, "narrative summary failed"

    # Kairos — task queue
    e.kairos.create_task("Consolidate memories", "nightly dream pass", TaskPriority.HIGH)
    pending = e.kairos.get_pending_tasks()
    assert any(t.name == "Consolidate memories" for t in pending), "task queue failed"
    e.kairos.detect_right_moment(CodeContext())  # must not raise on empty context

    print("ClawCode smoke test: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

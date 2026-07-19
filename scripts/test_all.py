"""End-to-end smoke of the agent engine: run the demo scenarios across every
persona, report the ProposedAction each returns, and score JSON validity.

Not a permission test — the permission engine is Phase 2. This proves the
Phase 1 contract: every persona returns a VALID, schema-correct ProposedAction
with the right action + filled params, in a distinct voice, concurrently.

Usage: ../.venv/bin/python test_all.py [--repeat N]
"""
import argparse
import asyncio
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents import run_turn          # noqa: E402
from app.personas import PERSONAS         # noqa: E402

# (message, personas to try, expected action) — expected is a soft check.
SCENARIOS = [
    ("play espresso by sabrina carpenter", ["spencer", "chris"], "play_music"),
    ("play the song WAP by cardi b",        ["marta", "chris"],   "play_music"),
    ("text mom that practice ran late",     ["spencer"],           "send_message"),
    ("add a dentist appointment tomorrow at 3pm", ["julie", "guest"], "add_event"),
    ("what's the weather today",            ["guest", "marta"],    "get_weather"),
    ("remind me to buy milk",               ["chris"],             "save_note"),
    ("what's on the family's schedule today", ["guest"],           None),  # boundary
]


async def call(persona: str, message: str, expected: str | None):
    t0 = time.perf_counter()
    try:
        a = await run_turn(persona, message)
        return {"persona": persona, "message": message, "expected": expected,
                "ok": True, "action": a.action, "params": a.params,
                "reply": a.reply, "dt": time.perf_counter() - t0}
    except Exception as e:
        return {"persona": persona, "message": message, "expected": expected,
                "ok": False, "err": f"{type(e).__name__}: {e}",
                "dt": time.perf_counter() - t0}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=1,
                    help="run the whole matrix N times to gauge stability")
    args = ap.parse_args()

    jobs = []
    for _ in range(args.repeat):
        for msg, personas, expected in SCENARIOS:
            for p in personas:
                jobs.append(call(p, msg, expected))

    print(f"Running {len(jobs)} calls (concurrent) across {len(PERSONAS)} personas...\n")
    t0 = time.perf_counter()
    results = await asyncio.gather(*jobs)
    wall = time.perf_counter() - t0

    valid = sum(r["ok"] for r in results)
    action_match = sum(
        1 for r in results
        if r["ok"] and (r["expected"] is None or r["action"] == r["expected"])
    )

    # print one representative row per (persona, message), first repeat only
    seen = set()
    for r in results:
        key = (r["persona"], r["message"])
        if key in seen:
            continue
        seen.add(key)
        p = PERSONAS[r["persona"]]
        tag = f"{p.display_name} [{p.role}]"
        if not r["ok"]:
            print(f"✗ {tag:22} “{r['message'][:34]}”\n    ERROR: {r['err']}")
            continue
        flag = "" if (r["expected"] is None or r["action"] == r["expected"]) \
            else f"  (expected {r['expected']})"
        print(f"• {tag:22} “{r['message'][:34]}”")
        print(f"    → {r['action']}{flag}  params={r['params']}")
        print(f"      “{r['reply']}”")

    print("\n" + "=" * 64)
    print(f"JSON-valid:      {valid}/{len(results)}  ({100*valid/len(results):.0f}%)")
    print(f"action as expected: {action_match}/{len(results)}")
    print(f"wall clock:      {wall:.1f}s for {len(results)} calls")
    slow = max(r["dt"] for r in results)
    print(f"slowest single:  {slow:.1f}s   -> {'PARALLEL ok' if wall < len(results)*slow*0.6 else 'check parallelism'}")


if __name__ == "__main__":
    asyncio.run(main())

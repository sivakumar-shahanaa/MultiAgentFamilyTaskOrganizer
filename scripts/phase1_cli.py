"""Phase 1 CLI test: same request, different persona -> different ProposedAction.

Runs the message for each persona CONCURRENTLY (one model, parallel slots),
so this doubles as a live re-proof of Phase 0 under structured output.

Usage:
  ../.venv/bin/python phase1_cli.py                       # default demo message
  ../.venv/bin/python phase1_cli.py -m "unlock the door" -p guest chris
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents import run_turn  # noqa: E402
from app.personas import PERSONAS  # noqa: E402


async def one(persona: str, message: str) -> tuple[str, float, object]:
    t0 = time.perf_counter()
    try:
        action = await run_turn(persona, message)
    except Exception as e:  # a flaky turn shouldn't kill the comparison
        action = e
    return persona, time.perf_counter() - t0, action


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", default="play espresso by sabrina carpenter")
    ap.add_argument("-p", "--personas", nargs="+", default=["spencer", "chris"],
                    choices=list(PERSONAS), metavar="PERSONA")
    args = ap.parse_args()

    print(f'>>> "{args.message}" as {", ".join(args.personas)} (concurrent)\n')
    t0 = time.perf_counter()
    results = await asyncio.gather(*(one(p, args.message) for p in args.personas))
    wall = time.perf_counter() - t0

    for persona, dt, action in results:
        p = PERSONAS[persona]
        print(f"┌─ {p.display_name}  [role={p.role}]  {dt:.2f}s")
        if isinstance(action, Exception):
            print(f"│ FAILED: {type(action).__name__}: {action}")
        else:
            print(f"│ action: {action.action}  params: {action.params}")
            print(f"│ reply:  {action.reply}")
        print("└" + "─" * 60)

    print(f"\nwall clock {wall:.2f}s for {len(results)} personas "
          f"(sum of singles {sum(dt for _, dt, _ in results):.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())

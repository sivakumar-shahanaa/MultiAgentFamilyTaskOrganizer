"""Phase 0 runtime proof: fire N simultaneous completions at one loaded model.

Proves the whole premise — a single copy of the weights, served with
OLLAMA_NUM_PARALLEL>=N, answers concurrent requests in parallel (one KV cache
per slot) rather than serializing them. If this fails, we need to know in the
first half hour, not at 4pm.

Run:  ../.venv/bin/python smoke_parallel.py
"""
import asyncio
import time

import httpx

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "gemma3:4b"

# Distinct prompts so we can eyeball that each slot answered its own request.
PROMPTS = [
    "In one sentence, what is a good song for focus?",
    "In one sentence, what should I cook tonight?",
    "In one sentence, what is the capital of France?",
]


async def one_call(client: httpx.AsyncClient, idx: int, prompt: str) -> dict:
    t0 = time.perf_counter()
    resp = await client.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "stream": False,
        },
        timeout=120.0,
    )
    dt = time.perf_counter() - t0
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    return {"idx": idx, "latency": dt, "prompt": prompt, "reply": text}


async def main() -> None:
    n = len(PROMPTS)
    print(f"Firing {n} simultaneous completions at {MODEL} ...\n")

    async with httpx.AsyncClient() as client:
        wall_start = time.perf_counter()
        results = await asyncio.gather(
            *(one_call(client, i, p) for i, p in enumerate(PROMPTS))
        )
        wall = time.perf_counter() - wall_start

    for r in sorted(results, key=lambda x: x["idx"]):
        print(f"[slot {r['idx']}] {r['latency']:6.2f}s  {r['reply'][:80]}")

    latencies = [r["latency"] for r in results]
    slowest = max(latencies)
    total_serial = sum(latencies)
    print(
        f"\nwall clock:      {wall:6.2f}s  (all {n} at once)"
        f"\nslowest single:  {slowest:6.2f}s"
        f"\nsum if serial:   {total_serial:6.2f}s"
    )
    # If parallel slots work, wall clock ~= slowest single, NOT the serial sum.
    speedup = total_serial / wall if wall else 0
    verdict = "PARALLEL ✓" if wall < total_serial * 0.75 else "SERIALIZED ✗"
    print(f"speedup:         {speedup:6.2f}x  ->  {verdict}")


if __name__ == "__main__":
    asyncio.run(main())

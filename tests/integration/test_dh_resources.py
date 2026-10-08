"""Resource-isolation contracts for DH CPU work."""

from __future__ import annotations

import threading
import time

import anyio

from app.api import routes_dh


def test_dh_capacity_limiter_caps_concurrent_cpu_jobs() -> None:
    active = 0
    peak = 0
    lock = threading.Lock()

    def work() -> None:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1

    async def run() -> None:
        async with anyio.create_task_group() as tasks:
            for _ in range(routes_dh.DH_CAPACITY_LIMIT * 2):
                tasks.start_soon(routes_dh._run_dh, work)

    anyio.run(run)
    assert peak == routes_dh.DH_CAPACITY_LIMIT

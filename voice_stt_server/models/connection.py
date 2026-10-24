"""Bounded transport waiting around existing synchronous initialization."""
import asyncio
import time


async def wait_initialization(work, *, notify=None, timeout=180, interval=5, late_result=None):
    task = asyncio.create_task(asyncio.to_thread(work))
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("initialization_timeout")
            done, _ = await asyncio.wait({task}, timeout=min(interval, remaining))
            if done:
                return task.result()
            if notify is not None:
                await notify()
    except BaseException:
        # Python cannot kill synchronous native initialization. A result that
        # arrives after timeout/disconnect must not leak a newly built session.
        def cleanup(finished):
            try:
                result = finished.result()
                if late_result is not None:
                    late_result(result)
            except BaseException:
                pass
        task.add_done_callback(cleanup)
        raise

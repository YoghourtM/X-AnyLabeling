"""TCP-style adaptive concurrency for batch VLM requests.

The window starts at one request, doubles every round of successes (slow
start) until the first congestion signal, then grows by one per round
(congestion avoidance) up to the user's limit. A rejection, a timeout or a
request that runs far longer than usual halves the window and pauses growth
for a cooldown period. Signals from requests that were already in flight when
the window shrank are ignored, so one burst only shrinks it once.
"""

import heapq
import itertools
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from .providers import VLMCancelledError, VLMCongestionError, VLMFatalError


class AdaptiveWindow:
    def __init__(
        self,
        max_window,
        cooldown=60.0,
        min_stall_seconds=30.0,
        clock=time.monotonic,
    ):
        self.max_window = max(1, int(max_window))
        self.current = 1
        self.ssthresh = self.max_window
        self.cooldown = float(cooldown)
        self.min_stall_seconds = float(min_stall_seconds)
        self._clock = clock
        self._acked = 0
        self._cooldown_until = float("-inf")
        self._last_decrease = float("-inf")
        self.srtt = None
        self.rttvar = None
        self.decreases = 0

    def in_cooldown(self):
        return self._clock() < self._cooldown_until

    def on_success(self, latency):
        if self.srtt is None:
            self.srtt, self.rttvar = latency, latency / 2
        else:
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - latency)
            self.srtt = 0.875 * self.srtt + 0.125 * latency
        if self.in_cooldown():
            return
        self._acked += 1
        if self._acked < self.current:
            return
        self._acked = 0
        if self.current < self.ssthresh:
            self.current = min(self.current * 2, self.ssthresh)
        else:
            self.current = min(self.current + 1, self.max_window)

    def on_congestion(self, started_at):
        """Shrink once per round; returns True when the window changed."""
        if started_at < self._last_decrease:
            return False
        now = self._clock()
        self.ssthresh = max(1, self.current // 2)
        self.current = self.ssthresh
        self._acked = 0
        self._last_decrease = now
        self._cooldown_until = now + self.cooldown
        self.decreases += 1
        return True

    def stall_seconds(self, hard_timeout):
        """RTO-like threshold after which a running request counts as stuck."""
        if self.srtt is None:
            return float(hard_timeout)
        estimate = self.srtt + 4 * self.rttvar
        return min(float(hard_timeout), max(self.min_stall_seconds, estimate))


@dataclass
class BatchStats:
    total: int
    succeeded: int = 0
    failed: int = 0
    retries: int = 0
    in_flight: int = 0
    window: int = 1
    max_window: int = 1
    aborted: str = ""
    errors: dict = field(default_factory=dict)

    @property
    def done(self):
        return self.succeeded + self.failed


def run_adaptive_batch(
    items,
    work,
    *,
    max_window,
    hard_timeout,
    max_retries=3,
    cooldown=60.0,
    min_stall_seconds=30.0,
    max_consecutive_failures=5,
    is_cancelled=lambda: False,
    on_result=lambda item, result: None,
    on_failure=lambda item, error: None,
    on_status=lambda stats, window: None,
    poll_seconds=0.2,
    clock=time.monotonic,
    sleep=time.sleep,
):
    """Run ``work(item, cancel_event)`` for every item with adaptive concurrency.

    ``on_result`` / ``on_failure`` run on the calling thread as each item
    settles. Returns the final :class:`BatchStats`.
    """
    window = AdaptiveWindow(max_window, cooldown, min_stall_seconds, clock)
    stats = BatchStats(total=len(items), max_window=window.max_window)
    cancel_event = threading.Event()
    queue = deque((item, 0) for item in items)
    retry_heap = []  # (ready_at, seq, item, attempt)
    seq = itertools.count()
    in_flight = {}  # future -> [item, attempt, started_at, flagged_slow]
    consecutive_failures = 0

    def settle_failure(item, attempt, error, congested):
        nonlocal consecutive_failures
        consecutive_failures += 1
        stats.errors[type(error).__name__] = (
            stats.errors.get(type(error).__name__, 0) + 1
        )
        if attempt < max_retries:
            stats.retries += 1
            backoff = (cooldown / 4 if congested else 2.0) * (attempt + 1)
            heapq.heappush(
                retry_heap, (clock() + backoff, next(seq), item, attempt + 1)
            )
        else:
            stats.failed += 1
            on_failure(item, error)

    with ThreadPoolExecutor(
        max_workers=window.max_window, thread_name_prefix="vlm-batch"
    ) as pool:
        while queue or retry_heap or in_flight:
            if not stats.aborted and is_cancelled():
                stats.aborted = "cancelled"
            if stats.aborted:
                cancel_event.set()
                queue.clear()
                retry_heap.clear()
            now = clock()
            while retry_heap and retry_heap[0][0] <= now:
                _, _, item, attempt = heapq.heappop(retry_heap)
                queue.appendleft((item, attempt))
            while queue and len(in_flight) < window.current:
                item, attempt = queue.popleft()
                future = pool.submit(work, item, cancel_event)
                in_flight[future] = [item, attempt, clock(), False]

            stats.in_flight, stats.window = len(in_flight), window.current
            on_status(stats, window)
            if not in_flight:
                sleep(poll_seconds)
                continue
            done, _ = wait(
                tuple(in_flight),
                timeout=poll_seconds,
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                item, attempt, started_at, _ = in_flight.pop(future)
                try:
                    result = future.result()
                except VLMCancelledError:
                    continue
                except VLMFatalError as exc:
                    stats.failed += 1
                    stats.aborted = str(exc)
                    on_failure(item, exc)
                    continue
                except VLMCongestionError as exc:
                    window.on_congestion(started_at)
                    settle_failure(item, attempt, exc, congested=True)
                except Exception as exc:  # noqa: BLE001 - item-level failure
                    settle_failure(item, attempt, exc, congested=False)
                else:
                    consecutive_failures = 0
                    window.on_success(clock() - started_at)
                    stats.succeeded += 1
                    on_result(item, result)
            if (
                not stats.aborted
                and window.current == 1
                and consecutive_failures >= max_consecutive_failures
            ):
                stats.aborted = (
                    f"{consecutive_failures} consecutive failures at "
                    "concurrency 1"
                )
            stall_after = window.stall_seconds(hard_timeout)
            now = clock()
            for entry in in_flight.values():
                if not entry[3] and now - entry[2] > stall_after:
                    # Slow, not dead: shrink the window but let it finish.
                    entry[3] = True
                    window.on_congestion(entry[2])
    stats.in_flight, stats.window = 0, window.current
    on_status(stats, window)
    return stats

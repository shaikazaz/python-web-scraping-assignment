from utils.rate_limiter import RateLimiter


def test_first_call_is_immediate_and_second_waits():
    now = [0.0]
    sleeps = []
    limiter = RateLimiter(1.0, clock=lambda: now[0], sleep=lambda s: (sleeps.append(s), now.__setitem__(0, now[0] + s)))
    limiter.wait()
    limiter.wait()
    assert sleeps == [1.0]


def test_zero_interval_is_noop():
    sleeps = []
    RateLimiter(0, sleep=sleeps.append).wait()
    RateLimiter(-1, sleep=sleeps.append).wait()
    assert sleeps == []


def test_reservations_are_thread_safe():
    import threading
    now = [0.0]
    sleeps = []
    lock = threading.Lock()

    def clock():
        with lock:
            return now[0]

    def sleep(seconds):
        with lock:
            sleeps.append(seconds)
            now[0] += seconds

    limiter = RateLimiter(1.0, clock=clock, sleep=sleep)
    threads = [threading.Thread(target=limiter.wait) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sorted(sleeps) == [1.0, 1.0, 1.0]

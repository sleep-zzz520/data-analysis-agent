"""请求监控指标：请求数 / 状态码分布 / 错误率 / 耗时分位数（纯标准库，内存态）。

对外暴露一个模块级单例 metrics，中间件每次请求调用 record()，
监控端点 /api/metrics 调用 snapshot() 返回当前聚合值。
线程安全；未来如需对接 Prometheus，可在此处加一个 export 方法。
"""
from __future__ import annotations

import threading
import time
from collections import deque

# 耗时样本保留最近 N 条（内存有界，避免长时间运行内存膨胀）
_MAX_LATENCY_SAMPLES = 2000
# 滑动窗口（秒）：窗口内请求数 / 错误率
_WINDOW_SECONDS = 60


class Metrics:
    def __init__(self, max_latency_samples: int = _MAX_LATENCY_SAMPLES,
                 window_seconds: int = _WINDOW_SECONDS):
        self._lock = threading.Lock()
        self._total = 0
        self._status_counts: dict[int, int] = {}
        self._latency_samples: deque = deque(maxlen=max_latency_samples)
        self._window: deque = deque()          # (timestamp, is_5xx)
        self._window_seconds = window_seconds
        self._started_at = time.time()

    def record(self, status: int, duration_ms: float) -> None:
        with self._lock:
            self._total += 1
            self._status_counts[status] = self._status_counts.get(status, 0) + 1
            self._latency_samples.append(duration_ms)
            now = time.time()
            self._window.append((now, status >= 500))
            self._expire_window(now)

    def snapshot(self) -> dict:
        with self._lock:
            now = time.time()
            self._expire_window(now)
            samples = sorted(self._latency_samples)
            n = len(samples)
            total_5xx = sum(c for s, c in self._status_counts.items() if s >= 500)
            window_requests = len(self._window)
            window_5xx = sum(1 for _, err in self._window if err)
            return {
                "uptime_seconds": round(now - self._started_at, 1),
                "total_requests": self._total,
                "status_counts": dict(sorted(self._status_counts.items())),
                "error_rate_5xx": round(total_5xx / self._total, 4) if self._total else 0.0,
                "window": {
                    "seconds": self._window_seconds,
                    "requests": window_requests,
                    "error_rate_5xx": round(window_5xx / window_requests, 4) if window_requests else 0.0,
                },
                "latency_ms": {
                    "avg": round(sum(samples) / n, 2) if n else None,
                    "p50": self._percentile(samples, 0.50),
                    "p95": self._percentile(samples, 0.95),
                    "p99": self._percentile(samples, 0.99),
                    "max": round(samples[-1], 2) if n else None,
                },
            }

    # ── internal ────────────────────────────────────────────────────────────
    def _expire_window(self, now: float) -> None:
        while self._window and now - self._window[0][0] > self._window_seconds:
            self._window.popleft()

    @staticmethod
    def _percentile(sorted_samples: list, p: float):
        if not sorted_samples:
            return None
        idx = min(len(sorted_samples) - 1, int(p * len(sorted_samples)))
        return round(sorted_samples[idx], 2)


metrics = Metrics()

from __future__ import annotations

from datetime import datetime

from app.services.optimizer import is_after_cutoff, optimize_pending_with_priority


class Scheduler:
    @staticmethod
    def should_auto_optimize(now: datetime) -> bool:
        return is_after_cutoff(now)

    @staticmethod
    def run_auto_optimization(stops, now: datetime):
        if not Scheduler.should_auto_optimize(now):
            return list(stops)
        return optimize_pending_with_priority(stops, now)

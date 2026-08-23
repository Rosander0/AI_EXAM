"""Suspicion score accumulation, continuous decay, and Event emission for SANKET.

CRITICAL INVARIANTS:
1. Time delta dt derives strictly from Frame.t, NEVER from wall-clock or frame counts.
2. Continuous decay: S = max(0, S - D * dt) + sum(w_i * E_i)
   makes isolated movements fade away, while sustained/repeated actions accumulate.
3. Ranking metric is SUSTAINED_SECONDS (cumulative time above alert threshold),
   not peak spikes — directly aligning with the Hackathon Extension Goal.
4. Output Event objects match DATA_CONTRACT.md exactly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Set
import numpy as np

from sanket.config import ConfigDict
from sanket.rules import RuleFiring
from sanket.seats import Seat


@dataclass
class Event:
    """Represents a persisted behavioral event matching DATA_CONTRACT.md."""
    event_id: str
    session_id: str
    seat_id: str
    track_id: Optional[int]
    t_start: float
    t_end: float
    frame_start: int
    frame_end: int
    rule: str
    points: float
    score_after: float
    confidence: float
    severity: str  # "critical" | "warning" | "info"
    reason: str
    clip_path: Optional[str] = None
    thumb_path: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class ScoringEngine:
    """Manages score accumulation, continuous decay, and Event emission per seat."""

    def __init__(self, config: ConfigDict, session_id: str = "sess_default"):
        self.config = config
        self.session_id = session_id

        score_cfg = config.get("scoring", {})
        self.decay_rate = float(score_cfg.get("decay_rate", 1.5))
        self.alert_thresh = float(score_cfg.get("alert_threshold", 100.0))
        self.realert_s = float(score_cfg.get("realert_seconds", 60.0))
        self.late_multiplier = float(score_cfg.get("late_exam_multiplier", 1.0))
        self.weights: Dict[str, float] = score_cfg.get("weights", {})

        self.alert_cooldown_s = float(score_cfg.get("alert_cooldown_seconds", 15.0))
        self.last_t: Optional[float] = None
        self.event_counter: int = 0

        # Per-seat metadata: seat_id -> dict
        self.last_alert_t: Dict[str, float] = {}
        self.last_alert_by_seat_rule: Dict[tuple[str, str], float] = {}
        self.distinct_rules_set: Dict[str, Set[str]] = {}

    def update(
        self,
        seats: Dict[str, Seat],
        firings_by_seat: Dict[str, List[RuleFiring]],
        t: float,
    ) -> List[Event]:
        """
        Applies time decay, adds rule firing points, updates sustained duration,
        and generates Event instances with time-bound throttling.
        """
        # Calculate dt strictly from Frame.t
        if self.last_t is None:
            dt = 0.0
        else:
            dt = max(0.0, t - self.last_t)
        self.last_t = t

        emitted_events: List[Event] = []

        for sid, seat in seats.items():
            if sid not in self.distinct_rules_set:
                self.distinct_rules_set[sid] = set()

            prev_score = seat.score

            # 1. Apply Continuous Decay: S = max(0, S - D * dt)
            if dt > 0 and seat.score > 0:
                decay_amount = self.decay_rate * dt
                seat.score = max(0.0, seat.score - decay_amount)

            # 2. Accumulate Rule Firings
            seat_firings = firings_by_seat.get(sid, [])
            points_added = 0.0

            for firing in seat_firings:
                weight = self.weights.get(firing.rule, firing.points)
                pts = weight * self.late_multiplier
                points_added += pts
                seat.score += pts
                seat.event_count += 1
                self.distinct_rules_set[sid].add(firing.rule)
                seat.distinct_rules = len(self.distinct_rules_set[sid])
                seat.last_reason = firing.reason

                # Determine Event severity with time-bound throttling
                is_instant_alert = firing.rule in ("object_phone", "object_chit")
                crossed_threshold = prev_score < self.alert_thresh and seat.score >= self.alert_thresh

                rule_key = (sid, firing.rule)
                last_alert_time = self.last_alert_by_seat_rule.get(rule_key, -999.0)
                cooldown_elapsed = (t - last_alert_time) >= self.alert_cooldown_s

                if is_instant_alert or crossed_threshold or (seat.score >= self.alert_thresh and cooldown_elapsed):
                    severity = "critical"
                    self.last_alert_by_seat_rule[rule_key] = t
                    self.last_alert_t[sid] = t
                else:
                    severity = "warning"

                self.event_counter += 1
                evt = Event(
                    event_id=f"evt_{self.event_counter:04d}",
                    session_id=self.session_id,
                    seat_id=sid,
                    track_id=firing.track_id,
                    t_start=round(firing.t_start, 2),
                    t_end=round(firing.t_end, 2),
                    frame_start=firing.frame_start,
                    frame_end=firing.frame_end,
                    rule=firing.rule,
                    points=pts,
                    score_after=round(seat.score, 1),
                    confidence=round(firing.confidence, 2),
                    severity=severity,
                    reason=firing.reason,
                )
                emitted_events.append(evt)

            # 3. Update peak score
            if seat.score > seat.peak_score:
                seat.peak_score = seat.score

            # 4. Update SUSTAINED_SECONDS (exact time spent above alert threshold during dt)
            if dt > 0:
                if prev_score >= self.alert_thresh and seat.score >= self.alert_thresh:
                    seat.sustained_seconds += dt
                elif prev_score >= self.alert_thresh and seat.score < self.alert_thresh:
                    # Decayed below threshold during this interval
                    if self.decay_rate > 0:
                        time_above = (prev_score - self.alert_thresh) / self.decay_rate
                        seat.sustained_seconds += min(dt, max(0.0, time_above))
                elif seat.score >= self.alert_thresh:
                    seat.sustained_seconds += dt * 0.5

            # 5. Update Seat Status
            if seat.score >= self.alert_thresh:
                seat.status = "alert"
            elif seat.score >= 40.0:
                seat.status = "accumulating"
            else:
                seat.status = "calm"

        return emitted_events

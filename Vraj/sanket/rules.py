"""Behavioral rule definitions for SANKET.

CRITICAL INVARIANTS:
1. The reason string is the product. Every rule outputs what was observed,
   the measured deviation, duration, and context.
2. Per-seat cooldowns prevent a single continuous movement from spamming firings.
3. Every rule is individually disableable via config.
4. Skip seats that are CALIBRATING or classified as STAFF.
5. Vocabulary rule: strictly alert / observed behaviour / review; never accuse or jump to conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

from sanket.config import ConfigDict
from sanket.features import SeatFeatures


@dataclass
class RuleFiring:
    """Represents a discrete rule trigger event."""
    rule: str
    points: float
    confidence: float
    reason: str
    t_start: float
    t_end: float
    seat_id: str
    track_id: Optional[int] = None
    frame_start: int = 0
    frame_end: int = 0


@dataclass
class SeatRuleState:
    """Maintains temporal condition tracking and cooldowns per seat."""
    seat_id: str
    last_fire_time: Dict[str, float] = field(default_factory=dict)
    active_condition_start: Dict[str, Optional[float]] = field(default_factory=dict)
    recent_firings: List[RuleFiring] = field(default_factory=list)


class BaseRule:
    """Abstract base class for invigilation behavioral rules."""
    name: str = "base_rule"

    def __init__(self, config: ConfigDict):
        self.config = config
        self.rule_cfg = config.get("rules", {}).get(self.name, {})
        self.enabled = bool(self.rule_cfg.get("enabled", True))
        self.cooldown_s = float(self.rule_cfg.get("cooldown_seconds", 5.0))
        self.points = float(config.get("scoring", {}).get("weights", {}).get(self.name, 10.0))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        raise NotImplementedError


class HeadTurnRule(BaseRule):
    """
    Fires when head turn deviation exceeds deviation_threshold (default 2.5 MAD)
    sustained for at least min_duration_seconds (default 1.0s).
    """
    name = "head_turn"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.dev_thresh = float(self.rule_cfg.get("deviation_threshold", 2.5))
        self.min_duration = float(self.rule_cfg.get("min_duration_seconds", 1.0))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled or not features.valid or features.head_turn_deviation is None:
            state.active_condition_start[self.name] = None
            return None

        # Check cooldown
        last_t = state.last_fire_time.get(self.name, -999.0)
        if (features.t - last_t) < self.cooldown_s:
            return None

        dev = features.head_turn_deviation
        if dev >= self.dev_thresh:
            start_t = state.active_condition_start.get(self.name)
            if start_t is None:
                state.active_condition_start[self.name] = features.t
                return None

            duration = features.t - start_t
            if duration >= self.min_duration:
                # Trigger firing
                direction = features.head_yaw_direction or "sideways"
                reason = f"Head turned {direction}, {dev:.1f} deviations from own baseline, held {duration:.1f}s"
                if baseline_unavailable:
                    reason += " (baseline unavailable, global threshold used)"

                state.last_fire_time[self.name] = features.t
                state.active_condition_start[self.name] = None

                return RuleFiring(
                    rule=self.name,
                    points=self.points,
                    confidence=float(np.clip(dev / 4.0, 0.6, 0.95)),
                    reason=reason,
                    t_start=start_t,
                    t_end=features.t,
                    seat_id=features.seat_id,
                    track_id=track_id,
                    frame_start=frame_index - int(duration * 25),
                    frame_end=frame_index,
                )
        else:
            state.active_condition_start[self.name] = None

        return None


class NeighbourReachRule(BaseRule):
    """
    Fires when candidate's wrist intrudes into adjacent seat space beyond min_depth.
    """
    name = "neighbour_reach"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.min_depth = float(self.rule_cfg.get("min_depth", 0.15))
        self.min_duration = float(self.rule_cfg.get("min_duration_seconds", 0.8))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled or not features.valid or not features.neighbour_intrusion:
            state.active_condition_start[self.name] = None
            return None

        last_t = state.last_fire_time.get(self.name, -999.0)
        if (features.t - last_t) < self.cooldown_s:
            return None

        # Find max intrusion among adjacent seats
        target_seat, max_depth = max(features.neighbour_intrusion.items(), key=lambda it: it[1])
        if max_depth >= self.min_depth:
            start_t = state.active_condition_start.get(self.name)
            if start_t is None:
                state.active_condition_start[self.name] = features.t
                return None

            duration = features.t - start_t
            if duration >= self.min_duration:
                reason = f"Wrist entered {target_seat}'s space, depth {int(max_depth * 100)}%, held {duration:.1f}s"
                state.last_fire_time[self.name] = features.t
                state.active_condition_start[self.name] = None

                return RuleFiring(
                    rule=self.name,
                    points=self.points,
                    confidence=float(np.clip(max_depth * 2.0, 0.7, 0.98)),
                    reason=reason,
                    t_start=start_t,
                    t_end=features.t,
                    seat_id=features.seat_id,
                    track_id=track_id,
                    frame_start=frame_index - int(duration * 25),
                    frame_end=frame_index,
                )
        else:
            state.active_condition_start[self.name] = None

        return None


class HiddenHandsRule(BaseRule):
    """
    Fires when both wrists are invisible for threshold_seconds (default 5.0s),
    re-firing every repeat_seconds (default 10.0s).
    """
    name = "hidden_hands"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.threshold_s = float(self.rule_cfg.get("threshold_seconds", 5.0))
        self.repeat_s = float(self.rule_cfg.get("repeat_seconds", 10.0))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled or not features.valid or features.hidden_hands_duration < self.threshold_s:
            return None

        dur = features.hidden_hands_duration
        last_t = state.last_fire_time.get(self.name, -999.0)

        # First trigger at threshold_s, then re-fires every repeat_s
        if (features.t - last_t) >= self.repeat_s or last_t < 0:
            reason = f"Both wrists not visible for {dur:.1f}s"
            state.last_fire_time[self.name] = features.t

            return RuleFiring(
                rule=self.name,
                points=self.points,
                confidence=0.75,
                reason=reason,
                t_start=features.t - dur,
                t_end=features.t,
                seat_id=features.seat_id,
                track_id=track_id,
                frame_start=frame_index - int(dur * 25),
                frame_end=frame_index,
            )

        return None


class TurningBackRule(BaseRule):
    """
    Fires when shoulder span foreshortens below span_ratio (0.55 of baseline)
    combined with torso rotation, sustained for min_duration_seconds.
    """
    name = "turning_back"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.span_ratio_thresh = float(self.rule_cfg.get("span_ratio", 0.55))
        self.torso_rot_thresh = float(self.rule_cfg.get("torso_rotation_threshold", 1.2))
        self.min_duration = float(self.rule_cfg.get("min_duration_seconds", 1.0))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled or not features.valid or features.shoulder_span_ratio is None:
            state.active_condition_start[self.name] = None
            return None

        last_t = state.last_fire_time.get(self.name, -999.0)
        if (features.t - last_t) < self.cooldown_s:
            return None

        span_r = features.shoulder_span_ratio
        torso_r = features.torso_rotation or 0.0

        if span_r <= self.span_ratio_thresh and torso_r >= self.torso_rot_thresh:
            start_t = state.active_condition_start.get(self.name)
            if start_t is None:
                state.active_condition_start[self.name] = features.t
                return None

            duration = features.t - start_t
            if duration >= self.min_duration:
                reason = f"Torso rotated away from desk, shoulder span {int(span_r * 100)}% of own baseline, held {duration:.1f}s"
                state.last_fire_time[self.name] = features.t
                state.active_condition_start[self.name] = None

                return RuleFiring(
                    rule=self.name,
                    points=self.points,
                    confidence=0.85,
                    reason=reason,
                    t_start=start_t,
                    t_end=features.t,
                    seat_id=features.seat_id,
                    track_id=track_id,
                    frame_start=frame_index - int(duration * 25),
                    frame_end=frame_index,
                )
        else:
            state.active_condition_start[self.name] = None

        return None


class RepeatedActionRule(BaseRule):
    """
    META-rule: Fires when N distinct rule firings occur for the same seat
    within window_seconds (directly implementing Hackathon Extension Goal).
    """
    name = "repeated_action"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.target_count = int(self.rule_cfg.get("count", 3))
        self.window_s = float(self.rule_cfg.get("window_seconds", 30.0))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled:
            return None

        last_t = state.last_fire_time.get(self.name, -999.0)
        if (features.t - last_t) < self.cooldown_s:
            return None

        # Filter firings within window_seconds (excluding meta-rule firings)
        recent = [
            f for f in state.recent_firings
            if (features.t - f.t_end) <= self.window_s and f.rule != self.name
        ]

        if len(recent) >= self.target_count:
            rule_summary = ", ".join(f.rule for f in recent[-self.target_count:])
            window_actual = features.t - recent[-self.target_count].t_start
            reason = f"{len(recent)} separate events in {int(window_actual)}s: {rule_summary}"

            state.last_fire_time[self.name] = features.t
            return RuleFiring(
                rule=self.name,
                points=self.points,
                confidence=0.90,
                reason=reason,
                t_start=recent[-self.target_count].t_start,
                t_end=features.t,
                seat_id=features.seat_id,
                track_id=track_id,
                frame_start=frame_index - int(window_actual * 25),
                frame_end=frame_index,
            )

        return None


class CandidateTalkingRule(BaseRule):
    """
    Fires when candidate is turned towards an adjacent candidate
    (mutual gaze, talking, or head turned directly toward neighbor)
    sustained for min_duration_seconds (default 0.8s).
    """
    name = "candidate_talking"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.min_duration = float(self.rule_cfg.get("min_duration_seconds", 0.8))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled or not features.valid or not features.talking_targets:
            state.active_condition_start[self.name] = None
            return None

        last_t = state.last_fire_time.get(self.name, -999.0)
        if (features.t - last_t) < self.cooldown_s:
            return None

        # Find max talking alignment
        target_sid, score = max(features.talking_targets.items(), key=lambda it: it[1])
        if score >= 0.5:
            start_t = state.active_condition_start.get(self.name)
            if start_t is None:
                state.active_condition_start[self.name] = features.t
                return None

            duration = features.t - start_t
            if duration >= self.min_duration:
                reason = f"Candidate turned towards {target_sid} (talking / mutual gaze observed for {duration:.1f}s)"
                state.last_fire_time[self.name] = features.t
                state.active_condition_start[self.name] = None

                return RuleFiring(
                    rule=self.name,
                    points=self.points,
                    confidence=float(np.clip(score, 0.75, 0.95)),
                    reason=reason,
                    t_start=start_t,
                    t_end=features.t,
                    seat_id=features.seat_id,
                    track_id=track_id,
                    frame_start=frame_index - int(duration * 25),
                    frame_end=frame_index,
                )
        else:
            state.active_condition_start[self.name] = None

        return None


class LapGazingRule(BaseRule):
    """
    Fires when the candidate's nose is significantly displaced from its resting position
    (e.g., dipping down) combined with hidden hands, suggesting lap-based unauthorized activity.
    """
    name = "lap_gazing"

    def __init__(self, config: ConfigDict):
        super().__init__(config)
        self.disp_thresh = float(self.rule_cfg.get("displacement_threshold", 0.35))
        self.min_duration = float(self.rule_cfg.get("min_duration_seconds", 3.0))

    def evaluate(
        self,
        features: SeatFeatures,
        state: SeatRuleState,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        baseline_unavailable: bool = False,
    ) -> Optional[RuleFiring]:
        if not self.enabled or not features.valid or features.nose_displacement is None:
            state.active_condition_start[self.name] = None
            return None

        last_t = state.last_fire_time.get(self.name, -999.0)
        if (features.t - last_t) < self.cooldown_s:
            return None

        # Check if nose is highly displaced and hands are hidden
        if features.nose_displacement >= self.disp_thresh and features.hidden_hands_duration > 0.0:
            start_t = state.active_condition_start.get(self.name)
            if start_t is None:
                state.active_condition_start[self.name] = features.t
                return None

            duration = features.t - start_t
            if duration >= self.min_duration:
                reason = f"Candidate exhibiting lap-gazing posture: head dipped down and hands hidden for {duration:.1f}s"
                state.last_fire_time[self.name] = features.t
                state.active_condition_start[self.name] = None

                return RuleFiring(
                    rule=self.name,
                    points=self.points,
                    confidence=0.85,
                    reason=reason,
                    t_start=start_t,
                    t_end=features.t,
                    seat_id=features.seat_id,
                    track_id=track_id,
                    frame_start=frame_index - int(duration * 25),
                    frame_end=frame_index,
                )
        else:
            state.active_condition_start[self.name] = None

        return None


class RuleEngine:
    """Evaluates all registered rules across monitored seats."""

    def __init__(self, config: ConfigDict):
        self.config = config
        self.rules: List[BaseRule] = [
            HeadTurnRule(config),
            NeighbourReachRule(config),
            HiddenHandsRule(config),
            TurningBackRule(config),
            CandidateTalkingRule(config),
            RepeatedActionRule(config),
            LapGazingRule(config),
        ]
        self.seat_states: Dict[str, SeatRuleState] = {}

    def evaluate_seat(
        self,
        features: SeatFeatures,
        track_id: Optional[int] = None,
        frame_index: int = 0,
        is_calibrating: bool = False,
        is_staff: bool = False,
        baseline_unavailable: bool = False,
    ) -> List[RuleFiring]:
        """
        Evaluates rules for a single seat.
        Skips seats that are CALIBRATING or classified as STAFF.
        """
        if is_calibrating or is_staff or not features.valid:
            return []

        sid = features.seat_id
        if sid not in self.seat_states:
            self.seat_states[sid] = SeatRuleState(seat_id=sid)

        state = self.seat_states[sid]
        firings: List[RuleFiring] = []

        # Evaluate base rules first
        for rule in self.rules:
            firing = rule.evaluate(
                features=features,
                state=state,
                track_id=track_id,
                frame_index=frame_index,
                baseline_unavailable=baseline_unavailable,
            )
            if firing:
                firings.append(firing)
                state.recent_firings.append(firing)

        # Trim old history from state
        state.recent_firings = [
            f for f in state.recent_firings
            if (features.t - f.t_end) <= 60.0
        ]

        return firings

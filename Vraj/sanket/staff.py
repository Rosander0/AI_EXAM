"""Staff Behavior Analysis & Supervision Quality Monitoring for SANKET.

CRITICAL INVARIANTS:
1. Staff are monitored for supervision quality, dwell patterns, and attention distribution.
2. Staff scores are strictly SEPARATED from candidate scores (never mixed or cross-penalized).
3. LANGUAGE INVARIANT: Never imply misconduct or wrongdoing. Neutral, professional vocabulary:
   - "unusual dwell pattern"
   - "attention distribution"
   - "observed proximity"
   - "supervision review"
4. Per-person baseline: Dwell deviation is benchmarked against that staff member's OWN
   median dwell duration across all seats visited during the session.
5. All durations and time intervals derive strictly from Frame.t.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from sanket.config import ConfigDict
from sanket.pose import Person
from sanket.scoring import Event
from sanket.seats import Seat, SeatMap


@dataclass
class StaffVisit:
    """Represents a discrete visit interval by a staff member to a candidate seat."""
    staff_id: str
    seat_id: str
    t_start: float
    t_end: float
    duration: float


@dataclass
class StaffEvent:
    """Represents a staff supervision analytics event."""
    event_id: str
    session_id: str
    staff_id: str
    seat_id: Optional[str]
    track_id: Optional[int]
    t_start: float
    t_end: float
    frame_start: int
    frame_end: int
    rule: str
    points: float
    score_after: float
    confidence: float
    severity: str  # "info" | "warning" | "critical"
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StaffMemberState:
    """Maintains trajectory, visit history, dwell statistics, and score for one staff member."""
    staff_id: str
    track_id: int
    first_seen_t: float
    last_seen_t: float
    current_seat_id: Optional[str] = None
    current_seat_enter_t: Optional[float] = None
    completed_visits: List[StaffVisit] = field(default_factory=list)
    dwell_per_seat: Dict[str, float] = field(default_factory=dict)
    visit_count_per_seat: Dict[str, int] = field(default_factory=dict)
    
    score: float = 0.0
    peak_score: float = 0.0
    event_count: int = 0
    distinct_rules: int = 0
    status: str = "normal"  # "normal" | "review_suggested" | "attention_elevated"
    last_reason: Optional[str] = None
    last_fire_times: Dict[str, float] = field(default_factory=dict)

    def get_median_dwell(self) -> float:
        """Computes median dwell across all completed visits, with a default prior of 15.0s."""
        durations = [v.duration for v in self.completed_visits if v.duration >= 3.0]
        if not durations:
            return 15.0
        return float(np.median(durations))

    def get_visited_seats(self) -> Set[str]:
        return set(self.visit_count_per_seat.keys())


class StaffMonitor:
    """Engine for tracking staff proximity, dwell baselines, repeat visits, and coverage."""

    def __init__(self, config: ConfigDict, session_id: str = "sess_default"):
        self.config = config
        self.session_id = session_id

        staff_cfg = config.get("staff_monitoring", {})
        self.enabled = bool(staff_cfg.get("enabled", True))
        self.proximity_ratio = float(staff_cfg.get("proximity_distance_ratio", 1.8))
        self.alert_thresh = float(staff_cfg.get("alert_threshold", 100.0))
        self.decay_rate = float(staff_cfg.get("decay_rate", 0.5))
        self.weights: Dict[str, float] = staff_cfg.get("weights", {
            "staff_dwell": 40.0,
            "staff_repeat_visit": 35.0,
            "staff_proximity_during_student_event": 50.0,
        })
        
        rules_cfg = staff_cfg.get("rules", {})
        self.dwell_cfg = rules_cfg.get("staff_dwell", {})
        self.dwell_factor_thresh = float(self.dwell_cfg.get("dwell_factor_threshold", 3.0))
        self.dwell_min_dur = float(self.dwell_cfg.get("min_duration_seconds", 30.0))
        self.dwell_cooldown = float(self.dwell_cfg.get("cooldown_seconds", 60.0))

        self.repeat_cfg = rules_cfg.get("staff_repeat_visit", {})
        self.repeat_count_thresh = int(self.repeat_cfg.get("count", 4))
        self.repeat_window_s = float(self.repeat_cfg.get("window_seconds", 720.0))
        self.repeat_cooldown = float(self.repeat_cfg.get("cooldown_seconds", 120.0))

        self.prox_cfg = rules_cfg.get("staff_proximity_during_student_event", {})
        self.prox_cooldown = float(self.prox_cfg.get("cooldown_seconds", 30.0))

        self.staff_members: Dict[str, StaffMemberState] = {}
        self.emitted_events: List[StaffEvent] = []
        self.event_counter: int = 0
        self.last_t: Optional[float] = None

    def update(
        self,
        staff_persons: List[Person],
        seat_map: SeatMap,
        student_events: List[Event],
        t: float,
        frame_index: int,
    ) -> List[StaffEvent]:
        """
        Updates staff tracking, evaluates dwell & repeat visits, correlates proximity with student events.
        """
        if not self.enabled:
            return []

        dt = max(0.0, t - self.last_t) if self.last_t is not None else 0.0
        self.last_t = t

        new_events: List[StaffEvent] = []

        # 1. Update Staff Lifecycle & Proximity
        active_staff_ids: Set[str] = set()

        for p in staff_persons:
            if p.track_id is None:
                continue

            staff_id = f"STAFF_{p.track_id:02d}"
            active_staff_ids.add(staff_id)

            if staff_id not in self.staff_members:
                self.staff_members[staff_id] = StaffMemberState(
                    staff_id=staff_id,
                    track_id=p.track_id,
                    first_seen_t=t,
                    last_seen_t=t,
                )

            staff_state = self.staff_members[staff_id]
            staff_state.last_seen_t = t

            # Apply score decay
            if dt > 0 and staff_state.score > 0:
                staff_state.score = max(0.0, staff_state.score - self.decay_rate * dt)

            # Determine nearest seat within proximity ratio
            nearest_seat_id = self._find_nearest_seat(p, seat_map.seats)

            if nearest_seat_id != staff_state.current_seat_id:
                # Close previous visit if any
                if staff_state.current_seat_id is not None and staff_state.current_seat_enter_t is not None:
                    visit_dur = t - staff_state.current_seat_enter_t
                    if visit_dur >= 2.0:
                        prev_sid = staff_state.current_seat_id
                        visit = StaffVisit(
                            staff_id=staff_id,
                            seat_id=prev_sid,
                            t_start=staff_state.current_seat_enter_t,
                            t_end=t,
                            duration=round(visit_dur, 1),
                        )
                        staff_state.completed_visits.append(visit)
                        staff_state.dwell_per_seat[prev_sid] = staff_state.dwell_per_seat.get(prev_sid, 0.0) + visit_dur
                        staff_state.visit_count_per_seat[prev_sid] = staff_state.visit_count_per_seat.get(prev_sid, 0) + 1

                # Start new visit
                staff_state.current_seat_id = nearest_seat_id
                staff_state.current_seat_enter_t = t if nearest_seat_id is not None else None

            # 2. Evaluate Rule: Staff Dwell (benchmark against staff member's own median dwell)
            if staff_state.current_seat_id is not None and staff_state.current_seat_enter_t is not None:
                current_dwell = t - staff_state.current_seat_enter_t
                median_dwell = staff_state.get_median_dwell()
                target_sid = staff_state.current_seat_id

                if current_dwell >= self.dwell_min_dur:
                    factor = current_dwell / max(5.0, median_dwell)
                    if factor >= self.dwell_factor_thresh:
                        last_fire = staff_state.last_fire_times.get(f"dwell_{target_sid}", -999.0)
                        if (t - last_fire) >= self.dwell_cooldown:
                            pts = self.weights.get("staff_dwell", 40.0)
                            staff_state.score += pts
                            staff_state.last_fire_times[f"dwell_{target_sid}"] = t
                            reason = (
                                f"Staff dwelled at {target_sid} for {int(current_dwell)}s, "
                                f"{factor:.1f}x their median dwell of {int(median_dwell)}s "
                                f"across {len(staff_state.visit_count_per_seat)} seats (unusual dwell pattern observed for human review)"
                            )
                            evt = self._emit_event(
                                staff_state=staff_state,
                                rule="staff_dwell",
                                seat_id=target_sid,
                                points=pts,
                                t_start=staff_state.current_seat_enter_t,
                                t_end=t,
                                frame_index=frame_index,
                                reason=reason,
                            )
                            new_events.append(evt)

            # 3. Evaluate Rule: Staff Repeat Visit
            if staff_state.current_seat_id is not None:
                target_sid = staff_state.current_seat_id
                recent_visits = [
                    v for v in staff_state.completed_visits
                    if v.seat_id == target_sid and (t - v.t_end) <= self.repeat_window_s
                ]
                # Include ongoing visit
                total_recent = len(recent_visits) + 1
                if total_recent >= self.repeat_count_thresh:
                    # Check other seats in window
                    other_seat_visits = [
                        v for v in staff_state.completed_visits
                        if v.seat_id != target_sid and (t - v.t_end) <= self.repeat_window_s
                    ]
                    avg_other = len(other_seat_visits) / max(1, len(seat_map.seats) - 1)
                    if avg_other <= 1.5:
                        last_fire = staff_state.last_fire_times.get(f"repeat_{target_sid}", -999.0)
                        if (t - last_fire) >= self.repeat_cooldown:
                            pts = self.weights.get("staff_repeat_visit", 35.0)
                            staff_state.score += pts
                            staff_state.last_fire_times[f"repeat_{target_sid}"] = t
                            window_m = self.repeat_window_s / 60.0
                            reason = (
                                f"Staff returned to {target_sid} {total_recent} times in {int(window_m)} minutes; "
                                f"other seats visited {avg_other:.1f}x on average (attention distribution observation)"
                            )
                            evt = self._emit_event(
                                staff_state=staff_state,
                                rule="staff_repeat_visit",
                                seat_id=target_sid,
                                points=pts,
                                t_start=recent_visits[0].t_start if recent_visits else t,
                                t_end=t,
                                frame_index=frame_index,
                                reason=reason,
                            )
                            new_events.append(evt)

            # 4. Evaluate Rule: Staff Proximity During Student Event
            if student_events and staff_state.current_seat_id is not None:
                for se in student_events:
                    if se.seat_id == staff_state.current_seat_id and se.severity in ("warning", "critical"):
                        last_fire = staff_state.last_fire_times.get(f"prox_{se.seat_id}", -999.0)
                        if (t - last_fire) >= self.prox_cooldown:
                            pts = self.weights.get("staff_proximity_during_student_event", 50.0)
                            staff_state.score += pts
                            staff_state.last_fire_times[f"prox_{se.seat_id}"] = t
                            mins = int(t // 60)
                            secs = int(t % 60)
                            reason = (
                                f"Staff present within proximity of {se.seat_id} during scored candidate event "
                                f"at {mins:02d}:{secs:02d} (observed proximity correlation for supervision review)"
                            )
                            evt = self._emit_event(
                                staff_state=staff_state,
                                rule="staff_proximity_during_student_event",
                                seat_id=se.seat_id,
                                points=pts,
                                t_start=se.t_start,
                                t_end=t,
                                frame_index=frame_index,
                                reason=reason,
                            )
                            new_events.append(evt)

            # Update peak score and status
            if staff_state.score > staff_state.peak_score:
                staff_state.peak_score = staff_state.score

            if staff_state.score >= self.alert_thresh:
                staff_state.status = "attention_elevated"
            elif staff_state.score >= 40.0:
                staff_state.status = "review_suggested"
            else:
                staff_state.status = "normal"

        self.emitted_events.extend(new_events)
        return new_events

    def _find_nearest_seat(self, person: Person, seats: Dict[str, Seat]) -> Optional[str]:
        """Finds closest seat anchor to the staff member within proximity threshold."""
        if not seats:
            return None

        pcx, pcy = person.bbox_center()
        pw = max(1.0, person.bbox[2] - person.bbox[0])

        best_sid = None
        min_dist = float("inf")

        for sid, seat in seats.items():
            scx = (seat.anchor_box[0] + seat.anchor_box[2]) / 2.0
            scy = (seat.anchor_box[1] + seat.anchor_box[3]) / 2.0
            dist = math.hypot(pcx - scx, pcy - scy)

            # Max proximity radius: 1.8x person width + seat width
            sw = max(1.0, seat.anchor_box[2] - seat.anchor_box[0])
            max_r = (pw + sw) * self.proximity_ratio * 0.65

            if dist <= max_r and dist < min_dist:
                min_dist = dist
                best_sid = sid

        return best_sid

    def _emit_event(
        self,
        staff_state: StaffMemberState,
        rule: str,
        seat_id: Optional[str],
        points: float,
        t_start: float,
        t_end: float,
        frame_index: int,
        reason: str,
    ) -> StaffEvent:
        """Constructs a new StaffEvent record."""
        self.event_counter += 1
        staff_state.event_count += 1
        staff_state.last_reason = reason

        severity = "critical" if staff_state.score >= self.alert_thresh else "warning"

        return StaffEvent(
            event_id=f"staff_evt_{self.event_counter:04d}",
            session_id=self.session_id,
            staff_id=staff_state.staff_id,
            seat_id=seat_id,
            track_id=staff_state.track_id,
            t_start=round(t_start, 2),
            t_end=round(t_end, 2),
            frame_start=max(0, frame_index - int((t_end - t_start) * 25)),
            frame_end=frame_index,
            rule=rule,
            points=points,
            score_after=round(staff_state.score, 1),
            confidence=0.88,
            severity=severity,
            reason=reason,
        )

    def generate_coverage_audit(self, seat_map: SeatMap) -> Dict[str, Any]:
        """Audits overall hall coverage and attention distribution across all seats."""
        all_seats = set(seat_map.seats.keys())
        all_visited: Set[str] = set()
        
        staff_coverage_details = {}
        for staff_id, st in self.staff_members.items():
            visited = st.get_visited_seats()
            all_visited.update(visited)
            unvisited_for_staff = list(all_seats - visited)
            staff_coverage_details[staff_id] = {
                "staff_id": staff_id,
                "track_id": st.track_id,
                "score": round(st.score, 1),
                "peak_score": round(st.peak_score, 1),
                "status": st.status,
                "median_dwell_s": round(st.get_median_dwell(), 1),
                "visited_seats": list(visited),
                "unvisited_seats": unvisited_for_staff,
                "dwell_per_seat": {k: round(v, 1) for k, v in st.dwell_per_seat.items()},
                "visits_per_seat": st.visit_count_per_seat,
                "total_visits": sum(st.visit_count_per_seat.values()),
                "total_dwell_s": round(sum(st.dwell_per_seat.values()), 1),
            }

        unvisited_hall_seats = list(all_seats - all_visited)

        return {
            "total_hall_seats": len(all_seats),
            "hall_seats_visited": list(all_visited),
            "hall_seats_never_approached": unvisited_hall_seats,
            "coverage_percentage": round((len(all_visited) / len(all_seats) * 100.0) if all_seats else 100.0, 1),
            "staff_count": len(self.staff_members),
            "staff_profiles": staff_coverage_details,
            "staff_events_count": len(self.emitted_events),
        }

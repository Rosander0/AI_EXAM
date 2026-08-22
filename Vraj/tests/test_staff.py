"""Unit and integration tests for Staff Behavior Analysis & Supervision Quality Monitoring."""

import unittest
import numpy as np
from sanket.config import load_config
from sanket.pose import Person
from sanket.scoring import Event
from sanket.seats import Seat, SeatMap
from sanket.staff import StaffMonitor, StaffMemberState, StaffVisit, StaffEvent


def make_person(track_id=1, bbox=(130, 80, 170, 220), t=0.0, frame_index=0) -> Person:
    return Person(
        track_id=track_id,
        bbox=bbox,
        bbox_conf=0.9,
        keypoints=np.zeros((17, 3)),
        frame_index=frame_index,
        t=t,
    )


class TestStaffMonitoring(unittest.TestCase):

    def _create_dummy_seat_map(self) -> SeatMap:
        cfg = load_config("config.yaml")
        sm = SeatMap(cfg)
        sm.seats = {
            "S01": Seat(seat_id="S01", anchor_box=[100, 100, 200, 200], grid_row=0, grid_col=0, occupied=True),
            "S02": Seat(seat_id="S02", anchor_box=[300, 100, 400, 200], grid_row=0, grid_col=1, occupied=True),
            "S03": Seat(seat_id="S03", anchor_box=[500, 100, 600, 200], grid_row=0, grid_col=2, occupied=True),
        }
        return sm

    def test_staff_monitor_initialization(self):
        cfg = load_config("config.yaml")
        monitor = StaffMonitor(cfg, session_id="test_sess")
        self.assertTrue(monitor.enabled)
        self.assertEqual(monitor.alert_thresh, 100.0)

    def test_staff_dwell_rule(self):
        cfg = load_config("config.yaml")
        cfg["staff_monitoring"]["rules"]["staff_dwell"]["min_duration_seconds"] = 10.0
        cfg["staff_monitoring"]["rules"]["staff_dwell"]["dwell_factor_threshold"] = 2.0
        
        monitor = StaffMonitor(cfg, session_id="test_sess")
        sm = self._create_dummy_seat_map()

        staff_state = StaffMemberState(
            staff_id="STAFF_01",
            track_id=1,
            first_seen_t=0.0,
            last_seen_t=0.0,
            completed_visits=[
                StaffVisit("STAFF_01", "S02", 0.0, 10.0, 10.0),
                StaffVisit("STAFF_01", "S03", 15.0, 25.0, 10.0),
            ],
            visit_count_per_seat={"S02": 1, "S03": 1},
            dwell_per_seat={"S02": 10.0, "S03": 10.0},
        )
        monitor.staff_members["STAFF_01"] = staff_state

        p = make_person(track_id=1, bbox=(130, 80, 170, 220), t=30.0, frame_index=100)
        events = monitor.update([p], sm, [], t=30.0, frame_index=100)
        self.assertEqual(len(events), 0)

        p2 = make_person(track_id=1, bbox=(130, 80, 170, 220), t=65.0, frame_index=800)
        events = monitor.update([p2], sm, [], t=65.0, frame_index=800)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].rule, "staff_dwell")
        self.assertEqual(events[0].staff_id, "STAFF_01")
        self.assertIn("S01", events[0].reason)
        self.assertIn("unusual dwell pattern", events[0].reason)
        self.assertGreaterEqual(staff_state.score, 40.0)

    def test_staff_repeat_visit_rule(self):
        cfg = load_config("config.yaml")
        cfg["staff_monitoring"]["rules"]["staff_repeat_visit"]["count"] = 3
        cfg["staff_monitoring"]["rules"]["staff_repeat_visit"]["window_seconds"] = 300.0

        monitor = StaffMonitor(cfg, session_id="test_sess")
        sm = self._create_dummy_seat_map()

        staff_state = StaffMemberState(
            staff_id="STAFF_01",
            track_id=1,
            first_seen_t=0.0,
            last_seen_t=0.0,
            completed_visits=[
                StaffVisit("STAFF_01", "S01", 10.0, 20.0, 10.0),
                StaffVisit("STAFF_01", "S01", 40.0, 50.0, 10.0),
                StaffVisit("STAFF_01", "S02", 70.0, 80.0, 10.0),
            ],
            visit_count_per_seat={"S01": 2, "S02": 1},
            dwell_per_seat={"S01": 20.0, "S02": 10.0},
        )
        monitor.staff_members["STAFF_01"] = staff_state

        p = make_person(track_id=1, bbox=(130, 80, 170, 220), t=100.0, frame_index=1000)
        events = monitor.update([p], sm, [], t=100.0, frame_index=1000)
        
        self.assertTrue(any(e.rule == "staff_repeat_visit" for e in events))
        repeat_evt = next(e for e in events if e.rule == "staff_repeat_visit")
        self.assertIn("attention distribution observation", repeat_evt.reason)

    def test_staff_proximity_during_student_event(self):
        cfg = load_config("config.yaml")
        monitor = StaffMonitor(cfg, session_id="test_sess")
        sm = self._create_dummy_seat_map()

        p = make_person(track_id=1, bbox=(130, 80, 170, 220), t=10.0, frame_index=100)
        monitor.update([p], sm, [], t=10.0, frame_index=100)

        student_evt = Event(
            event_id="evt_0001",
            session_id="test_sess",
            seat_id="S01",
            track_id=2,
            t_start=14.0,
            t_end=15.0,
            frame_start=350,
            frame_end=375,
            rule="object_phone",
            points=100.0,
            score_after=100.0,
            confidence=0.95,
            severity="critical",
            reason="Prohibited phone device observed",
        )

        p2 = make_person(track_id=1, bbox=(130, 80, 170, 220), t=15.0, frame_index=375)
        events = monitor.update([p2], sm, [student_evt], t=15.0, frame_index=375)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].rule, "staff_proximity_during_student_event")
        self.assertIn("observed proximity correlation for supervision review", events[0].reason)

    def test_staff_coverage_audit(self):
        cfg = load_config("config.yaml")
        monitor = StaffMonitor(cfg, session_id="test_sess")
        sm = self._create_dummy_seat_map()

        staff_state = StaffMemberState(
            staff_id="STAFF_01",
            track_id=1,
            first_seen_t=0.0,
            last_seen_t=100.0,
            completed_visits=[
                StaffVisit("STAFF_01", "S01", 10.0, 30.0, 20.0),
                StaffVisit("STAFF_01", "S02", 40.0, 70.0, 30.0),
            ],
            visit_count_per_seat={"S01": 1, "S02": 1},
            dwell_per_seat={"S01": 20.0, "S02": 30.0},
        )
        monitor.staff_members["STAFF_01"] = staff_state

        audit = monitor.generate_coverage_audit(sm)
        self.assertEqual(audit["total_hall_seats"], 3)
        self.assertIn("S01", audit["hall_seats_visited"])
        self.assertIn("S02", audit["hall_seats_visited"])
        self.assertIn("S03", audit["hall_seats_never_approached"])
        self.assertEqual(audit["coverage_percentage"], 66.7)

    def test_language_invariants(self):
        cfg = load_config("config.yaml")
        monitor = StaffMonitor(cfg, session_id="test_sess")
        sm = self._create_dummy_seat_map()

        forbidden_words = ["cheat", "cheating", "culprit", "misconduct", "guilty", "suspect", "offender", "fraud"]

        staff_state = StaffMemberState(
            staff_id="STAFF_01", track_id=1, first_seen_t=0.0, last_seen_t=0.0,
            completed_visits=[StaffVisit("STAFF_01", "S02", 0.0, 10.0, 10.0)] * 5,
            visit_count_per_seat={"S02": 5}, dwell_per_seat={"S02": 50.0},
        )
        monitor.staff_members["STAFF_01"] = staff_state

        p = make_person(track_id=1, bbox=(130, 80, 170, 220), t=10.0, frame_index=100)
        monitor.update([p], sm, [], t=10.0, frame_index=100)
        
        student_evt = Event(
            event_id="evt_01", session_id="sess", seat_id="S01", track_id=2,
            t_start=50.0, t_end=55.0, frame_start=1200, frame_end=1300,
            rule="head_turn", points=10.0, score_after=20.0, confidence=0.8,
            severity="warning", reason="Head turned",
        )
        p2 = make_person(track_id=1, bbox=(130, 80, 170, 220), t=55.0, frame_index=1300)
        events = monitor.update([p2], sm, [student_evt], t=55.0, frame_index=1300)

        for ev in events:
            reason_lower = ev.reason.lower()
            for fw in forbidden_words:
                self.assertNotIn(fw, reason_lower, f"Forbidden word '{fw}' found in staff event reason: {ev.reason}")


if __name__ == "__main__":
    unittest.main()

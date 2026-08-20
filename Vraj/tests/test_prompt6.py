"""Unit tests for SANKET Prompt 6 (Rule Engine & Suspicion Scoring)."""

import pytest
from sanket.config import load_config
from sanket.features import SeatFeatures
from sanket.rules import HeadTurnRule, NeighbourReachRule, RepeatedActionRule, RuleEngine, SeatRuleState
from sanket.scoring import Event, ScoringEngine
from sanket.seats import Seat


def test_head_turn_rule_and_cooldown():
    """Verify that head turn requires duration threshold and respects cooldown."""
    cfg = load_config("config.yaml")
    rule = HeadTurnRule(cfg)
    state = SeatRuleState(seat_id="S01")

    # t = 0.0s: deviation 3.0 exceeds 2.5 threshold, but duration is 0s -> should NOT fire
    f1 = SeatFeatures(seat_id="S01", t=0.0, head_turn_deviation=3.0, head_yaw_direction="left", valid=True)
    firing1 = rule.evaluate(f1, state)
    assert firing1 is None

    # t = 1.2s: deviation 3.0 sustained for 1.2s (> 1.0s) -> MUST fire
    f2 = SeatFeatures(seat_id="S01", t=1.2, head_turn_deviation=3.0, head_yaw_direction="left", valid=True)
    firing2 = rule.evaluate(f2, state)
    assert firing2 is not None
    assert firing2.rule == "head_turn"
    assert "Head turned left" in firing2.reason

    # t = 2.0s: deviation still 3.0, but inside 5.0s cooldown -> should NOT re-fire
    f3 = SeatFeatures(seat_id="S01", t=2.0, head_turn_deviation=3.0, head_yaw_direction="left", valid=True)
    firing3 = rule.evaluate(f3, state)
    assert firing3 is None


def test_repeated_action_meta_rule():
    """Verify repeated_action meta-rule fires when count >= 3 events occur within window."""
    cfg = load_config("config.yaml")
    meta_rule = RepeatedActionRule(cfg)
    state = SeatRuleState(seat_id="S01")

    # Simulate 3 previous head turn firings inside 15 seconds
    f_dummy = SeatFeatures(seat_id="S01", t=15.0, valid=True)
    from sanket.rules import RuleFiring
    state.recent_firings = [
        RuleFiring("head_turn", 10.0, 0.8, "Turn 1", 1.0, 2.0, "S01"),
        RuleFiring("head_turn", 10.0, 0.8, "Turn 2", 5.0, 6.0, "S01"),
        RuleFiring("neighbour_reach", 30.0, 0.8, "Reach 1", 10.0, 11.0, "S01"),
    ]

    firing = meta_rule.evaluate(f_dummy, state)
    assert firing is not None
    assert firing.rule == "repeated_action"
    assert "3 separate events" in firing.reason


def test_scoring_continuous_decay_and_sustained_seconds():
    """Verify S = max(0, S - D * dt) + sum(w_i * E_i) and sustained time accumulation."""
    cfg = load_config("config.yaml")
    cfg.scoring["decay_rate"] = 2.0  # 2.0 points per second
    cfg.scoring["alert_threshold"] = 50.0  # Lower threshold for test
    cfg.scoring["weights"] = {"turning_back": 60.0}

    scoring = ScoringEngine(cfg, session_id="sess_test")
    seats = {
        "S01": Seat("S01", 1, 1, (10, 10, 50, 50), score=0.0)
    }

    # Step 1 at t=0.0s: add 60 points (turns back)
    from sanket.rules import RuleFiring
    firing = RuleFiring("turning_back", 60.0, 0.85, "Turned back", 0.0, 0.0, "S01")
    events1 = scoring.update(seats, {"S01": [firing]}, t=0.0)

    assert len(events1) == 1
    assert seats["S01"].score == pytest.approx(60.0)
    assert seats["S01"].status == "alert"

    # Step 2 at t=5.0s: 5 seconds elapse with NO new firings
    # Score must decay by D * dt = 2.0 * 5.0 = 10.0 points -> New score = 50.0
    events2 = scoring.update(seats, {}, t=5.0)
    assert seats["S01"].score == pytest.approx(50.0)
    # Sustained seconds should have accumulated 5.0s while above 50
    assert seats["S01"].sustained_seconds == pytest.approx(5.0)


def test_candidate_talking_rule():
    """Verify that candidate_talking rule fires when sustained orientation towards neighbor occurs."""
    cfg = load_config("config.yaml")
    from sanket.rules import CandidateTalkingRule
    rule = CandidateTalkingRule(cfg)
    state = SeatRuleState(seat_id="S01")

    # t = 0.0s: candidate S01 turned towards S02, duration 0s -> should NOT fire
    f1 = SeatFeatures(seat_id="S01", t=0.0, talking_targets={"S02": 0.85}, valid=True)
    assert rule.evaluate(f1, state) is None

    # t = 1.0s: candidate S01 turned towards S02 for 1.0s (> 0.8s) -> MUST fire
    f2 = SeatFeatures(seat_id="S01", t=1.0, talking_targets={"S02": 0.85}, valid=True)
    firing = rule.evaluate(f2, state)
    assert firing is not None
    assert firing.rule == "candidate_talking"
    assert "turned towards S02" in firing.reason
    assert firing.points == 40.0

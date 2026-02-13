"""Tests for Phase 6 — Team & Scale Org features.

Covers: role hierarchy, permissions, caseload capacity, org summary,
rebalance suggestions, tier limits.
"""

from __future__ import annotations

from core.services.team import (
    ROLE_HIERARCHY,
    TIER_LIMITS,
    CoachCapacity,
    can_assign_athlete,
    check_tier_limit,
    compute_coach_capacity,
    compute_org_summary,
    has_permission,
    suggest_rebalance,
)


# ── Role Hierarchy tests ─────────────────────────────────────────────────

class TestRoleHierarchy:
    def test_hierarchy_order(self):
        assert ROLE_HIERARCHY["assistant"] < ROLE_HIERARCHY["coach"]
        assert ROLE_HIERARCHY["coach"] < ROLE_HIERARCHY["head_coach"]
        assert ROLE_HIERARCHY["head_coach"] < ROLE_HIERARCHY["owner"]

    def test_owner_can_manage_all(self):
        assert has_permission("owner", "head_coach")
        assert has_permission("owner", "coach")
        assert has_permission("owner", "assistant")

    def test_head_coach_can_manage_below(self):
        assert has_permission("head_coach", "coach")
        assert has_permission("head_coach", "assistant")

    def test_coach_can_manage_assistant(self):
        assert has_permission("coach", "assistant")

    def test_cannot_manage_same_level(self):
        assert not has_permission("coach", "coach")

    def test_cannot_manage_above(self):
        assert not has_permission("assistant", "coach")
        assert not has_permission("coach", "head_coach")

    def test_unknown_role(self):
        assert not has_permission("unknown", "coach")


class TestCanAssignAthlete:
    def test_head_coach_can_assign(self):
        assert can_assign_athlete("head_coach")

    def test_owner_can_assign(self):
        assert can_assign_athlete("owner")

    def test_coach_cannot_assign(self):
        assert not can_assign_athlete("coach")

    def test_assistant_cannot_assign(self):
        assert not can_assign_athlete("assistant")


# ── Coach Capacity tests ─────────────────────────────────────────────────

class TestCoachCapacity:
    def test_basic_capacity(self):
        cc = compute_coach_capacity(1, "Alice", "coach", 10, 20)
        assert cc.utilization_pct == 50.0
        assert cc.available_slots == 10

    def test_full_capacity(self):
        cc = compute_coach_capacity(2, "Bob", "coach", 20, 20)
        assert cc.utilization_pct == 100.0
        assert cc.available_slots == 0

    def test_over_capacity(self):
        cc = compute_coach_capacity(3, "Charlie", "coach", 25, 20)
        assert cc.utilization_pct == 125.0
        assert cc.available_slots == 0

    def test_empty_caseload(self):
        cc = compute_coach_capacity(4, "Diana", "coach", 0, 20)
        assert cc.utilization_pct == 0.0
        assert cc.available_slots == 20

    def test_zero_cap(self):
        cc = compute_coach_capacity(5, "Eve", "assistant", 0, 0)
        assert cc.utilization_pct == 0
        assert cc.available_slots == 0


# ── Org Summary tests ────────────────────────────────────────────────────

class TestOrgSummary:
    def test_basic_summary(self):
        capacities = [
            compute_coach_capacity(1, "A", "coach", 10, 20),
            compute_coach_capacity(2, "B", "coach", 15, 20),
        ]
        summary = compute_org_summary(1, "TestOrg", "pro", 5, 100, capacities, 25)
        assert summary.total_coaches == 2
        assert summary.total_athletes == 25
        assert summary.avg_utilization_pct == 62.5  # (50+75)/2

    def test_empty_org(self):
        summary = compute_org_summary(1, "Empty", "free", 1, 20, [], 0)
        assert summary.total_coaches == 0
        assert summary.avg_utilization_pct == 0.0


# ── Rebalance Suggestions tests ──────────────────────────────────────────

class TestRebalanceSuggestions:
    def test_suggests_transfer(self):
        capacities = [
            CoachCapacity(1, "Overloaded", "coach", 19, 20, 95.0, 1),
            CoachCapacity(2, "Available", "coach", 5, 20, 25.0, 15),
        ]
        suggestions = suggest_rebalance(capacities)
        assert len(suggestions) == 1
        assert suggestions[0]["from_coach"] == "Overloaded"
        assert suggestions[0]["to_coach"] == "Available"

    def test_no_suggestion_when_balanced(self):
        capacities = [
            CoachCapacity(1, "A", "coach", 10, 20, 50.0, 10),
            CoachCapacity(2, "B", "coach", 12, 20, 60.0, 8),
        ]
        suggestions = suggest_rebalance(capacities)
        assert len(suggestions) == 0

    def test_no_suggestion_when_none_available(self):
        capacities = [
            CoachCapacity(1, "A", "coach", 20, 20, 100.0, 0),
            CoachCapacity(2, "B", "coach", 20, 20, 100.0, 0),
        ]
        suggestions = suggest_rebalance(capacities)
        assert len(suggestions) == 0

    def test_empty_list(self):
        assert suggest_rebalance([]) == []


# ── Tier Limit tests ─────────────────────────────────────────────────────

class TestTierLimits:
    def test_free_tier(self):
        assert TIER_LIMITS["free"]["max_coaches"] == 1
        assert TIER_LIMITS["free"]["max_athletes"] == 20

    def test_pro_tier(self):
        assert TIER_LIMITS["pro"]["max_coaches"] == 5

    def test_enterprise_tier(self):
        assert TIER_LIMITS["enterprise"]["max_coaches"] == 50

    def test_within_limit(self):
        assert check_tier_limit("free", 0, "max_coaches")

    def test_at_limit(self):
        assert not check_tier_limit("free", 1, "max_coaches")

    def test_over_limit(self):
        assert not check_tier_limit("free", 5, "max_coaches")

    def test_unknown_tier_uses_free(self):
        assert not check_tier_limit("unknown", 1, "max_coaches")

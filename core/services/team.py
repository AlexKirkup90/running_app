"""Team & Organization management service.

Handles multi-coach organizations, role hierarchies, caseload management,
athlete assignment, and capacity planning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Role hierarchy: higher index = more permissions
ROLE_HIERARCHY: dict[str, int] = {
    "assistant": 0,
    "coach": 1,
    "head_coach": 2,
    "owner": 3,
}


@dataclass
class CoachCapacity:
    """Snapshot of a coach's caseload vs capacity."""

    coach_user_id: int
    coach_name: str
    org_role: str
    assigned_athletes: int
    caseload_cap: int
    utilization_pct: float
    available_slots: int


@dataclass
class OrgSummary:
    """High-level organization stats."""

    org_id: int
    org_name: str
    tier: str
    total_coaches: int
    total_athletes: int
    max_coaches: int
    max_athletes: int
    avg_utilization_pct: float


def has_permission(actor_role: str, target_role: str) -> bool:
    """Check if actor_role can manage target_role.

    A user can manage users at a strictly lower hierarchy level.
    """
    actor_level = ROLE_HIERARCHY.get(actor_role, -1)
    target_level = ROLE_HIERARCHY.get(target_role, -1)
    return actor_level > target_level


def can_assign_athlete(actor_role: str) -> bool:
    """Check if a role is allowed to assign athletes to coaches."""
    return ROLE_HIERARCHY.get(actor_role, -1) >= ROLE_HIERARCHY["head_coach"]


def compute_coach_capacity(
    coach_user_id: int,
    coach_name: str,
    org_role: str,
    assigned_count: int,
    caseload_cap: int,
) -> CoachCapacity:
    """Compute a coach's current capacity utilization."""
    util_pct = (assigned_count / caseload_cap * 100) if caseload_cap > 0 else 0
    available = max(0, caseload_cap - assigned_count)
    return CoachCapacity(
        coach_user_id=coach_user_id,
        coach_name=coach_name,
        org_role=org_role,
        assigned_athletes=assigned_count,
        caseload_cap=caseload_cap,
        utilization_pct=round(util_pct, 1),
        available_slots=available,
    )


def compute_org_summary(
    org_id: int,
    org_name: str,
    tier: str,
    max_coaches: int,
    max_athletes: int,
    coach_capacities: list[CoachCapacity],
    total_athletes: int,
) -> OrgSummary:
    """Compute organization-level summary statistics."""
    avg_util = 0.0
    if coach_capacities:
        avg_util = sum(c.utilization_pct for c in coach_capacities) / len(coach_capacities)
    return OrgSummary(
        org_id=org_id,
        org_name=org_name,
        tier=tier,
        total_coaches=len(coach_capacities),
        total_athletes=total_athletes,
        max_coaches=max_coaches,
        max_athletes=max_athletes,
        avg_utilization_pct=round(avg_util, 1),
    )


def suggest_rebalance(
    capacities: list[CoachCapacity],
) -> list[dict[str, Any]]:
    """Suggest athlete transfers to balance caseloads.

    Identifies overloaded coaches (>90% utilization) and suggests
    transferring athletes to coaches with available capacity.

    Returns list of {"from_coach", "to_coach", "reason"} suggestions.
    """
    overloaded = [c for c in capacities if c.utilization_pct > 90 and c.assigned_athletes > 0]
    underloaded = [c for c in capacities if c.available_slots > 0]

    if not overloaded or not underloaded:
        return []

    suggestions = []
    underloaded_sorted = sorted(underloaded, key=lambda c: c.utilization_pct)

    for over in overloaded:
        for under in underloaded_sorted:
            if under.available_slots > 0 and under.coach_user_id != over.coach_user_id:
                suggestions.append({
                    "from_coach": over.coach_name,
                    "from_coach_id": over.coach_user_id,
                    "to_coach": under.coach_name,
                    "to_coach_id": under.coach_user_id,
                    "reason": (
                        f"{over.coach_name} at {over.utilization_pct:.0f}% capacity, "
                        f"{under.coach_name} at {under.utilization_pct:.0f}% with "
                        f"{under.available_slots} slots available"
                    ),
                })
                break  # One suggestion per overloaded coach

    return suggestions


# ── Tier limits ──────────────────────────────────────────────────────────

TIER_LIMITS: dict[str, dict[str, int]] = {
    "free": {"max_coaches": 1, "max_athletes": 20},
    "pro": {"max_coaches": 5, "max_athletes": 100},
    "enterprise": {"max_coaches": 50, "max_athletes": 1000},
}


def check_tier_limit(tier: str, current_count: int, limit_key: str) -> bool:
    """Check if adding one more entity would exceed the tier limit.

    Returns True if within limits (can add), False if at/over limit.
    """
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    return current_count < limits.get(limit_key, 0)

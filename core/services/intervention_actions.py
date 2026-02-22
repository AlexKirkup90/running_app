from __future__ import annotations

from datetime import datetime, timedelta

from core.models import CoachActionLog, CoachIntervention


def apply_intervention_decision(s, rec: CoachIntervention, decision: str, note: str, modified_action: str | None, actor_user_id: int) -> None:
    note_fragment = note.strip() if note.strip() else "no_note"
    if decision == "accept_and_close":
        rec.status = "closed"
        rec.cooldown_until = None
        rec.why_factors = list(rec.why_factors or []) + [f"decision:accepted:{note_fragment}"]
    elif decision == "defer_24h":
        rec.cooldown_until = datetime.utcnow() + timedelta(hours=24)
        rec.why_factors = list(rec.why_factors or []) + [f"decision:defer_24h:{note_fragment}"]
    elif decision == "defer_72h":
        rec.cooldown_until = datetime.utcnow() + timedelta(hours=72)
        rec.why_factors = list(rec.why_factors or []) + [f"decision:defer_72h:{note_fragment}"]
    elif decision == "modify_action":
        rec.action_type = modified_action or rec.action_type
        rec.cooldown_until = None
        rec.why_factors = list(rec.why_factors or []) + [f"decision:modified:{note_fragment}"]
    else:
        rec.status = "closed"
        rec.cooldown_until = None
        rec.why_factors = list(rec.why_factors or []) + [f"decision:dismissed:{note_fragment}"]

    s.add(
        CoachActionLog(
            coach_user_id=actor_user_id,
            athlete_id=int(rec.athlete_id),
            action=f"intervention_{decision}",
            payload={"intervention_id": int(rec.id), "action_type": rec.action_type, "note": note.strip()},
        )
    )

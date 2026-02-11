"""automation policy hardening"""

from alembic import op

revision = "0002_policy_hardening"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create index if not exists idx_training_logs_athlete_date on training_logs(athlete_id, log_date)")
    op.execute("create index if not exists idx_events_athlete_date on events(athlete_id, event_date)")
    op.execute("create index if not exists idx_intervention_status on coach_interventions(status, created_at)")


def downgrade() -> None:
    op.execute("drop index if exists idx_training_logs_athlete_date")
    op.execute("drop index if exists idx_events_athlete_date")
    op.execute("drop index if exists idx_intervention_status")

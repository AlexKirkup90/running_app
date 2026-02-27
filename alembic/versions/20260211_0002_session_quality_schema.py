"""session quality schema upgrades

Revision ID: 20260211_0002
Revises: 20260101_0001
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260211_0002"
down_revision = "20260101_0001"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bool(bind is not None and bind.dialect.name == "sqlite")


def upgrade() -> None:
    op.add_column("athletes", sa.Column("max_hr", sa.Integer(), nullable=True))
    op.add_column("athletes", sa.Column("resting_hr", sa.Integer(), nullable=True))
    op.add_column("athletes", sa.Column("threshold_pace_sec_per_km", sa.Integer(), nullable=True))
    op.add_column("athletes", sa.Column("easy_pace_sec_per_km", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_check_constraint("ck_athletes_max_hr_positive", "athletes", "max_hr IS NULL OR max_hr > 0")
        op.create_check_constraint("ck_athletes_resting_hr_positive", "athletes", "resting_hr IS NULL OR resting_hr > 0")
        op.create_check_constraint(
            "ck_athletes_threshold_pace_positive", "athletes", "threshold_pace_sec_per_km IS NULL OR threshold_pace_sec_per_km > 0"
        )
        op.create_check_constraint("ck_athletes_easy_pace_positive", "athletes", "easy_pace_sec_per_km IS NULL OR easy_pace_sec_per_km > 0")

    op.add_column("sessions_library", sa.Column("intent", sa.String(length=40), nullable=False, server_default="general"))
    op.add_column("sessions_library", sa.Column("energy_system", sa.String(length=40), nullable=False, server_default="aerobic"))
    op.add_column("sessions_library", sa.Column("targets_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("sessions_library", sa.Column("progression_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("sessions_library", sa.Column("regression_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("sessions_library", sa.Column("coaching_notes", sa.Text(), nullable=False, server_default=""))

    op.add_column("training_logs", sa.Column("avg_hr", sa.Integer(), nullable=True))
    op.add_column("training_logs", sa.Column("max_hr", sa.Integer(), nullable=True))
    op.add_column("training_logs", sa.Column("avg_pace_sec_per_km", sa.Float(), nullable=True))
    if not _is_sqlite():
        op.create_check_constraint("ck_training_logs_avg_hr_positive", "training_logs", "avg_hr IS NULL OR avg_hr > 0")
        op.create_check_constraint("ck_training_logs_max_hr_positive", "training_logs", "max_hr IS NULL OR max_hr > 0")
        op.create_check_constraint(
            "ck_training_logs_hr_consistency", "training_logs", "avg_hr IS NULL OR max_hr IS NULL OR max_hr >= avg_hr"
        )
        op.create_check_constraint(
            "ck_training_logs_avg_pace_positive", "training_logs", "avg_pace_sec_per_km IS NULL OR avg_pace_sec_per_km > 0"
        )


def downgrade() -> None:
    if not _is_sqlite():
        op.drop_constraint("ck_training_logs_avg_pace_positive", "training_logs", type_="check")
        op.drop_constraint("ck_training_logs_hr_consistency", "training_logs", type_="check")
        op.drop_constraint("ck_training_logs_max_hr_positive", "training_logs", type_="check")
        op.drop_constraint("ck_training_logs_avg_hr_positive", "training_logs", type_="check")
    op.drop_column("training_logs", "avg_pace_sec_per_km")
    op.drop_column("training_logs", "max_hr")
    op.drop_column("training_logs", "avg_hr")

    op.drop_column("sessions_library", "coaching_notes")
    op.drop_column("sessions_library", "regression_json")
    op.drop_column("sessions_library", "progression_json")
    op.drop_column("sessions_library", "targets_json")
    op.drop_column("sessions_library", "energy_system")
    op.drop_column("sessions_library", "intent")

    if not _is_sqlite():
        op.drop_constraint("ck_athletes_easy_pace_positive", "athletes", type_="check")
        op.drop_constraint("ck_athletes_threshold_pace_positive", "athletes", type_="check")
        op.drop_constraint("ck_athletes_resting_hr_positive", "athletes", type_="check")
        op.drop_constraint("ck_athletes_max_hr_positive", "athletes", type_="check")
    op.drop_column("athletes", "easy_pace_sec_per_km")
    op.drop_column("athletes", "threshold_pace_sec_per_km")
    op.drop_column("athletes", "resting_hr")
    op.drop_column("athletes", "max_hr")

"""Reconcile model vs migration discrepancies

Changes:
  health_logs:
    - value: Float -> String (flexible "38.5", "150ml" etc.)
    - notes -> note (singular, String)
    - logged_at -> recorded_at
    - drop unit column

  vaccination_records:
    - next_due_date -> next_due
    - notes -> note (singular, String)
    - drop dose_number column

  child_profiles:
    - add playfab_id (String, unique, nullable)
    - add real_name (String(50), nullable initially)
    - add emergency_address (String, nullable)
    - add unique constraint on child_id

  children:
    - make user_id NOT NULL (requires no NULL data)

  chat_histories:
    - add session_id (String, nullable, indexed)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── health_logs ─────────────────────────────────────────────────────────
    # 1. value: Float -> String
    op.alter_column(
        "health_logs", "value",
        existing_type=sa.Float(),
        type_=sa.String(),
        existing_nullable=True,
        postgresql_using="value::text",
    )
    # 2. drop unit
    op.drop_column("health_logs", "unit")
    # 3. notes -> note
    op.alter_column("health_logs", "notes", new_column_name="note")
    # 4. logged_at -> recorded_at
    op.alter_column("health_logs", "logged_at", new_column_name="recorded_at")

    # ── vaccination_records ──────────────────────────────────────────────────
    # 1. drop dose_number
    op.drop_column("vaccination_records", "dose_number")
    # 2. next_due_date -> next_due
    op.alter_column("vaccination_records", "next_due_date", new_column_name="next_due")
    # 3. notes -> note
    op.alter_column("vaccination_records", "notes", new_column_name="note")

    # ── child_profiles ───────────────────────────────────────────────────────
    op.add_column("child_profiles",
        sa.Column("playfab_id", sa.String(), nullable=True))
    op.add_column("child_profiles",
        sa.Column("real_name", sa.String(50), nullable=True, server_default=""))
    op.add_column("child_profiles",
        sa.Column("emergency_address", sa.String(), nullable=True))
    op.add_column("child_profiles",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_child_profiles_child_id", "child_profiles", ["child_id"])
    op.create_unique_constraint(
        "uq_child_profiles_playfab_id", "child_profiles", ["playfab_id"])
    op.create_index(
        "ix_child_profiles_playfab_id", "child_profiles", ["playfab_id"], unique=True)

    # ── children: user_id NOT NULL ───────────────────────────────────────────
    # Clean orphaned rows first, then tighten constraint
    op.execute("DELETE FROM children WHERE user_id IS NULL")
    op.alter_column(
        "children", "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    # Add ON DELETE CASCADE to user_id FK
    op.drop_constraint("children_user_id_fkey", "children", type_="foreignkey")
    op.create_foreign_key(
        "children_user_id_fkey", "children", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )

    # ── chat_histories: add session_id ───────────────────────────────────────
    op.add_column("chat_histories",
        sa.Column("session_id", sa.String(36), nullable=True))
    op.create_index(
        "ix_chat_histories_session_id", "chat_histories", ["session_id"], unique=False)


def downgrade() -> None:
    # chat_histories
    op.drop_index("ix_chat_histories_session_id", table_name="chat_histories")
    op.drop_column("chat_histories", "session_id")

    # children
    op.drop_constraint("children_user_id_fkey", "children", type_="foreignkey")
    op.create_foreign_key(
        "children_user_id_fkey", "children", "users", ["user_id"], ["id"])
    op.alter_column("children", "user_id", existing_type=sa.Integer(), nullable=True)

    # child_profiles
    op.drop_index("ix_child_profiles_playfab_id", table_name="child_profiles")
    op.drop_constraint("uq_child_profiles_playfab_id", "child_profiles", type_="unique")
    op.drop_constraint("uq_child_profiles_child_id", "child_profiles", type_="unique")
    op.drop_column("child_profiles", "updated_at")
    op.drop_column("child_profiles", "emergency_address")
    op.drop_column("child_profiles", "real_name")
    op.drop_column("child_profiles", "playfab_id")

    # vaccination_records
    op.alter_column("vaccination_records", "note", new_column_name="notes")
    op.alter_column("vaccination_records", "next_due", new_column_name="next_due_date")
    op.add_column("vaccination_records",
        sa.Column("dose_number", sa.Integer(), nullable=True))

    # health_logs
    op.alter_column("health_logs", "recorded_at", new_column_name="logged_at")
    op.alter_column("health_logs", "note", new_column_name="notes")
    op.add_column("health_logs",
        sa.Column("unit", sa.String(20), nullable=True))
    op.alter_column(
        "health_logs", "value",
        existing_type=sa.String(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="value::double precision",
    )

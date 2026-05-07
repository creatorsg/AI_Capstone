"""Initial schema (전체 테이블 초기 생성)"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id",              sa.Integer(),     nullable=False),
        sa.Column("email",           sa.String(255),   nullable=False),
        sa.Column("hashed_password", sa.String(255),   nullable=False),
        sa.Column("nickname",        sa.String(50),    nullable=True),
        sa.Column("is_active",       sa.Boolean(),     nullable=True, server_default="true"),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at",      sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id",    "users", ["id"],    unique=False)

    # children
    op.create_table(
        "children",
        sa.Column("id",         sa.Integer(),     nullable=False),
        sa.Column("user_id",    sa.Integer(),     nullable=True),
        sa.Column("name",       sa.String(50),    nullable=False),
        sa.Column("birth_date", sa.Date(),        nullable=True),
        sa.Column("gender",     sa.String(10),    nullable=True),
        sa.Column("allergies",  postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("conditions", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("notes",      sa.Text(),        nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_children_id",      "children", ["id"],      unique=False)
    op.create_index("ix_children_user_id", "children", ["user_id"], unique=False)

    # child_profiles
    op.create_table(
        "child_profiles",
        sa.Column("id",            sa.Integer(),   nullable=False),
        sa.Column("child_id",      sa.Integer(),   nullable=False),
        sa.Column("blood_type",    sa.String(5),   nullable=True),
        sa.Column("medical_notes", sa.Text(),      nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_child_profiles_id", "child_profiles", ["id"], unique=False)

    # health_logs
    op.create_table(
        "health_logs",
        sa.Column("id",         sa.Integer(),  nullable=False),
        sa.Column("child_id",   sa.Integer(),  nullable=False),
        sa.Column("log_type",   sa.String(50), nullable=False),
        sa.Column("value",      sa.Float(),    nullable=True),
        sa.Column("unit",       sa.String(20), nullable=True),
        sa.Column("notes",      sa.Text(),     nullable=True),
        sa.Column("logged_at",  sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_logs_id", "health_logs", ["id"], unique=False)

    # vaccination_records
    op.create_table(
        "vaccination_records",
        sa.Column("id",               sa.Integer(),  nullable=False),
        sa.Column("child_id",         sa.Integer(),  nullable=False),
        sa.Column("vaccine_name",     sa.String(100), nullable=False),
        sa.Column("dose_number",      sa.Integer(),  nullable=True),
        sa.Column("vaccinated_at",    sa.Date(),     nullable=True),
        sa.Column("next_due_date",    sa.Date(),     nullable=True),
        sa.Column("notes",            sa.Text(),     nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vaccination_records_id", "vaccination_records", ["id"], unique=False)

    # chat_histories
    op.create_table(
        "chat_histories",
        sa.Column("id",         sa.Integer(),  nullable=False),
        sa.Column("child_id",   sa.Integer(),  nullable=True),
        sa.Column("question",   sa.Text(),     nullable=False),
        sa.Column("answer",     sa.Text(),     nullable=False),
        sa.Column("context",    postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_histories_id", "chat_histories", ["id"], unique=False)

    # conversation_sessions
    op.create_table(
        "conversation_sessions",
        sa.Column("id",                sa.String(36),  nullable=False),
        sa.Column("child_id",          sa.Integer(),   nullable=True),
        sa.Column("original_question", sa.Text(),      nullable=False),
        sa.Column("context",           postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("pending_field",     sa.String(50),  nullable=True),
        sa.Column("status",            sa.String(20),  nullable=True, server_default="'active'"),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("conversation_sessions")
    op.drop_index("ix_chat_histories_id",         table_name="chat_histories")
    op.drop_table("chat_histories")
    op.drop_index("ix_vaccination_records_id",    table_name="vaccination_records")
    op.drop_table("vaccination_records")
    op.drop_index("ix_health_logs_id",            table_name="health_logs")
    op.drop_table("health_logs")
    op.drop_index("ix_child_profiles_id",         table_name="child_profiles")
    op.drop_table("child_profiles")
    op.drop_index("ix_children_user_id",          table_name="children")
    op.drop_index("ix_children_id",               table_name="children")
    op.drop_table("children")
    op.drop_index("ix_users_email",               table_name="users")
    op.drop_index("ix_users_id",                  table_name="users")
    op.drop_table("users")

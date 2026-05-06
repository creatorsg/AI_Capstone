"""Add height/weight to children, fix nullable columns

변경 사항:
  1. children 테이블에 height_cm, weight_kg 컬럼 추가
  2. conversation_sessions.original_question: NOT NULL → nullable
     (턴 완료 후 None 으로 초기화하는 코드와 일치시키기 위함)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── children: 키/체중 컬럼 추가 ─────────────────────────────────────────
    op.add_column(
        "children",
        sa.Column("height_cm", sa.Float(), nullable=True, comment="키 (cm)"),
    )
    op.add_column(
        "children",
        sa.Column("weight_kg", sa.Float(), nullable=True, comment="체중 (kg)"),
    )

    # ── conversation_sessions: original_question NOT NULL → nullable ────────
    # 채팅 턴 완료 시 session.original_question = None 으로 초기화하기 때문에
    # NOT NULL 제약이 있으면 db.commit() 에서 500 에러 발생
    op.alter_column(
        "conversation_sessions",
        "original_question",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    # original_question 다시 NOT NULL 로 (기존 NULL 데이터가 있으면 실패할 수 있음)
    op.alter_column(
        "conversation_sessions",
        "original_question",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 키/체중 컬럼 제거
    op.drop_column("children", "weight_kg")
    op.drop_column("children", "height_cm")

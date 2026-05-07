"""placeholder migration 0004 - chain continuity only"""
from typing import Sequence, Union
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None: pass
def downgrade() -> None: pass

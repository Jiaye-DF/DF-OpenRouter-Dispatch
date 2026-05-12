"""baseline: 帶起原 Flyway V1~V11 schema。

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-12

此 migration 為從 Flyway 切換到 Alembic 時的 baseline,內容仍是原始 SQL 檔
(放在 ``backend/alembic/baseline_sql/`` 目錄下),按版號順序逐檔執行。

從此版號 (0002) 之後的 migration 才會走 Alembic 標準 ``op.create_table`` 等 Python API。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BASELINE_DIR = Path(__file__).resolve().parent.parent / "baseline_sql"
_VERSION_RE = re.compile(r"^V(\d+)__")


def _version_key(path: Path) -> int:
    m = _VERSION_RE.match(path.name)
    if not m:
        raise RuntimeError(f"baseline SQL 檔名不符 V<N>__ 規則: {path.name}")
    return int(m.group(1))


def upgrade() -> None:
    files = sorted(BASELINE_DIR.glob("V*.sql"), key=_version_key)
    if not files:
        raise RuntimeError(f"baseline SQL 不存在: {BASELINE_DIR}")
    for sql_file in files:
        sql = sql_file.read_text(encoding="utf-8")
        op.execute(sql)


def downgrade() -> None:
    # baseline 不支援 downgrade;若需重建請直接 drop database 重來。
    op.execute("DROP SCHEMA public CASCADE")
    op.execute("CREATE SCHEMA public")

"""修 bug:ai_eval_judge_settings.ai_judge_slot 唯一約束改 partial(排除軟刪)。

問題:建表時 `ai_judge_slot` 用全域 `unique=True`(PG 自動約束
`ai_eval_judge_settings_ai_judge_slot_key`,不排除軟刪)。判別模型設定 PUT 為「整批覆寫」:
先把舊有效設定軟刪(is_deleted=True),再 insert 新 slot 1/2/3。但軟刪列的 slot 1/2/3 仍
佔用全域 UNIQUE → 新 insert 撞約束 → **設定一次後即無法再修改**。

修正:對齊同表 `model_uid` 的 partial index 慣例,把 slot 唯一改為「僅在未軟刪列唯一」
(partial unique index `WHERE is_deleted = false`)。如此軟刪後 slot 即釋放,整批覆寫可正常進行;
同時間有效設定仍保證 slot 1/2/3 不重複。

downgrade 對稱還原為全域 UNIQUE 約束(注意:若資料表含軟刪的重複 slot,downgrade 會失敗,
屬預期——還原前需先清理軟刪列)。

Revision ID: 0027_judge_slot_partial_unique
Revises: 0026_ai_eval_reruns
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_judge_slot_partial_unique"
down_revision: str | Sequence[str] | None = "0026_ai_eval_reruns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "ai_eval_judge_settings"
_OLD_CONSTRAINT = "ai_eval_judge_settings_ai_judge_slot_key"
_NEW_INDEX = "uq_ai_eval_judge_settings_slot_active"


def upgrade() -> None:
    # 1) 移除全域 UNIQUE 約束(建表 unique=True 自動產生,不排除軟刪)。
    op.drop_constraint(_OLD_CONSTRAINT, _TABLE, type_="unique")
    # 2) 改為 partial unique index:僅在未軟刪列唯一(對齊 model_uid 慣例,釋放軟刪 slot)。
    op.create_index(
        _NEW_INDEX,
        _TABLE,
        ["ai_judge_slot"],
        unique=True,
        postgresql_where=sa.text("is_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index(_NEW_INDEX, table_name=_TABLE)
    op.create_unique_constraint(_OLD_CONSTRAINT, _TABLE, ["ai_judge_slot"])

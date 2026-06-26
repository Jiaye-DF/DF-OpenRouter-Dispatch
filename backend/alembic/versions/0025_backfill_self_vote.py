"""v2.0:回算既有 ai_self_vote 為新語意(裁判 vs 推薦)。

0024 更正了 ai_self_vote 的語意(由「原模型 vs 推薦」改為「判別模型自己 vs 推薦」),
但既有資料仍是舊邏輯算出的值。本檔以確定性方式重算每筆已成功評審候選的
ai_self_vote = 「該裁判(models.model_key,經 model_uid 連)的廠商前綴」是否等於
「ai_recommend_model 的廠商前綴」;任一側無 `provider/` 前綴 → NULL。

廠商前綴規則與 services/ai_model_eval.py `_vendor_prefix` 一致:取第一個 `/` 前段、
trim、lower,空字串視為無法判定(NULL)。失敗候選(ai_recommend_model 為 NULL)
維持 NULL。

可逆:downgrade 以舊邏輯(原模型 usage_logs.model vs 推薦)回算還原。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025_backfill_self_vote"
down_revision: str | Sequence[str] | None = "0024_self_vote_comment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 與 _vendor_prefix 對齊:第一個 '/' 前段、trim、lower、空→NULL。
_PREFIX_JUDGE = "nullif(lower(trim(split_part(jm.model_key, '/', 1))), '')"
_PREFIX_REC = "nullif(lower(trim(split_part(c.ai_recommend_model, '/', 1))), '')"
_PREFIX_ORIG = "nullif(lower(trim(split_part(u.model, '/', 1))), '')"


def upgrade() -> None:
    # 新語意:裁判(model_uid → models.model_key)vs 推薦。
    op.execute(
        f"""
        UPDATE ai_model_eval_candidates AS c
        SET ai_self_vote = CASE
            WHEN c.ai_recommend_model IS NULL THEN NULL
            WHEN position('/' in jm.model_key) = 0
              OR position('/' in c.ai_recommend_model) = 0 THEN NULL
            WHEN {_PREFIX_JUDGE} IS NULL OR {_PREFIX_REC} IS NULL THEN NULL
            ELSE ({_PREFIX_JUDGE} = {_PREFIX_REC})
        END
        FROM models AS jm
        WHERE c.model_uid = jm.model_uid
        """
    )


def downgrade() -> None:
    # 舊語意:原模型(usage_logs.model)vs 推薦。
    op.execute(
        f"""
        UPDATE ai_model_eval_candidates AS c
        SET ai_self_vote = CASE
            WHEN c.ai_recommend_model IS NULL THEN NULL
            WHEN position('/' in u.model) = 0
              OR position('/' in c.ai_recommend_model) = 0 THEN NULL
            WHEN {_PREFIX_ORIG} IS NULL OR {_PREFIX_REC} IS NULL THEN NULL
            ELSE ({_PREFIX_ORIG} = {_PREFIX_REC})
        END
        FROM ai_model_evaluations AS e
        JOIN usage_logs AS u ON e.usage_log_uid = u.usage_log_uid
        WHERE c.ai_evaluation_uid = e.ai_evaluation_uid
        """
    )

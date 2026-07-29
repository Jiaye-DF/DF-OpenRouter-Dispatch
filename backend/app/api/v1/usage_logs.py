from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1._scope_filters import resolve_filters
from app.clients.s3 import S3Client, S3Error, get_s3_client
from app.core.config import get_settings
from app.core.deps import DbDep, UserDep
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.response import success_response
from app.repositories.usage_log import UsageLogRepository
from app.schemas.common import Page
from app.schemas.usage_log import UsageLogDetail, UsageLogListItem
from app.services.request_snapshot import attachment_form, attachment_ref_of

logger = get_logger(__name__)

router = APIRouter(prefix="/usage-logs", tags=["usage-logs"])

# 附件 part → 內容參照欄位。刻意與 `request_snapshot._REF_FIELDS` 各存一份:該層規範為
# 不 import 任何 service 的純函式層,且其對外 API 只回「參照是什麼」;本層要**寫回**,
# 需要知道「參照放在哪一欄」。
_REF_FIELDS: tuple[tuple[str, str], ...] = (("image_url", "url"), ("file", "key"))


def _with_ref(part: Mapping[str, object], url: str) -> dict[str, object]:
    """把附件 part 內的參照欄位換成 presigned URL。

    一律回**新** dict:`request_content` 來自 ORM 實例的 JSONB,就地改寫等於改到快照本身。
    """
    out: dict[str, object] = dict(part)
    for key, field in _REF_FIELDS:
        inner = out.get(key)
        if isinstance(inner, Mapping) and isinstance(inner.get(field), str):
            out[key] = {**inner, field: url}
            break
    return out


class _Presigner:
    """把 `request_content` 內的 S3 物件 key 換成短期 presigned URL(D.9)。

    presign 需要 I/O,故**不**放在 `request_snapshot`(純函式層),形態判別則一律沿用
    該層的 `attachment_form` / `attachment_ref_of`,不在本層重寫字串判別。

    四態只有 `object_key` 需要換:

    - `data_uri`:v2.2.0(含全部歷史列)的舊快照,遷移期新舊並存 → **原樣回吐**,
      讓前端既有渲染路徑保底。
    - `remote_url`:呼叫端原本就給遠端 URL(§D.2 不代抓)→ 原樣。
    - `upload_failed`:前端據此顯示「內容未留存」→ 原樣(濾掉會複製 v2.1.2 的靜默失效)。

    presign 失敗一律**退回原值 + log warning**,整支 API 仍回 200:物件儲存是記帳 /
    稽核輔助層,不該有權力擋掉明細讀取(§D.5)。presigned URL 視同臨時憑證,
    **禁**入 log(`90-third-party-service/09-object-storage.md`)。
    """

    def __init__(self, *, client: S3Client, ttl: int, usage_log_uid: UUID) -> None:
        self._client = client
        self._ttl = ttl
        self._uid = usage_log_uid

    async def sign_content(self, content: Mapping[str, object]) -> dict[str, object]:
        """走訪快照的**兩種形狀**(見 `request_snapshot` 檔頭)並換掉附件內的物件 key。"""
        out: dict[str, object] = dict(content)

        messages = content.get("messages")
        if isinstance(messages, list):
            # messages 直傳模式(v2.1.2 起):沒有 text / images / files 鍵。
            out["messages"] = [await self._sign_message(m) for m in messages]
            return out

        images = content.get("images")
        if isinstance(images, list):
            out["images"] = [await self._sign_value(v) for v in images]

        files = content.get("files")
        if isinstance(files, list):
            # 單輪 `files[i]` 為**字串**時是 v2.2.0「只留檔名」的快照,不是物件 key
            # (v2.2.1 成功值一律為 dict)。presign 只是本地簽章計算、不驗物件是否存在,
            # 拿檔名去簽會簽出一條指向不存在物件、看起來卻很正常的 URL。
            out["files"] = [
                await self._sign_value(v) if isinstance(v, Mapping) else v for v in files
            ]
        return out

    async def _sign_message(self, message: object) -> object:
        if not isinstance(message, Mapping):
            return message
        parts = message.get("content")
        if not isinstance(parts, list):
            # content 為字串(純文字訊息)→ 無附件可換。
            return message
        out: dict[str, object] = dict(message)
        out["content"] = [await self._sign_value(p) for p in parts]
        return out

    async def _sign_value(self, value: object) -> object:
        if attachment_form(value) != "object_key":
            return value
        ref = attachment_ref_of(value)
        if ref is None:
            return value
        url = await self._presign(ref)
        if url is None:
            return value
        # 單輪 `images[i]` 的值本身就是 key(字串);其餘為 part,換掉內層參照欄位。
        if isinstance(value, str):
            return url
        return _with_ref(value, url) if isinstance(value, Mapping) else value

    async def _presign(self, key: str) -> str | None:
        try:
            return await self._client.presign_get(key, self._ttl)
        except S3Error as err:
            self._warn(type(err).__name__, err.aws_code or "-")
        except Exception as err:  # noqa: BLE001 - best-effort:presign 失敗不得擋掉明細讀取
            self._warn(type(err).__name__, "-")
        return None

    def _warn(self, error: str, aws_code: str) -> None:
        # 只記例外類別與 AWS 錯誤碼;物件 key 已由 S3Client 記過,
        # presigned URL 與 AWS 憑證**禁**入 log。
        logger.warning(
            "presign 失敗,該附件退回原樣值 usage_log_uid=%s error=%s aws_code=%s",
            self._uid,
            error,
            aws_code,
        )


async def _presign_request_content(
    content: dict[str, object] | None, *, usage_log_uid: UUID
) -> dict[str, object] | None:
    """明細回吐前把 S3 物件路徑換成短期 presigned URL(不另開 302 導轉端點,D.9)。

    `S3_STORAGE_ENABLED=false` → 原樣回吐、**完全不呼叫** S3(行為與 v2.2.0 一致)。
    """
    settings = get_settings()
    if not settings.S3_STORAGE_ENABLED or not content:
        return content
    try:
        client = get_s3_client()
    except S3Error as err:
        # 開關已開卻取不到 client(bucket 未設 / 憑證缺漏)屬設定錯,但仍不擋讀取:
        # 全部附件原樣回吐,前端沿用既有渲染路徑。
        logger.warning(
            "S3 client 取得失敗,本筆附件全數原樣回吐 usage_log_uid=%s error=%s",
            usage_log_uid,
            type(err).__name__,
        )
        return content
    presigner = _Presigner(
        client=client,
        ttl=settings.S3_PRESIGN_TTL_SECONDS,
        usage_log_uid=usage_log_uid,
    )
    return await presigner.sign_content(content)


@router.get("", summary="用量紀錄列表")
async def list_usage_logs(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    department_uid: UUID | None = None,
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    model: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    status: str | None = None,
    used_tools: bool | None = None,
    pid: int | None = Query(default=None, ge=1),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    # 權限收斂於 resolve_filters:admin 不鎖、非-admin 強制自身部門、跨部門顯式傳參 → 403。
    dept, project, user = resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows, total = await repo.list(
        page=page,
        size=size,
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        model=model,
        from_time=from_time,
        to_time=to_time,
        status=status,
        used_tools=used_tools,
        pid=pid,
        order=order,
    )
    data = Page[UsageLogListItem](
        items=[
            UsageLogListItem.model_validate(ul).model_copy(
                update={"project_code": code, "project_name": name}
            )
            for ul, code, name in rows
        ],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/{uid}", summary="用量紀錄單筆")
async def get_usage_log(uid: UUID, actor: UserDep, db: DbDep):
    # resolve_filters 回傳的 dept:admin → None(不鎖)、非-admin → 自身部門 UID。
    # 權限一律收斂於 resolve_filters,不在 router 依角色散落判斷。
    dept, _, _ = resolve_filters(actor, None, None, None)
    repo = UsageLogRepository(db)
    row = await repo.get_by_uid_with_project(uid)
    if row is None:
        raise AppError("not_found", code=404)
    log, project_code, project_name = row
    # 非-admin 取他部門明細 → 404(不以存在與否側漏,對齊 propose §D.1);admin dept 為 None 不鎖。
    if dept is not None and log.department_uid != dept:
        raise AppError("not_found", code=404)
    detail = UsageLogDetail.model_validate(log)
    detail = detail.model_copy(
        update={
            "project_code": project_code,
            "project_name": project_name,
            # 列表端點刻意不含 request_content(見 schemas/usage_log.py),故 presign 只在此處做。
            "request_content": await _presign_request_content(
                detail.request_content, usage_log_uid=uid
            ),
        }
    )
    return success_response(data=detail.model_dump(mode="json"), detail="success")

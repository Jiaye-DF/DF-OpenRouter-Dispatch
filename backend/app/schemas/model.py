from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatFile(BaseModel):
    """單一上傳檔案,對應 OpenRouter 的 `file` content part(如 PDF)。

    - `filename`:檔名;OpenRouter 必填,亦為 usage_logs 唯一保留的檔案資訊。
    - `file_data`:base64 data URL(如 `data:application/pdf;base64,...`)或可公開
      存取的遠端 URL;**僅用於本次送往下游,不寫入用量紀錄**(法務考量)。
    """

    filename: str = Field(min_length=1, max_length=255)
    file_data: str = Field(min_length=1)


class ChatTextPart(BaseModel):
    """messages 直傳模式的 `text` content part(OpenRouter/OpenAI 風格)。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"]
    text: str


class ChatImageUrl(BaseModel):
    """`image_url` part 的內層物件;白名單只收 `url`(與單輪 `images` 能力對齊)。"""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)


class ChatImagePart(BaseModel):
    """messages 直傳模式的 `image_url` content part。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["image_url"]
    image_url: ChatImageUrl


class ChatFilePart(BaseModel):
    """messages 直傳模式的 `file` content part;形狀對齊既有 `ChatFile`。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["file"]
    file: ChatFile


# content parts 白名單:只收 text / image_url / file(與單輪能力集對齊;
# video 等其他 type 一律驗證失敗,對齊 50-openrouter.md § 6.1)。
ChatContentPart = Annotated[
    ChatTextPart | ChatImagePart | ChatFilePart,
    Field(discriminator="type"),
]


class ChatMessage(BaseModel):
    """messages 直傳模式的單則訊息(v2.1.2,對齊 50-openrouter.md § 6.1)。

    - `role`:白名單只收 `system` / `user` / `assistant`;`tool` role 與
      `tool_calls` 回傳鏈本版不開放。
    - `content`:字串或 content parts 陣列(白名單見 `ChatContentPart`)。
    """

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str | list[ChatContentPart]


class ResponseFormat(BaseModel):
    """生成參數 `response_format` 的型別化白名單 schema(v2.1.2,禁 raw dict)。

    - `type="json_object"`:不得帶 `json_schema`。
    - `type="json_schema"`:必帶 `json_schema` 物件(原樣透傳下游)。
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["json_object", "json_schema"]
    json_schema: dict[str, object] | None = None

    @model_validator(mode="after")
    def _validate_json_schema_presence(self) -> Self:
        if self.type == "json_schema" and self.json_schema is None:
            raise ValueError("type 為 json_schema 時必須提供 json_schema 物件")
        if self.type == "json_object" and self.json_schema is not None:
            raise ValueError("type 為 json_object 時不可提供 json_schema 物件")
        return self


class ChatRequest(BaseModel):
    """Chat 代理的請求 body。

    輸入收斂為白名單參數,不暴露 OpenAI 全部欄位(對齊 50-openrouter.md § 5 / § 6):

    - 內容模式**互斥擇一**(同時帶 → 400):
      - 單輪模式:`text` / `images` / `files` 組成單一 user 訊息的多模態內容。
      - messages 直傳模式(v2.1.2):`messages` 自帶多輪對話 / system prompt /
        assistant 歷史,白名單驗證後原樣透傳。
    - `videos`:本版本不支援,送出即回 400(僅佔位,待未來版本)。
    - `tools`:見下方欄位說明;兩種內容模式皆可搭配。
    - 生成參數(v2.1.2):`temperature` / `max_tokens` / `response_format` 三項,
      兩種內容模式皆可帶;未帶(None)不注入 payload,走模型預設值。
    """

    model: str = Field(min_length=1, max_length=128)
    text: str | None = None
    images: list[str] | None = None
    files: list[ChatFile] | None = None  # 上傳檔案(如 PDF);僅檔名會寫入用量紀錄
    videos: list[str] | None = None  # 本版本不支援；送出即回 400
    # 直接透傳給下游(OpenRouter / internal),格式同 OpenAI tools 規格。
    # 例:OpenRouter 內建工具 [{"type": "openrouter:web_search"}]。
    # 注意:本版本僅支援「server 端工具」(回應仍為純文字);尚未開放會回
    # tool_calls 的 function calling。
    tools: list[dict[str, Any]] | None = None
    # messages 直傳模式(v2.1.2):與 text/images/files 互斥;不設應用層筆數上限
    # (模型 context window 為自然上限,對齊 propose v2.1.2 §D.2)。
    messages: list[ChatMessage] | None = None
    # 生成參數三欄(v2.1.2,§D.7);值域對齊 OpenAI/OpenRouter 慣例。
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    response_format: ResponseFormat | None = None

    @model_validator(mode="after")
    def _validate_messages_mode(self) -> Self:
        """messages 直傳模式的互斥驗證(對齊 50-openrouter.md § 6.1)。"""
        if self.messages is None:
            return self
        if len(self.messages) == 0:
            raise ValueError("messages 不可為空陣列")
        conflicts = [
            name
            for name, value in (("text", self.text), ("images", self.images), ("files", self.files))
            if value
        ]
        if conflicts:
            raise ValueError(f"messages 與 {'/'.join(conflicts)} 互斥,擇一提供")
        return self


class ChatResponse(BaseModel):
    """直接回 OpenRouter 原始 body（去除內部識別欄位後）。"""

    id: str | None = None
    model: str | None = None
    choices: list[dict[str, Any]] = []
    usage: dict[str, Any] | None = None
    created: int | None = None


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_uid: UUID
    provider: str
    model_key: str
    name: str
    description: str | None = None

    context_length: int | None = None
    max_completion_tokens: int | None = None
    modality: str | None = None
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)
    tokenizer: str | None = None

    price_prompt_per_token: Decimal | None = None
    price_completion_per_token: Decimal | None = None
    price_image_per_image: Decimal | None = None
    price_request_flat: Decimal | None = None

    is_moderated: bool
    tier_key: str | None = None

    openrouter_created_at: datetime | None = None
    last_synced_at: datetime

    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class AllowedModelRead(BaseModel):
    """公開「可用模型」清單的精簡視圖(供 SDK 使用者瀏覽並複製 model_key)。

    刻意只暴露挑選模型所需的基本欄位;定價、tokenizer、時間戳等內部資訊不對外。
    """

    model_config = ConfigDict(from_attributes=True)

    provider: str
    model_key: str
    name: str
    description: str | None = None
    context_length: int | None = None
    modality: str | None = None
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)


class ModelPatch(BaseModel):
    """Admin 編輯模型。

    - openrouter:僅可改 `is_active` 與 `tier_key`;其他欄位以同步資料為準(API 層忽略)。
    - internal:可改 `is_active` / `tier_key` / `name` / `description` / `context_length` / `modality`。
    """

    is_active: bool | None = None
    tier_key: str | None = Field(default=None, max_length=32)
    # 以下 internal-only;openrouter 編輯時忽略
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    context_length: int | None = Field(default=None, ge=0)
    modality: str | None = Field(default=None, max_length=64)
    input_modalities: list[str] | None = Field(default=None, max_length=16)
    output_modalities: list[str] | None = Field(default=None, max_length=16)


class ModelCreateRequest(BaseModel):
    """手動建立模型(僅接受 provider='internal';openrouter 必須走同步)。"""

    provider: str = Field(min_length=1, max_length=32)
    model_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_\-/.]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    context_length: int | None = Field(default=None, ge=0)
    modality: str | None = Field(default="text->text", max_length=64)
    input_modalities: list[str] = Field(default_factory=lambda: ["text"], max_length=16)
    output_modalities: list[str] = Field(default_factory=lambda: ["text"], max_length=16)
    tier_key: str | None = Field(default=None, max_length=32)


class ModelSyncResult(BaseModel):
    """同步流程的計數結果(對齊 propose § 6.2 第 7 步)。"""

    added: int
    updated: int
    deactivated: int
    total: int
    credits_synced: int
    credits_failed: int
    synced_at: datetime


class ModelBulkActivateRequest(BaseModel):
    """批次切換 OpenRouter 模型可用性(admin)。

    - `all`:啟用全部 OpenRouter 模型(is_active=TRUE)。
    - `defaults`:僅保留白名單(allowed_models)模型 —— 白名單內的啟用、其餘停用,
      等同重新套用 sync 的白名單規則(但不向 OpenRouter 重新拉取)。

    兩種模式皆只作用於 provider='openrouter' 的模型,不影響 internal 模型。
    """

    mode: Literal["all", "defaults"]


class ModelBulkActivateResult(BaseModel):
    """批次切換結果計數。"""

    mode: Literal["all", "defaults"]
    activated: int
    deactivated: int

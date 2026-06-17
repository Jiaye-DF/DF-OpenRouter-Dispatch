export const meta = {
  name: 'v1.9.1-implement',
  description: '多代理實作 v1.9.1(申請單生命週期 + 規則路由 + AI 欄位驗證自動開通)',
  phases: [
    { title: '後端基礎', detail: 'DB/model、config、schema、repository(可並行)' },
    { title: '後端服務', detail: 'router、agent(AI)、provision(可並行)' },
    { title: '後端端點', detail: '重寫 api_key_requests.py 端點與編排' },
    { title: '前端', detail: 'types+endpoints → page+dialog(pipeline)' },
    { title: '文件', detail: 'user-guide / admin-guide(可並行)' },
    { title: '驗證', detail: '後端 import/lint + 前端 tsc + 契約 DoD 檢查' },
  ],
}

const ROOT = 'c:/Users/jiaye.he/Desktop/tools-project/DF-OpenRouter-Dispatch'
const BE = `${ROOT}/backend`
const FE = `${ROOT}/frontend`
const TASKS = `${ROOT}/docs/Tasks/v1.9/tasks-v1.9.1.md`

// ── 全後端代理共用:既有慣例 ──
const CONV = `
專案慣例(務必遵循,回應/註解一律繁體中文,不過度抽象、不加無謂註解):
- 全 async SQLAlchemy。Repository 以 __init__(self, db: AsyncSession) 建構,查詢一律加 .is_deleted.is_(False)。
- UUID 產生:from uuid_utils import uuid7;欄位值用 UUID(str(uuid7()))。
- 稽核:from app.core.audit import write_audit;簽名 write_audit(db, *, actor_user_uid, actor_role, action, target_type, target_uid, result="success", detail=None, ip=None, extra=None);呼叫端負責 commit。
- 例外:from app.core.exceptions import AppError;AppError(detail: str, code: int = 400, data=None)。
- 回應:from app.core.response import success_response;success_response(data=<dict>, detail="success");data 用 <Schema>.model_validate(row).model_dump(mode="json")。
- Deps:from app.core.deps import UserDep, AdminDep, DbDep, ClientIpDep。Actor 屬性:actor.user_uid / actor.role / actor.is_admin / actor.department_uid / actor.email。
- Snowflake 專案 code:from app.core.snowflake import generate_id_str。
- 既有 service:
  - app.services.sdk_key.create_sdk_key(db, *, department_uid, name) -> (SdkApiKey, full_plaintext:str)
  - app.services.sdk_key.reveal_sdk_key(row) -> str | None(回 row.key_values)
  - app.services.user_token.generate_token(db, *, user_uid) -> (token:str, issued_at:datetime)
  - app.services.user_token.revoke_tokens(db, *, user_uid, reason) -> None
- OpenRouter:OpenRouterClient.chat_completion(payload: dict, *, api_key: str) -> dict;model 放 payload["model"]。
- Model 欄位:Department(department_uid, code, name);Project(project_uid, department_uid, code, name, description);User(user_uid, account, username, password_hash, role, department_uid, employee_id, email);SdkApiKey(sdk_api_key_uid, department_uid, name, key_hash, key_prefix, key_values)。
- TimestampMixin 提供 is_active(default True)/is_deleted(default False);新建 row 經 db.flush() 後 is_active 即為 True。
`

// ── 後端服務/端點之間的介面契約(所有後端代理都嵌入,確保簽名一致) ──
const IFACE = `
跨檔介面契約(嚴格遵守,各代理需互相吻合):

# services/api_key_request_router.py
from dataclasses import dataclass
@dataclass
class RouteResult:
    decision: str            # "manual" | "ai" | "system_cancel"
    reason: str | None       # 中文理由(manual / system_cancel 用;ai 為 None)
    matched_department: "Department | None"   # 命中沿用的既有部門(ai / provision 用)
    matched_user: "User | None"               # email 命中唯一一筆時的既有使用者(provision 沿用)
async def route(db: AsyncSession, req: ApiKeyRequest) -> RouteResult

# services/api_key_request_agent.py
@dataclass
class AgentDecision:
    confidence: int          # 0-100
    reason: str
    error: str | None = None
async def validate_fields(client: OpenRouterClient, req: ApiKeyRequest, matched_department: Department) -> AgentDecision

# services/api_key_request_provision.py
@dataclass
class ProvisionResult:
    ok: bool
    error: str | None = None
    matched_department_uid: UUID | None = None
    created_project_uid: UUID | None = None
    created_user_uid: UUID | None = None
    created_sdk_key_uid: UUID | None = None
    provisioned_secrets: dict | None = None   # {"sdk_key": str|None, "user_token": str, "project_code": str}
async def provision(db: AsyncSession, req: ApiKeyRequest, route: RouteResult, *, actor) -> ProvisionResult
`

// ════════════════════════════ Phase 1:後端基礎 ════════════════════════════
phase('後端基礎')

const p1 = await parallel([
  // 1a. DB 層:migration 0013 + model 欄位
  () => agent(`你是後端 DB 代理。實作 v1.9.1 的資料模型異動。

先讀:
- 契約 ${TASKS}(重點:「資料模型異動」「DB / Migration」「狀態模型」章節)
- ${BE}/alembic/versions/0012_api_key_requests.py(風格範本)
- ${BE}/app/models/api_key_request.py(要擴充的 model)

工作:
1) 新增 ${BE}/alembic/versions/0013_api_key_requests_lifecycle.py:
   - revision="0013_api_key_requests_lifecycle";down_revision="0012_api_key_requests"。
   - upgrade():ALTER TABLE api_key_requests 新增以下可空欄位:
     cancel_reason(Text)、cancel_source(String(8))、handled_by_user_uid(pg.UUID)、agent_decision(pg.JSONB)、
     error_message(Text)、created_project_uid(pg.UUID)、created_user_uid(pg.UUID)、created_sdk_key_uid(pg.UUID)、
     matched_department_uid(pg.UUID)、provisioned_secrets(pg.JSONB)、processed_at(DateTime(timezone=True))。
   - 既有資料:op.execute("UPDATE api_key_requests SET status='manual_pending' WHERE status='pending'")。
   - downgrade():把 manual_pending 還原為 pending(UPDATE),再逐一 drop 上述新增欄位(其餘狀態略過)。
   - import 與風格對齊 0012(from sqlalchemy.dialects import postgresql as pg;JSONB 用 pg.JSONB)。
2) 擴充 ${BE}/app/models/api_key_request.py:對應新增上述欄位為 Mapped[...](全部 nullable=True),
   JSONB 用 from sqlalchemy.dialects.postgresql import JSONB;DateTime 用 sqlalchemy DateTime(timezone=True)。
   更新檔頭 status 註解(列出 v1.9.1 五種狀態)。

${CONV}

完成後回傳:改動檔案清單 + 新增欄位清單 + 任何疑慮。`, { label: 'db-layer', phase: '後端基礎' }),

  // 1b. config + .env.example
  () => agent(`你是後端設定代理。

先讀 ${BE}/app/core/config.py 與 ${BE}/.env.example。

工作:
1) config.py:在 OpenRouter / Internal LLM 區塊附近新增設定
   API_KEY_AGENT_MODEL: str = "anthropic/claude-sonnet-4.6"(加一行繁中註解說明用途:申請單 AI 欄位驗證模型)。
2) .env.example:新增 API_KEY_AGENT_MODEL=anthropic/claude-sonnet-4.6;
   並確認 DEFAULT_OPENROUTER_KEY 已列(若無則補上,附註解:留空時 AI 驗證一律降級人工)。

只動這兩個檔。${CONV}

回傳:改動內容摘要。`, { label: 'config', phase: '後端基礎' }),

  // 1c. schema
  () => agent(`你是後端 Schema 代理。擴充 ${BE}/app/schemas/api_key_request.py。

先讀該檔(保留既有 ApiKeyRequestCreateRequest 與其 project_url 驗證器,不要動)。

依契約 ${TASKS}(「後端 — Schema / Repository」「資料模型異動」「API 端點」)新增/擴充:
1) ApiKeyRequestResponse:加欄位 cancel_reason: str|None、cancel_source: str|None、error_message: str|None、processed_at: datetime|None(皆 default None)。保留既有欄位。
2) 新增 AgentDecisionSchema(BaseModel):confidence: int、reason: str、error: str|None=None。
3) 新增 ProvisionedSecrets(BaseModel):sdk_key: str|None=None、user_token: str|None=None、project_code: str|None=None。
4) 新增 CancelRequest(BaseModel):reason: str = Field(min_length=1)(必填,缺則 422)。
5) 新增 ApiKeyRequestDetailResponse(BaseModel, from_attributes):含 ApiKeyRequestResponse 全部欄位
   + agent_decision: dict|None=None + provisioned_secrets: dict|None=None
   + created_project_uid/created_user_uid/created_sdk_key_uid/matched_department_uid/handled_by_user_uid: UUID|None=None。
   (agent_decision / provisioned_secrets 用 dict|None 直接吃 JSONB 內容即可。)

${CONV}

回傳:新增的 class 與欄位清單。`, { label: 'schema', phase: '後端基礎' }),

  // 1d. repositories
  () => agent(`你是後端 Repository 代理。新增以下方法,風格對齊各檔既有方法。

先讀:${BE}/app/repositories/user.py、project.py、sdk_api_key.py、api_key_request.py。

1) ${BE}/app/repositories/user.py:
   ⚠️ 既有 get_by_email 回單筆(SSO 用,**不要改**)。新增 list_by_email(self, email: str) -> list[User]:
   func.lower(User.email)==email.lower() 且 is_deleted.is_(False),回 .scalars().all() 的 list。
2) ${BE}/app/repositories/project.py:新增
   get_active_by_department_and_name(self, department_uid: UUID, name: str) -> Project | None:
   department_uid 相符、func.lower(Project.name)==name.lower()、is_active.is_(True)、is_deleted.is_(False),回 scalar_one_or_none()。
3) ${BE}/app/repositories/sdk_api_key.py:新增
   get_active_by_department(self, department_uid: UUID) -> SdkApiKey | None:
   department_uid 相符、is_active.is_(True)、is_deleted.is_(False),order_by(pid.desc()),回第一筆(.scalars().first())。
4) ${BE}/app/repositories/api_key_request.py:新增
   async def update_fields(self, row: ApiKeyRequest, **fields) -> None:逐一 setattr 後 await self.db.flush()(對齊其他 repo 的 update_fields)。

${CONV}

回傳:每個檔新增的方法簽名。`, { label: 'repos', phase: '後端基礎' }),
])

log(`Phase1 完成:${p1.filter(Boolean).length}/4 代理`)

// ════════════════════════════ Phase 2:後端服務 ════════════════════════════
phase('後端服務')

const p2 = await parallel([
  // 2a. router
  () => agent(`你是後端代理,新增 ${BE}/app/services/api_key_request_router.py。

先讀:契約 ${TASKS}(「規則路由」「狀態模型」章節)、${BE}/app/repositories/department.py、project.py、user.py、${BE}/app/models/api_key_request.py。

實作確定性規則路由,**不呼叫 AI、不寫 DB**。依下列決策樹(順序重要,硬規則先擋):
\`\`\`
dept = DepartmentRepository.get_by_code(req.department_code)
if dept is None:                                   -> manual,  reason="新部門需後台建立 OpenRouter Key"
elif dept.name.strip() != req.department_name.strip():  -> manual, reason="部門代號與名稱不符,請人工確認"
else:
  proj = ProjectRepository.get_active_by_department_and_name(dept.department_uid, req.project_name)
  users = UserRepository.list_by_email(req.owner_email)
  if proj is None:                                 -> ai,  matched_department=dept, matched_user=(users[0] if len(users)==1 else None)
  elif len(users) > 1:                             -> manual, reason="負責人 Email 命中多筆使用者,歧義需人工確認"
  elif len(users) == 0:                            -> manual, reason="既有專案下的新使用者需人工確認"
  else:                                            -> system_cancel, reason="過去已存在相同 Key 資料"
\`\`\`
注意:email 多筆/新使用者的硬規則只在「專案已存在」分支內判斷;「新專案」分支一律走 ai(matched_user 命中唯一才帶)。
回傳 RouteResult dataclass。

${IFACE}
${CONV}

回傳:檔案路徑 + route() 最終簽名 + 決策對應。`, { label: 'svc-router', phase: '後端服務' }),

  // 2b. agent (AI)
  () => agent(`你是後端代理,新增 ${BE}/app/services/api_key_request_agent.py。

先讀:契約 ${TASKS}(「AI 欄位驗證」「錯誤處理對照」)、${BE}/app/clients/openrouter/client.py、${BE}/app/clients/openrouter/errors.py、${BE}/app/core/config.py。

實作 AI 欄位驗證(只驗證、不寫 DB、不過白名單、不寫 usage_logs):
- validate_fields(client, req, matched_department) -> AgentDecision。
- 先檢查 settings.DEFAULT_OPENROUTER_KEY(get_settings()):為空 -> 直接回 AgentDecision(confidence=0, reason="", error="DEFAULT_OPENROUTER_KEY 未設定")。
- 組 payload:model = settings.API_KEY_AGENT_MODEL;messages 為 system + user;
  要求模型只輸出 JSON {"confidence": <0-100 int>, "reason": "<簡短中文>"};可設 payload["response_format"]={"type":"json_object"}。
- system prompt(繁中):說明任務 = 判斷 API Key 申請欄位是否正確/合理,重點 project_url 是否像有效且與 project_name 相符的 GitHub/Replit 連結、owner_email 網域是否合理、department_name/code 是否相稱、是否疑似亂填;**不要實際連線**,只做合理性判斷;只回 JSON。
- user content:帶申請 6 欄(department_name/code、project_name、project_url、owner_name、owner_email)+ 命中部門摘要(matched_department.name / .code)。
- 呼叫 await client.chat_completion(payload, api_key=settings.DEFAULT_OPENROUTER_KEY)。
- 解析 resp["choices"][0]["message"]["content"];去除可能的 \\\`\\\`\\\`json 圍欄後 json.loads;confidence 轉 int 並 clamp 0-100;reason 取字串。
- 任一例外(含 OpenRouterError、KeyError、JSON 解析失敗、逾時)-> AgentDecision(confidence=0, reason="", error=str(exc)[:300]);用 logger 記 exception。
- logger:from app.core.logging import get_logger。

${IFACE}
${CONV}

回傳:檔案路徑 + validate_fields 簽名 + payload/解析重點。`, { label: 'svc-agent', phase: '後端服務' }),

  // 2c. provision
  () => agent(`你是後端代理,新增 ${BE}/app/services/api_key_request_provision.py。

先讀:契約 ${TASKS}(「自動開通」章節)、${BE}/app/services/sdk_key.py、${BE}/app/services/user_token.py、
${BE}/app/api/v1/projects.py、users.py(建立 project/user 的欄位範本)、
${BE}/app/repositories/{project,user,sdk_api_key}.py、${BE}/app/core/audit.py。

實作確定性自動開通 provision(db, req, route, *, actor) -> ProvisionResult。**只 flush 不 commit**(commit 由端點負責),
失敗時 raise(讓端點以 savepoint rollback);或自行捕捉後回 ProvisionResult(ok=False, error=...)。採後者:內部用 try,失敗回 ok=False(端點再決定 rollback)。

步驟(全在傳入的 db session 內,依序 flush):
1) 部門:沿用 route.matched_department(必非 None)。matched_department_uid = dept.department_uid。
2) 專案:建立 Project(project_uid=UUID(str(uuid7())), department_uid=dept.uid, code=generate_id_str(), name=req.project_name, description=None);repo.add;flush。寫 write_audit(action="create_project", target_type="project", target_uid=project.project_uid, actor_user_uid=actor.user_uid, actor_role=actor.role)。created_project_uid 記下。
3) 使用者:route.matched_user 命中 -> 沿用該 user;否則建立新 User(account 用隨機合成 f"usr_{secrets.token_hex(12)}";password_hash = hash_password(secrets.token_urlsafe(32));role="user";username=req.owner_name;department_uid=dept.uid;email=req.owner_email)。
   - hash_password:from app.core.security import hash_password(若為同步函式直接呼叫即可)。
   - 新建才寫 write_audit(action="create_user", target_type="user", target_uid=user.user_uid,...)。created_user_uid 記下(沿用也記)。
4) SDK Key:sdk = SdkApiKeyRepository.get_active_by_department(dept.uid)。
   - 有 -> 沿用;plaintext = reveal_sdk_key(sdk)(可能 None)。
   - 無 -> (sdk, plaintext) = await create_sdk_key(db, department_uid=dept.uid, name=f"{req.project_name} 申請金鑰");寫 write_audit(action="create_sdk_key", target_type="sdk_api_key", target_uid=sdk.sdk_api_key_uid,...)。
   created_sdk_key_uid 記下。
5) User Token:沿用既有 user 時先 await revoke_tokens(db, user_uid=user.user_uid, reason="api_key_request_reissue")(重發撤舊);
   再 (token, issued_at) = await generate_token(db, user_uid=user.user_uid)。
6) provisioned_secrets = {"sdk_key": plaintext, "user_token": token, "project_code": project.code}。
回 ProvisionResult(ok=True, ...全部 uid... , provisioned_secrets=...)。
任一步例外 -> logger.exception 後回 ProvisionResult(ok=False, error=str(exc)[:300])。

${IFACE}
${CONV}

回傳:檔案路徑 + provision 簽名 + 各步驟沿用/新建邏輯。`, { label: 'svc-provision', phase: '後端服務' }),
])

log(`Phase2 完成:${p2.filter(Boolean).length}/3 服務`)

// ════════════════════════════ Phase 3:後端端點 ════════════════════════════
phase('後端端點')

const p3 = await agent(`你是後端 API 代理。重寫 ${BE}/app/api/v1/api_key_requests.py,實作 v1.9.1 全部端點與送出編排。

先讀:現行 ${BE}/app/api/v1/api_key_requests.py、契約 ${TASKS}(「API 端點」「錯誤處理對照」「權限與稽核」「狀態模型」)、
${BE}/app/api/v1/user_tokens.py(get_openrouter_client 注入請參考 ${BE}/app/api/v1/models.py:243 的 Depends 用法)、
以及本階段新增的服務:${BE}/app/services/api_key_request_router.py、api_key_request_agent.py、api_key_request_provision.py(讀它們確認簽名)。

保留既有 GET ""(列表)與 import 結構。POST "" 改寫為同步編排,並新增其餘端點:

POST ""(本人):
  1) 建 ApiKeyRequest row(status 先給 "manual_pending" 佔位),applicant_user_uid=actor.user_uid;repo.add;flush。
  2) route = await router.route(db, row)。
  3) decision 分流:
     - "system_cancel":row.status="cancelled";cancel_source="system";cancel_reason=route.reason;processed_at=now。
     - "manual":row.status="manual_pending";若 route.reason 存在寫入 error_message? 不,manual 的理由放哪?→ 存 agent_decision 不適用;
       將 route.reason 一併存入 error_message 供前端顯示(亦可)。matched_department_uid 若有則記。
     - "ai":
        client 由 Depends(get_openrouter_client) 注入端點函式參數;decision_ai = await agent.validate_fields(client, row, route.matched_department)。
        row.agent_decision = {"confidence": decision_ai.confidence, "reason": decision_ai.reason} (有 error 也一併放 error 欄)。
        if decision_ai.error: row.error_message = decision_ai.error。
        if decision_ai.confidence >= 95:
           用 savepoint 隔離開通:try: async with db.begin_nested(): pr = await provision.provision(db, row, route, actor=actor)
              若 pr.ok=False -> raise 以觸發 savepoint rollback。
           except: row.status="manual_pending";row.error_message = (pr.error or str(exc));(savepoint 已回滾開通寫入)。
           成功:row.status="agent_done";寫回 pr 的各 uid 欄、provisioned_secrets、processed_at;
                 並 write_audit(action="auto_provision_api_key_request", target_type="api_key_request", target_uid=row.request_uid)。
        else: row.status="manual_pending"(降級)。
  4) 一律 write_audit(action="create_api_key_request",...);await db.commit()。
  5) 回 success_response(data=ApiKeyRequestDetailResponse.model_validate(row).model_dump(mode="json"))
     —— agent_done 時帶回 provisioned_secrets。

POST "/{uid}/cancel"(本人;body: CancelRequest):非本人且非 admin→403;非 manual_pending→409;
  否則 status="cancelled"、cancel_source="user"、cancel_reason=body.reason、processed_at=now;write_audit(action="cancel_api_key_request")。

POST "/{uid}/revoke"(本人或 admin):非本人且非 admin→403;非 manual_pending→409(已處理禁止撤銷);
  否則 status="revoked"、processed_at=now;write_audit(action="revoke_api_key_request")。

POST "/{uid}/process"(admin):限 manual_pending(否則 409);route = await router.route(db, row)。
  若 route.matched_department 為 None(新部門)→ 仍允許 admin 開通?契約:admin 確定性開通→done。
  但新部門無既有 dept,provision 需 dept。處理:若 route.decision 仍是 "manual" 且為新部門(matched_department None),
  回 AppError("manual_provision_requires_department", code=409)並提示需先於後台建立部門/Key;
  否則(matched_department 存在)直接呼叫 provision.provision(db, row, route, actor=actor)(以 savepoint),
  成功:status="done"、handled_by_user_uid=actor.user_uid、寫回 uid 欄 + provisioned_secrets + processed_at;
  write_audit(action="process_api_key_request")。失敗回 409 + error_message。

GET "/{uid}"(本人或 admin):非本人且非 admin→403;回 ApiKeyRequestDetailResponse。

POST "/{uid}/claim-secrets"(本人):非本人→403;回目前 provisioned_secrets(可能 None→提示),
  然後 update row.provisioned_secrets=None;write_audit(action="claim_api_key_request_secrets" 或沿用既有命名 — 用 "claim_secrets_api_key_request")。commit。

通用:
- 取單筆用 ApiKeyRequestRepository.get_by_uid;None→AppError("not_found", 404)。
- now:from datetime import UTC, datetime; datetime.now(tz=UTC)。
- 「本人」判定:row.applicant_user_uid == actor.user_uid。
- 所有寫入端點最後 await db.commit()。

${CONV}

完成後請執行 \`cd ${BE} && python -c "import app.main"\`(或 ruff)確認可 import,把結果一併回報。
回傳:新增端點清單 + 送出編排重點 + import/語法檢查結果。`, { label: 'endpoint', phase: '後端端點' })

log('Phase3 端點完成')

// ════════════════════════════ Phase 4:前端 ════════════════════════════
phase('前端')

const feTypes = await agent(`你是前端代理。更新 ${FE}/src/types/api.ts 與 ${FE}/src/lib/api/endpoints.ts。

先讀這兩個檔。

1) types/api.ts:擴充 interface ApiKeyRequest 加 cancel_reason?: string|null、cancel_source?: string|null、error_message?: string|null、processed_at?: string|null;
   status 維持 string。新增:
   - interface AgentDecision { confidence: number; reason: string; error?: string | null }
   - interface ProvisionedSecrets { sdk_key?: string | null; user_token?: string | null; project_code?: string | null }
   - interface ApiKeyRequestDetail extends ApiKeyRequest { agent_decision?: AgentDecision | null; provisioned_secrets?: ProvisionedSecrets | null; created_project_uid?: string|null; created_user_uid?: string|null; created_sdk_key_uid?: string|null; matched_department_uid?: string|null; handled_by_user_uid?: string|null }
2) endpoints.ts:在 apiKeyRequests 常數附近新增:
   apiKeyRequestById: (uid: string) => \`/api/v1/api-key-requests/\${uid}\`,
   cancelApiKeyRequest: (uid: string) => \`/api/v1/api-key-requests/\${uid}/cancel\`,
   revokeApiKeyRequest: (uid: string) => \`/api/v1/api-key-requests/\${uid}/revoke\`,
   processApiKeyRequest: (uid: string) => \`/api/v1/api-key-requests/\${uid}/process\`,
   claimApiKeyRequestSecrets: (uid: string) => \`/api/v1/api-key-requests/\${uid}/claim-secrets\`,

只動這兩檔。回應/註解繁體中文。回傳:新增的型別與 endpoint 鍵。`, { label: 'fe-types', phase: '前端' })

const fePage = await agent(`你是前端代理。改寫 ${FE}/src/app/(main)/api-key-requests/page.tsx,實作 v1.9.1 列表狀態與操作。

先讀:現行 page.tsx、剛更新的 ${FE}/src/types/api.ts、${FE}/src/lib/api/endpoints.ts、契約 ${TASKS}(「前端」章節)。
參考既有元件用法(同檔已 import:Badge、LoadingButton、useDialog/showDialog、useToast、apiClient/ApiError、Table 等)。

實作(沿用既有風格與既有元件,勿引入新依賴):
1) 狀態 badge 對應函式:manual_pending→variant="warning" 文字「待人工處理」;agent_done→"success"「Agent 已處理」;done→"success"「已處理」;
   revoked→"secondary"「已撤銷」;cancelled→"secondary"「已取消」。取代現行寫死的「待審核」badge。
2) 送出(onSubmit)維持 loading;成功後若回應 status==="agent_done" 且有 provisioned_secrets → 彈一次性憑證視窗
   (用 showDialog 顯示 sdk_key / user_token / project_code;sdk_key 為 null 時提示「請向管理員索取」)。仍重新 load 列表。
   POST 回應型別改用 ApiKeyRequestDetail。
3) 列操作欄(新增一欄「操作」):
   - 本人(it.applicant_user_uid === 目前使用者 uid;從 useAppSelector(s=>s.auth.actor) 取 user uid):
     manual_pending → 顯示「取消」(彈窗填原因,呼叫 cancelApiKeyRequest)與「撤銷」(二次確認,呼叫 revokeApiKeyRequest)。
     agent_done/done → 顯示「領取憑證」(呼叫 claimApiKeyRequestSecrets,成功彈一次性憑證視窗;已領取/空則提示)。
   - admin 且 manual_pending → 顯示「人工處理」:先 GET apiKeyRequestById 取 detail 顯示 agent_decision(信心分數/理由),確認後呼叫 processApiKeyRequest,成功彈憑證視窗。
4) 所有 API 呼叫以 try/catch 包覆,錯誤用 showDialog({type:"error", message: err.localizedDetail})(err instanceof ApiError)。
   操作成功後 toast + 重新 load。
5) 取消原因輸入可用簡單 prompt 式 Dialog;若專案已有可複用的輸入型 Dialog 元件則沿用,否則用既有 showDialog + 受控 state 實作最小可用版本(不要新建大型元件檔)。

保持 TypeScript 嚴格、無 any 濫用。回應/註解繁體中文。

完成後執行 \`cd ${FE} && npx tsc --noEmit\`(或 npm run typecheck 若存在)確認型別通過,回報結果(若有錯誤請修正後再回報)。
回傳:改動摘要 + tsc 結果。`, { label: 'fe-page', phase: '前端' })

log('Phase4 前端完成')

// ════════════════════════════ Phase 5:文件 ════════════════════════════
phase('文件')

const p5 = await parallel([
  () => agent(`你是文件代理。更新使用者指南 ${FE}/src/app/(main)/user-guide/page.tsx。

先讀該檔了解現有結構/元件用法,**沿用相同排版風格**新增一個段落:「申請後的狀態與領取憑證」(申請人視角)。
內容要點(繁中,精簡):送出後可能結果 = 系統自動開通(Agent 已處理,於詳情/列表「領取憑證」一次性取得 SDK Key / User Token / 專案代碼,僅顯示一次)、
待人工處理(管理員會審核;可在處理前自行「取消」並填原因,或「撤銷」)、已取消/已撤銷的意義、重複申請會被系統自動取消。
不要改其他段落。回傳:新增段落摘要。`, { label: 'doc-user', phase: '文件' }),

  () => agent(`你是文件代理。更新管理員指南 ${FE}/src/app/(main)/admin-guide/page.tsx。

先讀該檔了解現有結構/元件用法,**沿用相同排版風格**新增一個段落:「API Key 申請:待人工處理的審核與新部門開通」。
內容要點(繁中,精簡):待人工處理清單的來源(新部門 / AI 信心 < 95 / AI 失敗 / 既有專案下新使用者 / 部門代號名稱不符 / Email 歧義)、
人工處理流程(檢視 AI 信心分數與理由 → 一鍵開通成 done)、新部門案需先到 OpenRouter 後台建立 Key 後再開通、
已處理(agent_done/done)不可撤銷。不要改其他段落。回傳:新增段落摘要。`, { label: 'doc-admin', phase: '文件' }),
])

log(`Phase5 文件完成:${p5.filter(Boolean).length}/2`)

// ════════════════════════════ Phase 6:驗證 ════════════════════════════
phase('驗證')

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ok', 'summary', 'issues'],
  properties: {
    ok: { type: 'boolean', description: '是否全部通過(無阻斷性錯誤)' },
    summary: { type: 'string' },
    issues: { type: 'array', items: { type: 'string' }, description: '發現的問題(檔案:行 + 描述)' },
  },
}

const verify = await parallel([
  () => agent(`你是後端驗證代理。在 ${BE} 執行:
1) python -c "import app.main"(確認所有新檔可 import、無語法/簽名錯誤)。
2) 若有 ruff:ruff check app/(只看本次相關檔)。
回報實際輸出。若有錯誤,**直接修正**(對齊既有慣例)後重跑直到通過。
最後對照契約 ${TASKS} 的「Definition of Done — 後端」逐項核對是否齊備。`, { label: 'verify-be', phase: '驗證', schema: VERIFY_SCHEMA }),

  () => agent(`你是前端驗證代理。在 ${FE} 執行 npx tsc --noEmit(或 package.json 內的 typecheck script)。
回報輸出。若有型別錯誤**直接修正**後重跑直到通過。
對照契約 ${TASKS} 的「前端」DoD 逐項核對。`, { label: 'verify-fe', phase: '驗證', schema: VERIFY_SCHEMA }),
])

return {
  phase1: p1.map((r, i) => ({ agent: ['db', 'config', 'schema', 'repos'][i], ok: !!r })),
  phase2: p2.map((r, i) => ({ agent: ['router', 'agent', 'provision'][i], ok: !!r })),
  endpoint: !!p3,
  frontend: { types: !!feTypes, page: !!fePage },
  docs: p5.map(Boolean),
  verify: verify.filter(Boolean),
}

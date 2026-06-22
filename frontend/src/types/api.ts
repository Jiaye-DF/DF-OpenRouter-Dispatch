// 統一 API 回應型別，對齊後端 20-backend.md § 1

export interface ApiResponse<T = unknown> {
  success: boolean;
  code: number;
  data: T | null;
  detail: string;
}

// 登入成功後 /auth/me 回傳的 Actor
export interface Actor {
  user_uid: string;
  account: string;
  username: string;
  role: "admin" | "user";
  department_uid: string | null;
  email: string | null;
}

// 分頁結果通用型別
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

// API Key 申請單(v1.9)
export interface ApiKeyRequest {
  request_uid: string;
  applicant_user_uid: string;
  department_name: string;
  department_code: string;
  project_name: string;
  project_url: string;
  owner_name: string;
  owner_email: string;
  status: string;
  created_at: string;
  // v1.9.1 取消 / 錯誤 / 處理時間
  cancel_reason?: string | null;
  cancel_source?: string | null;
  error_message?: string | null;
  processed_at?: string | null;
  // v1.9.2 開通完成 Email 通知:寄送成功時間 / 失敗原因
  notified_at?: string | null;
  notify_error?: string | null;
}

// v1.9.1 AI 欄位驗證代理決策
export interface AgentDecision {
  confidence: number;
  reason: string;
  error?: string | null;
}

// v1.9.1 自動開通產生的祕密(僅領取時回傳)
export interface ProvisionedSecrets {
  sdk_key?: string | null;
  user_token?: string | null;
  project_code?: string | null;
}

// v1.9.1 申請單詳情(含代理決策與開通結果關聯)
export interface ApiKeyRequestDetail extends ApiKeyRequest {
  agent_decision?: AgentDecision | null;
  provisioned_secrets?: ProvisionedSecrets | null;
  created_project_uid?: string | null;
  created_user_uid?: string | null;
  created_sdk_key_uid?: string | null;
  matched_department_uid?: string | null;
  handled_by_user_uid?: string | null;
}

// v1.9.2 重送開通通知結果(admin)
export interface ResendNotifyResult {
  request_uid: string;
  notified_at?: string | null;
  notify_error?: string | null;
}

// API Key 申請表單送出內容(6 欄全必填)
export interface ApiKeyRequestCreate {
  department_name: string;
  department_code: string;
  project_name: string;
  project_url: string;
  owner_name: string;
  owner_email: string;
}

// 部門
export interface Department {
  department_uid: string;
  code: string; // 成本中心代碼
  org_code: string | null; // 組織代碼
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 申請表單『專案負責人』下拉選項(名稱 + 信箱,選取後自動帶入信箱)
export interface OwnerOption {
  username: string;
  email: string;
}

// 專案
export interface Project {
  project_uid: string;
  department_uid: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 使用者（管理端列表使用）
export interface User {
  user_uid: string;
  account: string;
  username: string;
  role: "admin" | "user";
  department_uid: string | null;
  email: string | null;
  employee_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// OpenRouter Key（只顯示 last4 + prefix）
export interface OpenRouterKey {
  openrouter_key_uid: string;
  department_uid: string;
  name: string;
  key_prefix: string;
  key_last4: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // v1.1 新增餘額欄位（僅 admin 可見;後端非 admin 不會回填）
  credits_used_usd?: string | null;
  credits_limit_usd?: string | null; // NULL 代表無上限
  credits_is_free_tier?: boolean | null;
  credits_synced_at?: string | null; // ISO 字串
  // v1.2 速率限制(per-Key;0 = 不限)
  rpm_limit: number;
  min_request_interval_ms: number;
}

// Internal Key (v1.2;全平台共用,無 department)
export interface InternalKey {
  internal_key_uid: string;
  name: string;
  base_url: string;
  has_api_key: boolean;
  key_last4: string | null;
  rpm_limit: number;
  min_request_interval_ms: number;
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

// SDK Key
export interface SdkKey {
  sdk_api_key_uid: string;
  department_uid: string;
  name: string;
  key_prefix: string;
  // 完整 key 明文(v1.5+ 建立才有;舊資料為 null → admin 可在 DB 直接補)
  key_values: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 用量紀錄(列表精簡視圖 — 不含 request_content / response_summary)
export interface UsageLog {
  usage_log_uid: string;
  user_uid: string | null;
  department_uid: string;
  project_uid: string | null;
  openrouter_key_uid: string | null;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: string;
  latency_ms: number;
  status: "success" | "error";
  error_code: string | null;
  used_tools: boolean;
  openrouter_generation_id: string | null;
  created_at: string;
}

// 用量紀錄請求快照(寫入時的使用者原始輸入)
export interface UsageRequestContent {
  model?: string;
  text?: string | null;
  images?: string[];
  // 上傳檔案僅保留檔名(不留存檔案內容,法務考量)
  files?: string[];
  tools?: Record<string, unknown>[];
}

// 用量紀錄回應摘要(v1.6.2 起 output_text 為完整回覆;舊紀錄僅有截斷的 first_text)
export interface UsageResponseSummary {
  output_text?: string;
  first_text?: string;
  usage?: Record<string, unknown>;
}

// 用量紀錄單筆詳情(列表欄位 + 完整 Input / Output)
export interface UsageLogDetail extends UsageLog {
  request_content: UsageRequestContent | null;
  response_summary: UsageResponseSummary | null;
}

// 儀錶板彙總
export interface StatsOverview {
  total_requests: number;
  total_tokens: number;
  total_cost_usd: string;
}

export interface StatsByDepartment {
  department_uid: string;
  department_code: string | null;
  department_name: string;
  total_tokens: number;
  total_cost_usd: string;
  total_requests: number;
}

export interface StatsByModel {
  model: string;
  department_uid?: string;
  department_name?: string;
  total_tokens: number;
  total_cost_usd: string;
  total_requests: number;
  prompt_tokens?: number;
  completion_tokens?: number;
}

// v1.5 新增 — 依專案 / 使用者彙總
export interface StatsByProject {
  project_uid: string;
  project_code: string;
  project_name: string;
  project_description: string | null; // 專案描述(Excel 匯出「備註」欄)
  total_requests: number;
  total_tokens: number;
  total_cost_usd: string;
}

export interface StatsByUser {
  user_uid: string | null;
  username: string | null;
  employee_id: string | null;
  total_requests: number;
  total_tokens: number;
  total_cost_usd: string;
}

// v1.5 新增 — 使用者下拉精簡欄位
export interface UserDropdownItem {
  user_uid: string;
  username: string;
  employee_id: string | null;
  department_uid: string | null;
}

export interface StatsTimeseriesPoint {
  bucket: string;
  total_requests: number;
  total_tokens: number;
  total_cost_usd: string;
}

// ─── v1.1 模型主檔 ──────────────────────────────────────────────

// 模型(對齊 backend ModelRead)
// Decimal 欄位以字串傳輸,避免 JS 浮點誤差
export interface Model {
  model_uid: string;
  provider: "openrouter" | "internal";
  model_key: string;
  name: string;
  description: string | null;

  context_length: number | null;
  max_completion_tokens: number | null;
  modality: string | null;
  // 模態 tag(v1.5):可輸入 / 可輸出之型別,例 ["text","image"]。
  // OpenRouter 模型由 sync 自動填入;internal 模型由 admin 自訂。
  input_modalities: string[];
  output_modalities: string[];
  tokenizer: string | null;

  price_prompt_per_token: string | null;
  price_completion_per_token: string | null;
  price_image_per_image: string | null;
  price_request_flat: string | null;

  is_moderated: boolean;
  tier_key: string | null;

  openrouter_created_at: string | null;
  last_synced_at: string;

  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelPatch {
  is_active?: boolean;
  tier_key?: string | null;
}

export interface ModelSyncResult {
  added: number;
  updated: number;
  deactivated: number;
  total: number;
  credits_synced: number;
  credits_failed: number;
  synced_at: string;
}

// 模型分級
export interface ModelTier {
  tier_uid: string;
  key: string;
  label_zh: string;
  label_en: string | null;
  color: string | null;
  sort_order: number;
  auto_match_min_price_per_mtok: string | null;
  auto_match_max_price_per_mtok: string | null;
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelTierCreate {
  key: string;
  label_zh: string;
  label_en?: string | null;
  color?: string | null;
  sort_order?: number;
  // 注意:後端以「USD/token」為單位儲存;前端輸入是 USD/M tokens,送出前須除以 1_000_000
  auto_match_min_price_per_mtok?: string | null;
  auto_match_max_price_per_mtok?: string | null;
}

export interface ModelTierPatch {
  label_zh?: string;
  label_en?: string | null;
  color?: string | null;
  sort_order?: number;
  auto_match_min_price_per_mtok?: string | null;
  auto_match_max_price_per_mtok?: string | null;
}

// Sync 白名單(v1.5)
export interface AllowedModel {
  allowed_model_uid: string;
  model_key: string;
  note: string | null;
  is_active: boolean;
}

// 結構化錯誤 data 酬載
export interface SyncThrottledData {
  retry_after_seconds: number;
}

export interface TierInUseData {
  using_models: string[];
}

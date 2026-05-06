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

// 部門
export interface Department {
  department_uid: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
}

// SDK Key
export interface SdkKey {
  sdk_api_key_uid: string;
  department_uid: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 用量紀錄
export interface UsageLog {
  usage_log_uid: string;
  user_uid: string | null;
  department_uid: string;
  openrouter_key_uid: string | null;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: string;
  latency_ms: number;
  status: "success" | "error";
  error_code: string | null;
  created_at: string;
}

// 儀錶板彙總
export interface StatsOverview {
  total_requests: number;
  total_tokens: number;
  total_cost_usd: string;
}

export interface StatsByDepartment {
  department_uid: string;
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
  openrouter_model_id: string;
  name: string;
  description: string | null;

  context_length: number | null;
  max_completion_tokens: number | null;
  modality: string | null;
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

// 結構化錯誤 data 酬載
export interface SyncThrottledData {
  retry_after_seconds: number;
}

export interface TierInUseData {
  using_models: string[];
}

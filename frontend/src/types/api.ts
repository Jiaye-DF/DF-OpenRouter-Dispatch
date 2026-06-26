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

// AI 分析 — 判別模型設定(v2.0)
// GET/PUT /ai-eval/judge-settings 回傳 list(未設定時為 []);slot 1→3 依序對應 3 個判別模型
export interface JudgeSetting {
  ai_judge_slot: number;
  model_uid: string;
  model_key: string;
  name: string;
  // 後端若回傳更新時間則用以顯示「目前設定更新時間」(未提供則不顯示)
  updated_at?: string | null;
}

// judge_model_not_active 的結構化 data:列出缺漏 / 非 active 的 uid
export interface JudgeModelNotActiveData {
  model_uids: string[];
}

// ─── v2.0.3 評審結果(usage-log 明細頁內嵌「AI 分析」)────────────────
// 對齊 propose-v2.0.3.md §4.2 對外 JSON 結構,後端 schema 來源:
// backend/app/schemas/ai_model_eval_result.py。
// 慣例:Decimal 欄位一律以字串傳輸(`string | null`),避免 JS 浮點誤差
// (沿用既有 Model「Decimal 以字串傳輸」),實際 Decimal→str 由後端 service 負責。

// 任務分析(父表 dim1/2,v2.0.1 已取首個成功評審值存為單一值)
export interface TaskAnalysis {
  summary: string; // 使用者輸入摘要(dim1)
  intent: string; // 任務意圖原始枚舉字串(如 code_generation);中文對照見 lib/ai-eval-labels.ts
  complexity: string; // 任務複雜度(low / medium / high)
}

// 推薦共識(三評審 ai_recommend_model 收斂;對齊 propose §5)
// 命名以 Eval 前綴避免與其他 RecommendConsensus 語意混淆
export interface EvalRecommendConsensus {
  model: string | null; // 多數推薦模型;分歧時為票數最高者;全 null → null
  tier: string | null; // 眾數模型對應 tier(同模型應一致);null 安全
  votes: number; // 眾數模型得票數
  is_split: boolean; // true=無嚴格過半共識(分歧)
}

// 本版計算的彙總(三評審 → 單一判決;對齊 propose §5)
export interface EvaluationSummary {
  judge_count: number; // 候選總數
  succeeded_count: number; // 其中評審成功(AI 欄位非 null)數,用於「部分成功」標示
  avg_fit_score: string | null; // 非 null fit 的平均(四捨五入 3 位);Decimal→string;全 null → null
  min_fit_score: string | null; // 非 null fit 極小值;Decimal→string
  max_fit_score: string | null; // 非 null fit 極大值;Decimal→string
  recommend_consensus: EvalRecommendConsensus;
  self_vote_count: number; // ai_self_vote=true 的候選數(自我偏好警示)
}

// 單一評審候選(子表 dim3/4,失敗裁判 AI 欄位為 null;對齊 propose §4.2)
export interface EvalCandidate {
  ai_candidate_uid: string;
  judge_model_uid: string;
  judge_model_key: string | null; // join models 補上;取不到時 null(前端顯示 UUID 尾碼)
  judge_model_name: string | null; // join models 補上;取不到時 null
  ai_recommend_model: string | null;
  ai_recommend_tier: string | null;
  ai_recommend_reason: string | null;
  ai_fit_score: string | null; // 吻合度;Decimal→string
  ai_self_vote: boolean | null; // 該裁判是否推薦自家廠商(偏差語意)
}

// 評審結果(父表 + 任務分析 + 彙總 + 三子候選;對齊 propose §4.2)
export interface EvaluationResult {
  ai_evaluation_uid: string;
  usage_log_uid: string;
  ai_original_model: string; // 被評審原文所用的原始模型 key
  status: "pending" | "evaluated" | "error"; // 評審狀態
  ai_evaluated_at: string | null; // 評審完成時間(ISO);未完成為 null
  task_analysis: TaskAnalysis | null; // 無成功評審值時為 null
  summary: EvaluationSummary | null; // 失敗 / 無候選時為 null
  candidates: EvalCandidate[]; // 三評審明細(最多 3 筆);v2.0.4 細看專頁重用
}

// 頂層 wrapper(對齊 propose §4.2 / 決議 #6)
// 無評審列時 evaluation 為 null(對應 200 + evaluation=null,非 404)
export interface EvaluationResultResponse {
  evaluation: EvaluationResult | null;
}

// ─── v2.1.0 AI 推薦模型「真實重跑 + 對比裁決」總覽(依用量紀錄分組;唯讀展示)──
// 對齊 propose-v2.1.0.md §5.4 / §6.1,後端 schema 來源:
// backend/app/schemas/ai_model_eval_rerun_result.py。
// 名詞(去黑話,對齊後端):
// - 原模型 = 使用者實際呼叫、寫進 usage_logs 的模型。
// - AI 推薦模型 = 評審推薦、且 ≠ 原模型的模型(DB 欄位仍叫 rerun_model)。
// - 對比裁決 = AI 比對「原模型輸出 vs 推薦模型輸出」何者較佳(compare_*)。
// 慣例:金額(cost_usd / original_cost_usd / cost_delta_usd)與信心分數(compare_score)
// 一律以字串傳輸(`string | null`)避免 JS 浮點誤差(沿用既有 Model / EvalCandidate)。

// 單一 AI 推薦模型的真實重跑 + 對比裁決(對應一筆 ai_model_eval_reruns;對齊 propose §5.4)
export interface RerunRecommendation {
  rerun_model: string; // AI 推薦模型 key(實際重跑)
  model_uid: string | null; // 推薦模型 models.model_uid(軟引用;取不到 null)
  output_text: string | null; // 推薦模型真實輸出原文(歷史未存 / 失敗列 → null)
  // 真實用量 / 成本(推薦模型真實 API 結果;失敗列可能為 null)
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  cost_usd: string | null; // 推薦模型真實成本(USD);Decimal→string
  cost_delta_usd: string | null; // 成本差 推薦模型 − 原;Decimal→string
  latency_ms: number | null; // 推薦模型延遲(毫秒)
  // 狀態
  status: string; // success / error
  error_code: string | null; // 錯誤碼;無錯誤為 null
  // 對比裁決(discriminator;子開關停用時整組為 null)
  compare_winner: string | null; // original / challenger / tie;中文對照見 lib/ai-eval-labels.ts
  compare_score: string | null; // 信心分數 0–1;Decimal→string
  compare_reason: string | null; // 裁決理由
  compare_judge_model: string | null; // 擔任裁決的模型 key(推薦該模型的評審本人)
  triggered_at: string; // 重跑執行時間(ISO)
}

// 一組 = 一筆用量紀錄(原模型 + 原模型真實輸出原文 + 原成本)+ 其下去重後的
// 1–N 個 AI 推薦模型(對齊 propose §5.4 / §6.1)
export interface RerunGroup {
  usage_log_uid: string; // 分組鍵(來源 usage_logs.usage_log_uid;連到明細頁)
  original_model: string; // 原模型 key(並排顯示)
  original_output_text: string | null; // 原模型真實輸出原文(歷史未存快照 → null)
  original_cost_usd: string | null; // 原呼叫成本(USD);Decimal→string
  evaluated_at: string | null; // 該組最新一筆推薦模型的重跑執行時間(ISO;無列 → null)
  recommendations: RerunRecommendation[]; // 去重後的 AI 推薦模型列(最新優先)
}

// 跨 log 裁決分布(頁頂輕量彙總;對齊 propose §6.1;計數針對當頁分組內所有推薦模型)
export interface RerunStats {
  total_recommendations: number; // 推薦模型總筆數
  keep_count: number; // compare_winner='original'(建議維持原模型)
  swap_count: number; // compare_winner='challenger'(建議改用推薦模型)
  tie_count: number; // compare_winner='tie'(平手)
  unjudged_count: number; // status='success' 但 compare_winner IS NULL(已重跑·未裁決)
  failed_count: number; // status != 'success'(重跑失敗)
}

// AI 判決總覽分頁 wrapper(對齊後端 RerunOverviewPage:items/total/page/size + stats)
// 無資料時 items 為空陣列 [](對應 200 + items=[],非 null / 非 404)
export interface RerunOverviewPage {
  items: RerunGroup[]; // 當頁分組(依用量紀錄,最新優先)
  total: number; // 分組後的總組數(distinct usage_log,非重跑列數)
  page: number; // 分頁參數回放
  size: number; // 分頁參數回放
  stats: RerunStats; // 當頁分組內推薦模型的裁決分布彙總
}

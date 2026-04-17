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

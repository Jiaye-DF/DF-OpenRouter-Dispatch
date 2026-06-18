// 後端錯誤碼 → 前端顯示文字
// 規則：不暴露欄位名 / 表名 / 內部識別；僅描述操作結果與建議下一步。

const MESSAGES: Record<string, string> = {
  // 認證 / 權限
  unauthorized: "登入已逾期或尚未登入，請重新登入。",
  forbidden: "權限不足，無法執行此操作。",
  invalid_credentials: "帳號或密碼錯誤。",
  account_locked: "帳號已暫時鎖定，請稍後再試。",
  account_taken: "此帳號已被使用。",
  refresh_reuse_detected: "登入憑證異常，請重新登入。",

  // 密碼 / 使用者
  weak_password: "密碼強度不足（至少 10 字元，含大小寫英數符中三類）。",
  password_reused: "新密碼不可與舊密碼相同。",
  user_no_department: "此使用者尚未指派部門，請先指派後再操作。",
  user_department_missing: "此使用者指派的部門不存在，請先修正。",
  user_requires_identity: "請輸入員工編號與 Email。",

  // 一般
  not_found: "找不到指定資源。",
  code_conflict: "代碼已被使用，請改用其他代碼。",
  invalid_input: "輸入內容有誤，請檢查後再送出。",

  // 部門 / 專案 / Key
  department_not_found: "部門不存在或已停用。",
  dept_has_active_keys: "部門下仍有啟用的 Key，無法刪除。",
  dept_has_active_projects: "部門下仍有啟用的專案,無法刪除。",

  // 模型 / OpenRouter
  model_forbidden: "此模型未在白名單內。",
  model_not_found: "此模型不存在。",
  model_key_duplicated: "模型 key 已存在,請更換。",
  tier_not_found: "指定的模型分級不存在。",
  feature_not_supported: "此功能目前不支援。",
  rate_limited: "請求過於頻繁,請稍後再試。",
  openrouter_unavailable: "OpenRouter 服務暫時不可用,請確認 OpenRouter Key 是否有正確加入。",

  // v1.2 本地模型
  internal_busy: "本地模型目前繁忙,排隊已超時,請稍後再試。",
  internal_unavailable: "本地模型服務暫時無法使用,請稍後再試。",
  provider_misconfigured: "本地模型設定未完成,請聯絡系統管理員。",
  provider_not_allowed: "此 provider 不允許手動建立,請改用同步流程。",

  // v1.5 專案維度
  project_code_required: "請於請求 header 帶入 X-Project-Code。",
  project_invalid: "X-Project-Code 不存在、已停用或與 SDK Key 部門不符。",

  // v1.9.2 開通完成 Email 通知
  secrets_already_claimed: "憑證已被領取並清空,無法再重送通知。",
  m365_not_configured: "M365 寄信尚未設定,無法寄送通知。",

  // 預設
  操作失敗: "操作失敗,請稍後再試。",
};

export function localizeError(detail: string): string {
  if (!detail) return "操作失敗";
  if (MESSAGES[detail]) return MESSAGES[detail];
  // 含「欄位 」前綴的驗證訊息直接保留（由 FastAPI 驗證器產生，欄位為 API 層級）
  if (detail.startsWith("欄位 ")) return detail;
  // 其他未知碼：回傳保守訊息,不洩漏細節
  return "操作失敗,請稍後再試。";
}

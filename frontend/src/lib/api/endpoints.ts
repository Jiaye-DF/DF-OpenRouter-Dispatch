// 所有後端 API endpoint 集中常數，禁止於他處硬編字串

export const API_ENDPOINTS = {
  // 認證
  login: "/api/v1/auth/login",
  refresh: "/api/v1/auth/refresh",
  logout: "/api/v1/auth/logout",
  me: "/api/v1/auth/me",
  // DF-SSO 登入入口（瀏覽器整頁導向,需搭配 NEXT_PUBLIC_API_BASE_URL 組成絕對網址）
  ssoLogin: "/api/v1/auth/sso/login",

  // 使用者（admin）
  users: "/api/v1/users",
  usersDropdown: "/api/v1/users/dropdown",
  // 申請表單『專案負責人』下拉(全使用者可用,含 Email)
  userOwnerOptions: "/api/v1/users/owner-options",
  userById: (uid: string) => `/api/v1/users/${uid}`,
  resetUserPassword: (uid: string) => `/api/v1/users/${uid}/password/reset`,
  userTokens: (uid: string) => `/api/v1/users/${uid}/tokens`,
  revokeUserTokens: (uid: string) => `/api/v1/users/${uid}/tokens/revoke`,

  // API Key 申請表單(v1.9,admin / member 皆可)
  apiKeyRequests: "/api/v1/api-key-requests",
  // v1.9.1 申請單詳情與狀態流轉
  apiKeyRequestById: (uid: string) => `/api/v1/api-key-requests/${uid}`,
  cancelApiKeyRequest: (uid: string) => `/api/v1/api-key-requests/${uid}/cancel`,
  revokeApiKeyRequest: (uid: string) => `/api/v1/api-key-requests/${uid}/revoke`,
  processApiKeyRequest: (uid: string) => `/api/v1/api-key-requests/${uid}/process`,
  claimApiKeyRequestSecrets: (uid: string) =>
    `/api/v1/api-key-requests/${uid}/claim-secrets`,
  // v1.9.2 admin 重送開通完成 Email 通知
  resendApiKeyRequestNotify: (uid: string) =>
    `/api/v1/api-key-requests/${uid}/resend-notify`,

  // 組織
  departments: "/api/v1/departments",
  departmentById: (uid: string) => `/api/v1/departments/${uid}`,
  projects: "/api/v1/projects",
  projectById: (uid: string) => `/api/v1/projects/${uid}`,

  // OpenRouter Keys
  openrouterKeys: "/api/v1/openrouter-keys",
  openrouterKeyById: (uid: string) => `/api/v1/openrouter-keys/${uid}`,

  // Internal Keys (v1.2)
  internalKeys: "/api/v1/internal-keys",
  internalKeyById: (uid: string) => `/api/v1/internal-keys/${uid}`,

  // SDK Keys
  sdkKeys: "/api/v1/sdk-keys",
  sdkKeyById: (uid: string) => `/api/v1/sdk-keys/${uid}`,

  // 用量 / 統計
  usageLogs: "/api/v1/usage-logs",
  usageLogById: (uid: string) => `/api/v1/usage-logs/${uid}`,
  statsOverview: "/api/v1/stats/overview",
  statsByDepartment: "/api/v1/stats/by-department",
  statsByModel: "/api/v1/stats/by-model",
  statsByProject: "/api/v1/stats/by-project",
  statsByUser: "/api/v1/stats/by-user",
  statsTimeseries: "/api/v1/stats/timeseries",

  // 模型主檔(v1.1)
  models: "/api/v1/models",
  modelById: (uid: string) => `/api/v1/models/${uid}`,
  syncModels: "/api/v1/models/sync",
  bulkActivateModels: "/api/v1/models/bulk-activate",

  // 模型分級(v1.1)
  modelTiers: "/api/v1/model-tiers",
  modelTierById: (uid: string) => `/api/v1/model-tiers/${uid}`,

  // Sync 白名單(v1.5)
  allowedModels: "/api/v1/allowed-models",
  allowedModelById: (uid: string) => `/api/v1/allowed-models/${uid}`,

  // AI 分析 — 判別模型設定(v2.0)
  aiEvalJudgeSettings: "/api/v1/ai-eval/judge-settings",
  // AI 分析 — 依 usage_log 取評審結果(v2.0.3,對齊 propose §4.1;admin 限定)
  aiEvaluationByUsageLog: (uid: string) =>
    `/api/v1/ai-eval/evaluations/by-usage-log/${uid}`,
  // AI 分析 — 依 usage_log 取 challenger 重跑 + 對比裁決(v2.1.0,對齊 propose §5.4;admin 限定)
  aiRerunsByUsageLog: (uid: string) =>
    `/api/v1/ai-eval/reruns/by-usage-log/${uid}`,
  // AI 分析 — 跨 log AI 判決總覽(分頁;admin 限定)
  aiRerunsOverview: "/api/v1/ai-eval/reruns",
} as const;

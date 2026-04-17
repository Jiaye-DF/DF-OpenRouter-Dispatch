// 所有後端 API endpoint 集中常數，禁止於他處硬編字串

export const API_ENDPOINTS = {
  // 認證
  login: "/api/v1/auth/login",
  refresh: "/api/v1/auth/refresh",
  logout: "/api/v1/auth/logout",
  me: "/api/v1/auth/me",
  changePassword: "/api/v1/auth/password",

  // 使用者（admin）
  users: "/api/v1/users",
  userById: (uid: string) => `/api/v1/users/${uid}`,
  resetUserPassword: (uid: string) => `/api/v1/users/${uid}/password/reset`,
  userTokens: (uid: string) => `/api/v1/users/${uid}/tokens`,
  revokeUserTokens: (uid: string) => `/api/v1/users/${uid}/tokens/revoke`,

  // 組織
  departments: "/api/v1/departments",
  departmentById: (uid: string) => `/api/v1/departments/${uid}`,
  projects: "/api/v1/projects",
  projectById: (uid: string) => `/api/v1/projects/${uid}`,

  // OpenRouter Keys
  openrouterKeys: "/api/v1/openrouter-keys",
  openrouterKeyById: (uid: string) => `/api/v1/openrouter-keys/${uid}`,

  // SDK Keys
  sdkKeys: "/api/v1/sdk-keys",
  sdkKeyById: (uid: string) => `/api/v1/sdk-keys/${uid}`,

  // 用量 / 統計
  usageLogs: "/api/v1/usage-logs",
  usageLogById: (uid: string) => `/api/v1/usage-logs/${uid}`,
  statsOverview: "/api/v1/stats/overview",
  statsByDepartment: "/api/v1/stats/by-department",
  statsByModel: "/api/v1/stats/by-model",
  statsTimeseries: "/api/v1/stats/timeseries",
} as const;

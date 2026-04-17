import { createApi } from "@reduxjs/toolkit/query/react";
import type { BaseQueryFn } from "@reduxjs/toolkit/query";
import { ApiError, apiClient } from "@/lib/api/client";

// RTK Query baseQuery：透過 apiClient 送出，將 ApiError 正規化為 { error }
interface BaseQueryArgs {
  url: string;
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
}

const baseQuery: BaseQueryFn<BaseQueryArgs, unknown, ApiError> = async (args) => {
  try {
    const method = args.method ?? "GET";
    let data: unknown;
    if (method === "GET") {
      data = await apiClient.get(args.url, { query: args.query });
    } else if (method === "POST") {
      data = await apiClient.post(args.url, args.body, { query: args.query });
    } else if (method === "PATCH") {
      data = await apiClient.patch(args.url, args.body, { query: args.query });
    } else if (method === "PUT") {
      data = await apiClient.put(args.url, args.body, { query: args.query });
    } else {
      data = await apiClient.delete(args.url, { query: args.query });
    }
    return { data };
  } catch (err) {
    if (err instanceof ApiError) return { error: err };
    return {
      error: new ApiError(500, 500, (err as Error)?.message ?? "unknown_error"),
    };
  }
};

export const api = createApi({
  reducerPath: "api",
  baseQuery,
  tagTypes: [
    "Me",
    "User",
    "Department",
    "Project",
    "OpenRouterKey",
    "SdkKey",
    "UsageLog",
    "Stats",
  ],
  endpoints: () => ({}),
});

"use client";

import { Provider } from "react-redux";
import { store } from "./index";

// 將 Redux store 注入 App Router；layout.tsx 於 client wrapper 中使用
export function ReduxProvider({ children }: { children: React.ReactNode }) {
  return <Provider store={store}>{children}</Provider>;
}

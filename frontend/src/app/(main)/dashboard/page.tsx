"use client";

import * as React from "react";
import { PageTitle } from "@/components/common/PageTitle";
import { KpiCards } from "@/components/feature/stats/KpiCards";
import { DeptTokensBar } from "@/components/feature/stats/DeptTokensBar";
import { ModelTokensStacked } from "@/components/feature/stats/ModelTokensStacked";
import { DailyTimeseriesLine } from "@/components/feature/stats/DailyTimeseriesLine";
import { apiClient } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type {
  StatsByDepartment,
  StatsByModel,
  StatsOverview,
  StatsTimeseriesPoint,
} from "@/types/api";

// 儀錶板首頁：3 張 KPI + 部門長條 + 模型堆疊柱 + 時序折線
export default function DashboardPage() {
  const [overview, setOverview] = React.useState<StatsOverview>();
  const [byDept, setByDept] = React.useState<StatsByDepartment[]>();
  const [byModel, setByModel] = React.useState<StatsByModel[]>();
  const [timeseries, setTimeseries] = React.useState<StatsTimeseriesPoint[]>();
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      // 分別以 Promise.allSettled 併發取得，任一失敗不影響其他區塊
      const [ov, dept, model, ts] = await Promise.allSettled([
        apiClient.get<StatsOverview>(API_ENDPOINTS.statsOverview),
        apiClient.get<StatsByDepartment[]>(API_ENDPOINTS.statsByDepartment),
        apiClient.get<StatsByModel[]>(API_ENDPOINTS.statsByModel),
        apiClient.get<StatsTimeseriesPoint[]>(API_ENDPOINTS.statsTimeseries, {
          query: { granularity: "day" },
        }),
      ]);
      if (cancelled) return;
      if (ov.status === "fulfilled") setOverview(ov.value);
      if (dept.status === "fulfilled") setByDept(dept.value);
      if (model.status === "fulfilled") setByModel(model.value);
      if (ts.status === "fulfilled") setTimeseries(ts.value);
      setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageTitle
        title="儀錶板"
        description="檢視本月份平台整體用量、部門與模型分布"
      />
      <div className="flex flex-col gap-6">
        <KpiCards data={overview} loading={loading} />
        <div className="grid gap-6 lg:grid-cols-2">
          <DeptTokensBar data={byDept} />
          <ModelTokensStacked data={byModel} />
        </div>
        <DailyTimeseriesLine data={timeseries} />
      </div>
    </>
  );
}

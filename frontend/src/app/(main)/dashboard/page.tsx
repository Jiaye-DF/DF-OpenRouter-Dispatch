"use client";

import * as React from "react";
import { Download } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { Button } from "@/components/ui/button";
import { KpiCards } from "@/components/feature/stats/KpiCards";
import { DeptTokensBar } from "@/components/feature/stats/DeptTokensBar";
import { ModelTokensStacked } from "@/components/feature/stats/ModelTokensStacked";
import { DailyTimeseriesLine } from "@/components/feature/stats/DailyTimeseriesLine";
import { ByProjectBar } from "@/components/feature/stats/ByProjectBar";
import { ByUserBar } from "@/components/feature/stats/ByUserBar";
import {
  DashboardFilters,
  type DashboardFilterValue,
} from "@/components/feature/stats/DashboardFilters";
import { apiClient } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { useAppSelector } from "@/store/hooks";
import type {
  StatsByDepartment,
  StatsByModel,
  StatsByProject,
  StatsByUser,
  StatsOverview,
  StatsTimeseriesPoint,
} from "@/types/api";

// 本地時區(瀏覽器=台北)的 YYYY-MM-DD
function localYmd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// 預設日期區間:當月 1 號 ~ 今天
function defaultRange(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return { from: localYmd(first), to: localYmd(now) };
}

// 儀錶板首頁(v1.5 / v1.6):
// - 頂部篩選(部門 / 專案 / 使用者 / 日期區間),admin 可任選、non-admin 鎖在自己部門
// - 日期區間預設當月,起訖以台北日界送至後端(+08:00),所有彙總共用同一範圍
// - KPI / 各維度長條 / 時序折線 / Excel 匯出皆套用相同篩選
export default function DashboardPage() {
  const actor = useAppSelector((s) => s.auth.actor);
  const isAdmin = actor?.role === "admin";
  const actorDeptUid = actor?.department_uid ?? null;

  const [filters, setFilters] = React.useState<DashboardFilterValue>(() => {
    const r = defaultRange();
    return {
      department_uid: "",
      project_uid: "",
      user_uid: "",
      from: r.from,
      to: r.to,
    };
  });

  const [overview, setOverview] = React.useState<StatsOverview>();
  const [byDept, setByDept] = React.useState<StatsByDepartment[]>();
  const [byModel, setByModel] = React.useState<StatsByModel[]>();
  const [byProject, setByProject] = React.useState<StatsByProject[]>();
  const [byUser, setByUser] = React.useState<StatsByUser[]>();
  const [timeseries, setTimeseries] = React.useState<StatsTimeseriesPoint[]>();
  const [granularity, setGranularity] = React.useState<"day" | "hour">("day");
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const query: Record<string, string> = {};
      if (filters.department_uid) query.department_uid = filters.department_uid;
      if (filters.project_uid) query.project_uid = filters.project_uid;
      if (filters.user_uid) query.user_uid = filters.user_uid;
      // 以台北日界(+08:00)送出:起始含當日 00:00:00、結束含當日 23:59:59
      if (filters.from) query.from = `${filters.from}T00:00:00+08:00`;
      if (filters.to) query.to = `${filters.to}T23:59:59+08:00`;

      const [ov, dept, model, project, user, ts] = await Promise.allSettled([
        apiClient.get<StatsOverview>(API_ENDPOINTS.statsOverview, { query }),
        apiClient.get<StatsByDepartment[]>(API_ENDPOINTS.statsByDepartment, {
          query,
        }),
        apiClient.get<StatsByModel[]>(API_ENDPOINTS.statsByModel, { query }),
        apiClient.get<StatsByProject[]>(API_ENDPOINTS.statsByProject, {
          query,
        }),
        apiClient.get<StatsByUser[]>(API_ENDPOINTS.statsByUser, { query }),
        apiClient.get<StatsTimeseriesPoint[]>(API_ENDPOINTS.statsTimeseries, {
          query: { ...query, granularity },
        }),
      ]);
      if (cancelled) return;
      if (ov.status === "fulfilled") setOverview(ov.value);
      if (dept.status === "fulfilled") setByDept(dept.value);
      if (model.status === "fulfilled") setByModel(model.value);
      if (project.status === "fulfilled") setByProject(project.value);
      if (user.status === "fulfilled") setByUser(user.value);
      if (ts.status === "fulfilled") setTimeseries(ts.value);
      setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [filters, granularity]);

  const hasAnyData =
    (byDept?.length ?? 0) +
      (byProject?.length ?? 0) +
      (byUser?.length ?? 0) >
    0;

  const [exporting, setExporting] = React.useState(false);
  const onDownloadExcel = async () => {
    setExporting(true);
    try {
      const { exportDashboardToExcel } = await import("@/lib/export/excel");
      // 檔名帶篩選的日期區間(資料本身已是該區間彙總結果)
      const range =
        filters.from && filters.to
          ? `${filters.from}_${filters.to}`
          : localYmd(new Date());
      exportDashboardToExcel(
        { byDept, byProject, byUser },
        `dashboard_${range}.xlsx`,
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <PageTitle
        title="儀錶板"
        description="檢視指定期間平台成本與用量;可依日期、部門、專案、使用者篩選"
        actions={
          <Button
            variant="outline"
            onClick={onDownloadExcel}
            disabled={loading || exporting || !hasAnyData}
            title={
              !hasAnyData
                ? "尚無資料可下載"
                : "下載 Excel(含部門 / 專案 / 使用者三個 sheet)"
            }
          >
            <Download className="h-4 w-4" />
            {exporting ? "產生中…" : "下載 Excel"}
          </Button>
        }
      />
      <div className="flex flex-col gap-6">
        <DashboardFilters
          value={filters}
          onChange={setFilters}
          isAdmin={isAdmin}
          actorDeptUid={actorDeptUid}
        />
        <KpiCards data={overview} loading={loading} />
        <DeptTokensBar data={byDept} />
        <ModelTokensStacked data={byModel} />
        <ByProjectBar data={byProject} />
        <ByUserBar data={byUser} />
        <DailyTimeseriesLine
          data={timeseries}
          granularity={granularity}
          onGranularityChange={setGranularity}
        />
      </div>
    </>
  );
}

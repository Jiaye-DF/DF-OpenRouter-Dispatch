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

// 儀錶板首頁(v1.5):
// - 頂部三層篩選(部門 / 專案 / 使用者),admin 可任選、non-admin 鎖在自己部門
// - KPI / 各維度長條 / 時序折線皆套用相同篩選
export default function DashboardPage() {
  const actor = useAppSelector((s) => s.auth.actor);
  const isAdmin = actor?.role === "admin";
  const actorDeptUid = actor?.department_uid ?? null;

  const [filters, setFilters] = React.useState<DashboardFilterValue>({
    department_uid: "",
    project_uid: "",
    user_uid: "",
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
      const today = new Date().toISOString().slice(0, 10);
      exportDashboardToExcel(
        { byDept, byProject, byUser },
        `dashboard_${today}.xlsx`,
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <PageTitle
        title="儀錶板"
        description="檢視本月份平台整體成本與用量;可依部門、專案、使用者篩選"
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
        <div className="grid gap-6 lg:grid-cols-2">
          <DeptTokensBar data={byDept} />
          <ModelTokensStacked data={byModel} />
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <ByProjectBar data={byProject} />
          <ByUserBar data={byUser} />
        </div>
        <DailyTimeseriesLine
          data={timeseries}
          granularity={granularity}
          onGranularityChange={setGranularity}
        />
      </div>
    </>
  );
}

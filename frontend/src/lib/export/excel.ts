import * as XLSX from "xlsx";
import { toUSDNumber } from "@/lib/utils/format";
import type {
  StatsByDepartment,
  StatsByModel,
  StatsByProject,
  StatsByProjectModel,
  StatsByUser,
  StatsOverview,
  StatsTimeseriesPoint,
} from "@/types/api";

// 6 位小數的 Excel 數字格式(USD 統一規則)
const USD_FORMAT = "$0.000000";

// 時序桶為後端以 Asia/Taipei 切出的 naive wall-clock 字串(UTC+8),
// 直接以字串切片格式化,禁丟 new Date() 二次偏移(對齊 02-frontend/04-datetime.md)。
function formatBucketTaipei(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/);
  return m ? `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}:${m[6]}` : iso;
}

interface SheetSpec {
  name: string;
  header: string[];
  rows: (string | number)[][];
  // 需要套用 USD 格式的欄位 0-based index;對該欄每個 cell 設 `z` 為 USD_FORMAT。
  usdColumns: number[];
}

function buildSheet(spec: SheetSpec): XLSX.WorkSheet {
  const ws = XLSX.utils.aoa_to_sheet([spec.header, ...spec.rows]);
  // 第一列(header)後從 row 1 開始套 USD 格式
  for (let r = 0; r < spec.rows.length; r++) {
    for (const c of spec.usdColumns) {
      const addr = XLSX.utils.encode_cell({ r: r + 1, c });
      const cell = ws[addr];
      if (cell) cell.z = USD_FORMAT;
    }
  }
  // 欄寬自動估算
  const widths = spec.header.map((h, c) => {
    const max = Math.max(
      h.length,
      ...spec.rows.map((r) => String(r[c] ?? "").length),
    );
    return { wch: Math.min(Math.max(max + 2, 10), 40) };
  });
  ws["!cols"] = widths;
  return ws;
}

interface DashboardExportInput {
  overview?: StatsOverview;
  byDept?: StatsByDepartment[];
  byProject?: StatsByProject[];
  byProjectModel?: StatsByProjectModel[];
  byModel?: StatsByModel[];
  byUser?: StatsByUser[];
  timeseries?: StatsTimeseriesPoint[];
}

/**
 * 將儀錶板全維度匯出為單一 xlsx 檔。
 * sheet 順序:總覽 → 部門 → 專案 → 專案×模型 → 依模型 → 使用者 → 時序。
 * 既有三 sheet(部門 / 專案 / 使用者)欄位不動。
 */
export function exportDashboardToExcel(
  data: DashboardExportInput,
  fileName: string,
): void {
  const wb = XLSX.utils.book_new();

  // 總覽(KPI):兩欄 指標 / 值,僅成本列套 USD 格式
  const overviewSpec: SheetSpec = {
    name: "總覽",
    header: ["指標", "值"],
    rows: [
      ["總請求數", data.overview?.total_requests ?? 0],
      ["總 Tokens", data.overview?.total_tokens ?? 0],
      ["總成本 (USD)", toUSDNumber(data.overview?.total_cost_usd)],
    ],
    // buildSheet 的 usdColumns 會套整欄;此處值欄混雜請求數 / Tokens,故留空,成本列另手動套。
    usdColumns: [],
  };
  const overviewWs = buildSheet(overviewSpec);
  // 僅「總成本 (USD)」列(header 後第 3 列 → r=3)的值欄(c=1)套 USD 格式
  const overviewCostAddr = XLSX.utils.encode_cell({ r: 3, c: 1 });
  if (overviewWs[overviewCostAddr]) overviewWs[overviewCostAddr].z = USD_FORMAT;

  const deptSpec: SheetSpec = {
    name: "部門",
    header: ["成本中心代碼", "部門名稱", "請求數", "Tokens", "成本 (USD)"],
    rows: (data.byDept ?? []).map((d) => [
      d.department_code ?? "",
      d.department_name,
      d.total_requests,
      d.total_tokens,
      toUSDNumber(d.total_cost_usd),
    ]),
    usdColumns: [4],
  };

  const projectSpec: SheetSpec = {
    name: "專案",
    header: ["專案代碼", "專案名稱", "備註", "請求數", "Tokens", "成本 (USD)"],
    rows: (data.byProject ?? []).map((p) => [
      p.project_code,
      p.project_name,
      p.project_description ?? "",
      p.total_requests,
      p.total_tokens,
      toUSDNumber(p.total_cost_usd),
    ]),
    usdColumns: [5],
  };

  // 專案×模型明細:每專案再依模型拆解花費
  const projectModelSpec: SheetSpec = {
    name: "專案×模型",
    header: ["專案代碼", "專案名稱", "模型", "請求數", "Tokens", "成本 (USD)"],
    rows: (data.byProjectModel ?? []).map((pm) => [
      pm.project_code,
      pm.project_name,
      pm.model,
      pm.total_requests,
      pm.total_tokens,
      toUSDNumber(pm.total_cost_usd),
    ]),
    usdColumns: [5],
  };

  // 依模型:含 Prompt / Completion Tokens 拆分
  const modelSpec: SheetSpec = {
    name: "依模型",
    header: [
      "模型",
      "請求數",
      "Prompt Tokens",
      "Completion Tokens",
      "Tokens",
      "成本 (USD)",
    ],
    rows: (data.byModel ?? []).map((m) => [
      m.model,
      m.total_requests,
      m.prompt_tokens ?? 0,
      m.completion_tokens ?? 0,
      m.total_tokens,
      toUSDNumber(m.total_cost_usd),
    ]),
    usdColumns: [5],
  };

  const userSpec: SheetSpec = {
    name: "使用者",
    header: ["員工編號", "姓名", "請求數", "Tokens", "成本 (USD)"],
    rows: (data.byUser ?? []).map((u) => [
      u.employee_id ?? "",
      u.username ?? "(未知)",
      u.total_requests,
      u.total_tokens,
      toUSDNumber(u.total_cost_usd),
    ]),
    usdColumns: [4],
  };

  // 時序:時間桶為 UTC+8 wall-clock 字串
  const timeseriesSpec: SheetSpec = {
    name: "時序",
    header: ["時間 (UTC+8)", "請求數", "Tokens", "成本 (USD)"],
    rows: (data.timeseries ?? []).map((t) => [
      formatBucketTaipei(t.bucket),
      t.total_requests,
      t.total_tokens,
      toUSDNumber(t.total_cost_usd),
    ]),
    usdColumns: [3],
  };

  // 追加順序:總覽 → 部門 → 專案 → 專案×模型 → 依模型 → 使用者 → 時序
  XLSX.utils.book_append_sheet(wb, overviewWs, overviewSpec.name);
  XLSX.utils.book_append_sheet(wb, buildSheet(deptSpec), deptSpec.name);
  XLSX.utils.book_append_sheet(wb, buildSheet(projectSpec), projectSpec.name);
  XLSX.utils.book_append_sheet(
    wb,
    buildSheet(projectModelSpec),
    projectModelSpec.name,
  );
  XLSX.utils.book_append_sheet(wb, buildSheet(modelSpec), modelSpec.name);
  XLSX.utils.book_append_sheet(wb, buildSheet(userSpec), userSpec.name);
  XLSX.utils.book_append_sheet(
    wb,
    buildSheet(timeseriesSpec),
    timeseriesSpec.name,
  );

  XLSX.writeFile(wb, fileName);
}

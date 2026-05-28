import * as XLSX from "xlsx";
import { toUSDNumber } from "@/lib/utils/format";
import type {
  StatsByDepartment,
  StatsByProject,
  StatsByUser,
} from "@/types/api";

// 6 位小數的 Excel 數字格式(USD 統一規則)
const USD_FORMAT = "$0.000000";

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
  byDept?: StatsByDepartment[];
  byProject?: StatsByProject[];
  byUser?: StatsByUser[];
}

/** 將儀錶板三維度匯出為單一 xlsx 檔(部門 / 專案 / 使用者 sheet)。 */
export function exportDashboardToExcel(
  data: DashboardExportInput,
  fileName: string,
): void {
  const wb = XLSX.utils.book_new();

  const deptSpec: SheetSpec = {
    name: "部門",
    header: ["部門代碼", "部門名稱", "請求數", "Tokens", "成本 (USD)"],
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
    header: ["專案代碼", "專案名稱", "請求數", "Tokens", "成本 (USD)"],
    rows: (data.byProject ?? []).map((p) => [
      p.project_code,
      p.project_name,
      p.total_requests,
      p.total_tokens,
      toUSDNumber(p.total_cost_usd),
    ]),
    usdColumns: [4],
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

  XLSX.utils.book_append_sheet(wb, buildSheet(deptSpec), deptSpec.name);
  XLSX.utils.book_append_sheet(wb, buildSheet(projectSpec), projectSpec.name);
  XLSX.utils.book_append_sheet(wb, buildSheet(userSpec), userSpec.name);

  XLSX.writeFile(wb, fileName);
}

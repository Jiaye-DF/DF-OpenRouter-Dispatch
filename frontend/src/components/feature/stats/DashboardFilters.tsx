"use client";

import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type {
  Department,
  Paginated,
  Project,
  UserDropdownItem,
} from "@/types/api";

const SELECT_CLASS =
  "h-10 w-full rounded-xl border border-border bg-background px-3 text-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 " +
  "hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-60";

export interface DashboardFilterValue {
  department_uid: string;
  project_uid: string;
  user_uid: string;
}

interface Props {
  value: DashboardFilterValue;
  onChange: (next: DashboardFilterValue) => void;
  isAdmin: boolean;
  actorDeptUid: string | null;
}

// 儀表板頂部三層篩選列(v1.5)
// - admin:三個下拉皆可用,部門可選「全部」
// - non-admin:部門固定為自己,藏起下拉只顯示 badge
// - 選了部門後,專案 / 使用者下拉自動限縮到該部門範圍
export function DashboardFilters({
  value,
  onChange,
  isAdmin,
  actorDeptUid,
}: Props) {
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [users, setUsers] = React.useState<UserDropdownItem[]>([]);

  // 部門清單(admin 才需要;non-admin 只看自己,不打)
  React.useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await apiClient.get<Paginated<Department>>(
          API_ENDPOINTS.departments,
          { query: { page: 1, size: 200 } }
        );
        if (!cancelled) setDepts(res.items);
      } catch {
        /* 忽略 — 下拉空即可 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  // 專案 / 使用者下拉(隨選定的部門變動)
  const filterDept = isAdmin ? value.department_uid : actorDeptUid ?? "";
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const query: Record<string, string | number> = { page: 1, size: 200 };
        if (filterDept) query.department_uid = filterDept;
        const [proj, usr] = await Promise.allSettled([
          apiClient.get<Paginated<Project>>(API_ENDPOINTS.projects, { query }),
          apiClient.get<UserDropdownItem[]>(API_ENDPOINTS.usersDropdown, {
            query: filterDept ? { department_uid: filterDept } : undefined,
          }),
        ]);
        if (cancelled) return;
        if (proj.status === "fulfilled") setProjects(proj.value.items);
        if (usr.status === "fulfilled") setUsers(usr.value);
      } catch {
        /* 忽略 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filterDept]);

  const onDeptChange = (next: string) => {
    // 切部門:同時把專案 / 使用者重設(避免殘留跨部門 ID)
    onChange({ department_uid: next, project_uid: "", user_uid: "" });
  };

  const currentDeptName =
    depts.find((d) => d.department_uid === actorDeptUid)?.name ?? "(未指派)";

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="grid gap-4 md:grid-cols-3">
          {/* 部門 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-muted-foreground">部門</label>
            {isAdmin ? (
              <select
                className={SELECT_CLASS}
                value={value.department_uid}
                onChange={(e) => onDeptChange(e.target.value)}
              >
                <option value="">全部部門</option>
                {depts.map((d) => (
                  <option key={d.department_uid} value={d.department_uid}>
                    {d.name}({d.code})
                  </option>
                ))}
              </select>
            ) : (
              <div className="h-10 flex items-center">
                <Badge variant="secondary">{currentDeptName}</Badge>
                <span className="ml-2 text-sm text-muted-foreground">
                  (僅 admin 可跨部門檢視)
                </span>
              </div>
            )}
          </div>

          {/* 專案 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-muted-foreground">專案</label>
            <select
              className={SELECT_CLASS}
              value={value.project_uid}
              onChange={(e) =>
                onChange({ ...value, project_uid: e.target.value })
              }
            >
              <option value="">全部專案</option>
              {projects.map((p) => (
                <option key={p.project_uid} value={p.project_uid}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* 使用者 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-muted-foreground">使用者</label>
            <select
              className={SELECT_CLASS}
              value={value.user_uid}
              onChange={(e) =>
                onChange({ ...value, user_uid: e.target.value })
              }
            >
              <option value="">全部使用者</option>
              {users.map((u) => (
                <option key={u.user_uid} value={u.user_uid}>
                  {u.username}
                  {u.employee_id ? `(${u.employee_id})` : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

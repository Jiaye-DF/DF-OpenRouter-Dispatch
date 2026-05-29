"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/EmptyState";
import { RankingTable } from "@/components/feature/stats/RankingTable";
import { formatUSD, toUSDNumber } from "@/lib/utils/format";
import type { StatsByDepartment } from "@/types/api";

interface Props {
  data?: StatsByDepartment[];
}

// 部門 × 總成本長條圖 + 排行表;Y 軸金額,tooltip 帶 tokens / requests 細節。
export function DeptTokensBar({ data }: Props) {
  const items = (data ?? []).map((d) => ({
    name: d.department_name,
    cost: toUSDNumber(d.total_cost_usd),
    tokens: d.total_tokens,
    requests: d.total_requests,
  }));
  const tableItems = items.map((d) => ({
    name: d.name,
    requests: d.requests,
    cost: d.cost,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>部門成本 (USD)</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState title="尚無用量資料" />
        ) : (
          <>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={items}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v) => formatUSD(v, 2)}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgb(var(--color-card))",
                    border: "1px solid rgb(var(--color-border))",
                    borderRadius: 12,
                  }}
                  formatter={(_v, _n, p) => {
                    const row = p?.payload as
                      | { cost: number; tokens: number; requests: number }
                      | undefined;
                    if (!row) return null;
                    return [
                      `${formatUSD(row.cost)} · ${row.tokens.toLocaleString()} tokens · ${row.requests.toLocaleString()} 次`,
                      "用量",
                    ];
                  }}
                />
                <Bar
                  dataKey="cost"
                  fill="rgb(var(--color-primary))"
                  radius={[6, 6, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
            <RankingTable items={tableItems} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

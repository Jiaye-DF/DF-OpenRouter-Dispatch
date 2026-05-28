"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/EmptyState";
import { RankingTable } from "@/components/feature/stats/RankingTable";
import type { StatsByModel } from "@/types/api";

interface Props {
  data?: StatsByModel[];
}

// 模型 × 總 tokens 堆疊柱狀 + 排行表;若資料僅單層(無 department 分組)則退化為單條柱
export function ModelTokensStacked({ data }: Props) {
  const grouped = new Map<string, Record<string, number | string>>();
  const deptSet = new Set<string>();

  for (const row of data ?? []) {
    const key = row.model;
    const dept = row.department_name ?? "總計";
    deptSet.add(dept);
    const entry = grouped.get(key) ?? { model: key };
    entry[dept] = ((entry[dept] as number) ?? 0) + row.total_tokens;
    grouped.set(key, entry);
  }
  const chartData = Array.from(grouped.values());
  const depts = Array.from(deptSet);

  // 排行表:依模型彙總(跨部門加總)
  const modelTotals = new Map<string, { requests: number; tokens: number }>();
  for (const row of data ?? []) {
    const prev = modelTotals.get(row.model) ?? { requests: 0, tokens: 0 };
    modelTotals.set(row.model, {
      requests: prev.requests + row.total_requests,
      tokens: prev.tokens + row.total_tokens,
    });
  }
  const tableItems = Array.from(modelTotals.entries()).map(([name, v]) => ({
    name,
    requests: v.requests,
    tokens: v.tokens,
  }));

  // 色盤:以主色與輔色為基底循環
  const palette = [
    "rgb(var(--color-primary))",
    "rgb(var(--color-accent))",
    "#f59e0b",
    "#10b981",
    "#ef4444",
    "#8b5cf6",
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>總模型用量 (Tokens)</CardTitle>
      </CardHeader>
      <CardContent>
        {chartData.length === 0 ? (
          <EmptyState title="尚無模型資料" />
        ) : (
          <>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="model" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "rgb(var(--color-card))",
                    border: "1px solid rgb(var(--color-border))",
                    borderRadius: 12,
                  }}
                />
                <Legend />
                {depts.map((d, idx) => (
                  <Bar
                    key={d}
                    dataKey={d}
                    stackId="tokens"
                    fill={palette[idx % palette.length]}
                    radius={idx === depts.length - 1 ? [6, 6, 0, 0] : [0, 0, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
            <RankingTable items={tableItems} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

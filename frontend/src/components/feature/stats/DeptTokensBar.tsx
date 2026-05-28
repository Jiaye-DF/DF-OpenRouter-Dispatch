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
import type { StatsByDepartment } from "@/types/api";

interface Props {
  data?: StatsByDepartment[];
}

// 部門 × 總 tokens 長條圖 + 排行表
export function DeptTokensBar({ data }: Props) {
  const items = (data ?? []).map((d) => ({
    name: d.department_name,
    tokens: d.total_tokens,
  }));
  const tableItems = (data ?? []).map((d) => ({
    name: d.department_name,
    requests: d.total_requests,
    tokens: d.total_tokens,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>部門用量(Tokens)</CardTitle>
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
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "rgb(var(--color-card))",
                    border: "1px solid rgb(var(--color-border))",
                    borderRadius: 12,
                  }}
                />
                <Bar
                  dataKey="tokens"
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

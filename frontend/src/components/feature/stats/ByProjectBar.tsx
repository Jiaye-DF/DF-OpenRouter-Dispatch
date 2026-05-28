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
import type { StatsByProject } from "@/types/api";

interface Props {
  data?: StatsByProject[];
}

// 專案 × 總 tokens 長條圖 + 排行表(v1.5);歷史無 project 的紀錄不會出現於此
export function ByProjectBar({ data }: Props) {
  const items = (data ?? []).map((d) => ({
    name: d.project_name,
    tokens: d.total_tokens,
  }));
  const tableItems = (data ?? []).map((d) => ({
    name: d.project_name,
    requests: d.total_requests,
    tokens: d.total_tokens,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>專案用量(Tokens)</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState title="尚無專案用量資料" description="代理呼叫須帶 X-Project-Code 才會出現在此" />
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

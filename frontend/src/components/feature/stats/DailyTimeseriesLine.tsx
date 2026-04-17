"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/EmptyState";
import type { StatsTimeseriesPoint } from "@/types/api";

interface Props {
  data?: StatsTimeseriesPoint[];
}

// 日 / 時用量折線圖：total_tokens 為主軸
export function DailyTimeseriesLine({ data }: Props) {
  const items = (data ?? []).map((d) => ({
    bucket: d.bucket,
    tokens: d.total_tokens,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>用量時序</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState title="尚無時序資料" />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={items}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  background: "rgb(var(--color-card))",
                  border: "1px solid rgb(var(--color-border))",
                  borderRadius: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="tokens"
                stroke="rgb(var(--color-primary))"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import * as React from "react";
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
import { FilterChip } from "@/components/ui/FilterChip";
import { formatUSD, toUSDNumber } from "@/lib/utils/format";
import type { StatsTimeseriesPoint } from "@/types/api";

type Granularity = "day" | "hour";

interface Props {
  data?: StatsTimeseriesPoint[];
  granularity: Granularity;
  onGranularityChange: (g: Granularity) => void;
}

// 用量時序折線圖(v1.6):
// - bucket 由後端 Postgres 以 Asia/Taipei 切桶(UTC+8),收到的是 naive timestamp 字串
// - day 模式:tick 只顯示 M/D
// - hour 模式:00 點 tick 顯示 M/D 00:00,其他 hour 只顯示 HH:00(避免 X 軸文字疊)
//
// 直接以字串切片解析,不丟給 new Date() — 避免瀏覽器時區把已是台北時間的 naive 字串再偏移一次。
interface ParsedBucket {
  raw: string;
  year: number;
  month: number;
  day: number;
  hour: number;
}

function parseBucket(s: string): ParsedBucket | null {
  // 支援 "2026-05-29T08:00:00" / "2026-05-29 08:00:00" / 帶毫秒;只取到 hour
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):/);
  if (!m) return null;
  return {
    raw: s,
    year: Number(m[1]),
    month: Number(m[2]),
    day: Number(m[3]),
    hour: Number(m[4]),
  };
}

function formatTick(p: ParsedBucket, granularity: Granularity): string {
  if (granularity === "day") {
    return `${p.month}/${p.day}`;
  }
  // hour:00 點才印日期
  if (p.hour === 0) {
    return `${p.month}/${p.day} 00:00`;
  }
  return `${String(p.hour).padStart(2, "0")}:00`;
}

function formatTooltipLabel(p: ParsedBucket, granularity: Granularity): string {
  const datePart = `${p.year}/${String(p.month).padStart(2, "0")}/${String(p.day).padStart(2, "0")}`;
  if (granularity === "day") return datePart;
  return `${datePart} ${String(p.hour).padStart(2, "0")}:00`;
}

export function DailyTimeseriesLine({
  data,
  granularity,
  onGranularityChange,
}: Props) {
  const items = React.useMemo(
    () =>
      (data ?? [])
        .map((d) => {
          const parsed = parseBucket(d.bucket);
          return parsed
            ? {
                bucket: d.bucket,
                parsed,
                cost: toUSDNumber(d.total_cost_usd),
                tokens: d.total_tokens,
              }
            : null;
        })
        .filter(<T,>(x: T | null): x is T => x !== null),
    [data]
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle>成本時序 (USD,UTC+8)</CardTitle>
        <div className="flex items-center gap-2">
          <FilterChip
            active={granularity === "day"}
            onClick={() => onGranularityChange("day")}
          >
            日
          </FilterChip>
          <FilterChip
            active={granularity === "hour"}
            onClick={() => onGranularityChange("hour")}
          >
            小時
          </FilterChip>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState title="尚無時序資料" />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={items} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="bucket"
                tick={{ fontSize: 11 }}
                tickFormatter={(_, i) => formatTick(items[i].parsed, granularity)}
                minTickGap={granularity === "hour" ? 24 : 8}
              />
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
                labelFormatter={(_, payload) => {
                  const p = payload?.[0]?.payload?.parsed as ParsedBucket | undefined;
                  return p ? formatTooltipLabel(p, granularity) : "";
                }}
                formatter={(_v, _n, p) => {
                  const row = p?.payload as
                    | { cost: number; tokens: number }
                    | undefined;
                  if (!row) return null;
                  return [
                    `${formatUSD(row.cost)} · ${row.tokens.toLocaleString()} tokens`,
                    "用量",
                  ];
                }}
              />
              <Line
                type="monotone"
                dataKey="cost"
                stroke="rgb(var(--color-primary))"
                strokeWidth={2}
                dot={granularity === "day"}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

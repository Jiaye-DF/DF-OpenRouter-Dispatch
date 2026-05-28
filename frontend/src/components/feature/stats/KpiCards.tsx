import { Activity, Coins, Hash } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatUSD } from "@/lib/utils/format";
import type { StatsOverview } from "@/types/api";

interface Props {
  data?: StatsOverview;
  loading?: boolean;
}

// 三張 KPI 卡：總請求數 / 總 tokens / 總金額
export function KpiCards({ data, loading }: Props) {
  const items = [
    {
      label: "總請求數",
      value: data ? data.total_requests.toLocaleString() : "-",
      icon: Activity,
    },
    {
      label: "總 Tokens",
      value: data ? data.total_tokens.toLocaleString() : "-",
      icon: Hash,
    },
    {
      label: "總成本 (USD)",
      value: data ? formatUSD(data.total_cost_usd) : "-",
      icon: Coins,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <Card key={item.label}>
            <CardHeader className="flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm text-muted-foreground font-normal">
                {item.label}
              </CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-24" />
              ) : (
                <div className="text-2xl font-semibold">{item.value}</div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

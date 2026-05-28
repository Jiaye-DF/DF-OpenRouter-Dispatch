"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

export interface RankingRow {
  name: string;
  requests: number;
  tokens: number;
}

interface Props {
  items: RankingRow[];
  emptyText?: string;
}

// 儀錶板四維度共用的排行表 — 預設 Top 10,可展開全部。依 tokens 降冪排序。
export function RankingTable({ items, emptyText = "尚無資料" }: Props) {
  const [expanded, setExpanded] = React.useState(false);

  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-4 text-center">
        {emptyText}
      </div>
    );
  }

  const sorted = [...items].sort((a, b) => b.tokens - a.tokens);
  const shown = expanded ? sorted : sorted.slice(0, 10);
  const hasMore = sorted.length > 10;

  return (
    <div className="mt-4">
      <Table>
        <THead>
          <TR>
            <TH className="w-16 text-right">排名</TH>
            <TH>名稱</TH>
            <TH className="text-right">請求數</TH>
            <TH className="text-right">Tokens</TH>
          </TR>
        </THead>
        <TBody>
          {shown.map((row, i) => (
            <TR key={`${row.name}-${i}`}>
              <TD className="text-right text-muted-foreground font-mono">
                {i + 1}
              </TD>
              <TD className="max-w-[240px] truncate" title={row.name}>
                {row.name}
              </TD>
              <TD className="text-right font-mono">
                {row.requests.toLocaleString()}
              </TD>
              <TD className="text-right font-mono">
                {row.tokens.toLocaleString()}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
      {hasMore && (
        <div className="mt-2 flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "收合" : `顯示全部(${sorted.length})`}
          </Button>
        </div>
      )}
    </div>
  );
}

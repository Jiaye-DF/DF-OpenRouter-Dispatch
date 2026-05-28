// 後端 cost_usd 以字串傳輸(避免 JS 浮點誤差);本平台 USD 顯示一律保留 6 位小數。

const USD_DECIMALS = 6;

export function formatUSD(value: string | number | null | undefined, decimals = USD_DECIMALS): string {
  if (value === null || value === undefined || value === "") return "-";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "-";
  return `$${n.toFixed(decimals)}`;
}

export function toUSDNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

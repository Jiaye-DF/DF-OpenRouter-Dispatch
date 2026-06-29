// AI 分析(v2.0.3)枚舉中文對照 + 吻合度格式 util,集中以利 reuse
// (對齊 02-frontend/05-components.md「任何 reuse 必抽」)。
//
// 枚舉來源為後端 backend/app/schemas/ai_model_eval.py 的 TaskIntent / TaskComplexity;
// 後端一律傳原始枚舉字串(如 code_generation),中文對照由前端維護
// (propose-v2.0.3.md §6.2 / 決議 #4)。**新增枚舉時兩邊同步**(§8.4)。
//
// 全檔純函式、無副作用、TS strict。

// 任務意圖枚舉 → 中文 label(來源:後端 TaskIntent)
export const INTENT_LABELS: Record<string, string> = {
  code_generation: "程式生成",
  qa: "問答",
  summarization: "摘要",
  translation: "翻譯",
  reasoning: "推理",
  extraction: "擷取",
  other: "其他",
};

// 任務複雜度枚舉 → 中文 label(來源:後端 TaskComplexity)
export const COMPLEXITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中等",
  high: "高",
};

// 意圖中文 label;查不到回原值(fallback 不爆,容忍後端未來新增枚舉)
export function intentLabel(v: string): string {
  return INTENT_LABELS[v] ?? v;
}

// 複雜度中文 label;查不到回原值(fallback 不爆)
export function complexityLabel(v: string): string {
  return COMPLEXITY_LABELS[v] ?? v;
}

// 吻合度色階門檻(0–1):≥0.7 高、≥0.4 中、其餘低;null → none。
// 供 task-306 決定進度條 / Badge 顏色(高綠中黃低紅)。集中於此避免散落。
const FIT_HIGH_THRESHOLD = 0.7;
const FIT_MID_THRESHOLD = 0.4;

// 後端 Decimal→string 的吻合度(如 "0.733")→ 整數百分比字串(如 "73%")。
// 解析失敗 / null → 安全字串 "—"(em dash),不爆。
export function formatFitPercent(score: string | null): string {
  if (score === null) return "—";
  const n = Number(score);
  if (!Number.isFinite(n)) return "—";
  // 0–1 → 0–100,四捨五入到整數百分比,保持一致格式
  return `${Math.round(n * 100)}%`;
}

// 吻合度色階判斷:high / mid / low / none(null 或解析失敗 → none)。
// 門檻見上方常數;供 306 映射顏色,集中以利調門檻一處改。
export function fitTone(score: string | null): "high" | "mid" | "low" | "none" {
  if (score === null) return "none";
  const n = Number(score);
  if (!Number.isFinite(n)) return "none";
  if (n >= FIT_HIGH_THRESHOLD) return "high";
  if (n >= FIT_MID_THRESHOLD) return "mid";
  return "low";
}

// ─── v2.1.0 對比裁決(RerunRecommendation.compare_winner / compare_score)──
// 來源為後端 discriminator 裁決原始字串(original / challenger / tie),
// 中文對照由前端維護(對齊 INTENT_LABELS 慣例;新增枚舉時兩邊同步)。

// 裁決枚舉 → 中文 Badge label(來源:後端 compare_winner)
export const WINNER_LABELS: Record<string, string> = {
  original: "維持原模型",
  challenger: "建議改用",
  tie: "平手",
};

// 裁決中文 label;查不到回原值(fallback 不爆,容忍後端未來新增枚舉)
export function winnerLabel(v: string): string {
  return WINNER_LABELS[v] ?? v;
}

// 裁決色調:original / challenger / tie / none(查不到 → none)。
// 供 task-410 決定 Badge 顏色,集中以利一處改。
export function winnerTone(
  v: string,
): "original" | "challenger" | "tie" | "none" {
  if (v === "original" || v === "challenger" || v === "tie") return v;
  return "none";
}

// 後端 Decimal→string 的信心分數(如 "0.82",0–1)→ 整數百分比字串(如 "82%")。
// 解析失敗 / null → 安全字串 "—"(em dash),不爆(對齊 formatFitPercent)。
export function formatConfidencePercent(score: string | null): string {
  if (score === null) return "—";
  const n = Number(score);
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n * 100)}%`;
}

// ─── v2.1.0 裁決分布(RerunStats 各計數)總覽頁中文 label ──────────────
// 單一來源,供 task-411 總覽頁頁頂彙總顯示;禁前端各頁硬編。
// key 對齊後端 RerunStats 欄位名(去掉 _count;total 為 total_recommendations)。
export const VERDICT_DISTRIBUTION_LABELS: Record<string, string> = {
  total: "推薦模型總數",
  keep: "維持原模型",
  swap: "建議改用",
  tie: "平手",
  unjudged: "未裁決",
  failed: "重跑失敗",
};

// 裁決分布中文 label;查不到回原值(fallback 不爆)。
export function verdictDistributionLabel(key: string): string {
  return VERDICT_DISTRIBUTION_LABELS[key] ?? key;
}

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

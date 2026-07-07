// 日期時間顯示共用入口(對齊 docs/Design-Base/02-frontend/04-datetime.md)。
//
// DB 存 UTC+8 wall-clock:**禁** `new Date(...).toLocaleString` / 帶 `timeZone`
// (會二次時區偏移)。一律以正規表示式切 ISO 字串,不建構 Date 物件。
// 本檔為 fixed.md v2.1 §5 / §8 記載「共用 datetime util 缺口」的落地(reflect 候選 2)。

/** 將 UTC+8 wall-clock ISO 字串格式化為 `YYYY/MM/DD HH:mm:ss`;空值回「—」。 */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/);
  return m ? `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}:${m[6]}` : iso;
}

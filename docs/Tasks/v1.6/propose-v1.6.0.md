[//]: # (此檔為 v1.6 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.6.0 · 部門+SDK Key 管理整合 + 後台導引動線清理

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.6.0.md`。
>
> 對應母本:[v1.5 專案維度串接 + 儀表板多維度篩選](../v1.5/propose-v1.5.0.md)。

## 1. 目標

兩件事一起做:

1. **把「SDK Key 管理」整個合進「部門管理」頁**,讓 admin 進後台後可以依「部門 → 專案 → 使用者」線性順序完成設定,中間不必跳到別的選單;同時降低新使用者對 SDK Key 是什麼、要在哪管理的困惑。
2. **後台導引動線的雜訊清理**:移除 user-guide 殘留的版本相對描述(例「(v1.5+ 必填)」),這類字串對沒有歷史脈絡的讀者反而是雜訊。

不做:**SDK Key 認證機制變更**(維持 v1.5 的「argon2 hash 驗證 + AES-GCM 可逆加密供顯示」雙寫策略,不改 auth path)。

## 2. 動機

- v1.5 之前,後台側邊欄把「組織」(部門 / 專案 / 使用者)與「存取金鑰」(SDK Keys)分成兩個 section,新使用者第一次設定時必須在兩個 section 之間來回切。
- 業務流程上「建立一個新部門」幾乎一定會緊接著「核發第 1 把 SDK Key 給這個部門的程式用」 — 拆兩頁讓這個 1+1 動作硬被中斷。
- v1.5 已把 SDK Key 改為可逆加密(`key_encrypted` 欄,DB 內存得到完整明文),展開部門 row 直接展示底下所有 key 的明文已經沒有「會洩漏」的技術阻礙(整個風險面已在 v1.5 評估過)。
- 「(v1.5+ 必填)」這類描述在當下是必要的版本提示;v1.6 起新團隊看到只會困惑 — 文件就該描述「現在是怎樣」,不是「相對某個版本怎樣」。

## 3. 範圍

### In Scope

**前端**:

- `src/app/(main)/departments/page.tsx`:
  - 表格 row 最左側加可展開的箭頭(chevron)按鈕;點開後在該 row 下方 inline 插入 sub-section,顯示該部門的全部 SDK Keys(名稱 / 部門金鑰明文 / 啟停 / 刪除 + 「+ 新增 SDK Key」按鈕)
  - 進頁時批次拉一次 `/api/v1/sdk-keys?size=200`,前端依 `department_uid` group 進 `Map<department_uid, SdkKey[]>`;展開時就讀已抓到的資料(不另外打 API)
  - 「新增部門」對話框新增「主金鑰名稱」欄(預設「{部門名稱} 主金鑰」);提交流程改為「POST /departments → 成功後立刻 POST /sdk-keys」兩步串接,Key 明文用既有的「明文 dialog」一次性顯示(同時也可從 row 展開後重新複製)
  - 編輯 / 刪除部門邏輯維持不動;狀態 badge 維持
- `src/components/layout/Sidebar.tsx`:
  - 移除「存取金鑰」整個 section(底下只有 SDK Keys 一項,合進部門頁後此 section 失去意義)
  - 「組織」section 順序維持為:部門 → 專案 → 使用者
- `src/app/(main)/sdk-keys/page.tsx`:**保留**,不從 sidebar 連過去,但允許直接打網址訪問(避免使用者書籤撞 404);後續 v1.7+ 視使用情況決定是否真正刪檔
- `src/app/(main)/user-guide/page.tsx`:
  - 錯誤碼表「`project_code_required`」描述移除「(v1.5+ 必填)」字串

**後端**:

- 不改動 API 形狀、不改 DB schema、不新增 migration。
- 部門 + SDK Key 的兩步串接由前端負責;若第 1 步成功、第 2 步失敗(極少數情境如部門剛建立後立刻被刪),使用者可以從展開的部門 row 直接「+ 新增 SDK Key」補救,UX 上可接受不需要 transactional endpoint。

**文件**:

- `docs/Tasks/v1.6/propose-v1.6.0.md`(本檔)
- propose 確認後產出 `docs/Tasks/v1.6/tasks-v1.6.0.md`

### Out of Scope

- **SDK Key 認證 / 加密策略變更**(v1.5 的雙寫策略繼續沿用)
- **SDK Key 綁專案**(同 v1.5 propose § 3.Out of Scope,留待後續視需求再加)
- **後端 transactional「建部門+建 key」端點**(前端兩步串接 + 補救路徑已夠)
- **舊 `/sdk-keys` 路徑的 redirect / 刪除**(觀察一兩版,確認沒人靠書籤進來再清)
- **`docs/INTEGRATION.md`「(v1.5+ 必填)」字串**:INTEGRATION 是給 SDK 接入方看的文件,版本相對描述對外部讀者反而有用,維持不動
- **預算管理**(同 v1.5 propose:留待業務需求出現)

## 4. 流程概要

```
admin 進後台
   │
   └─ 側邊欄「組織」section
        部門 ──▶ 專案 ──▶ 使用者(順序設定)
        │
        ├─ 「+ 新增部門」對話框
        │     │
        │     ├─ 填:代碼 / 名稱 / 描述 / 主金鑰名稱(預設「{部門名稱} 主金鑰」)
        │     └─ 送出:POST /departments → 成功後 POST /sdk-keys
        │                                    │
        │                                    └─ 回傳明文 → 一次性 Dialog 顯示 + 複製
        │
        └─ 部門表格 row(展開後)
              │
              ├─ 該部門全部 SDK Keys(名稱 / 部門金鑰明文 / 啟停 / 刪除)
              └─ 「+ 新增 SDK Key」 → 同樣 POST /sdk-keys
```

## 5. 既有資料相容

- 既有 SDK Keys(無論 v1.5 之前或之後建立)在新的部門展開區塊中都會出現,差別只是 v1.5 前建立的 row 部門金鑰欄會顯示「(舊資料,請重新建立)」(沿用 v1.5 已實作的 UI)
- 不需要資料遷移、不需要新 migration
- 既有 `/sdk-keys` 頁面保留,但側邊欄不再連過去 → 既有書籤仍能打開

## 6. 後續可考慮(留待後續版本)

- 觀察 `/sdk-keys` 路由的 access 紀錄,沒人靠書籤進來就在 v1.7+ 直接刪檔
- 部門卡片預設展開最新建立的 row(降低使用者第一次找不到剛產生的 key 的機率)
- 在「主金鑰」概念上加 UI tag(例 第 1 把 / 後加的);目前 schema 沒這個欄位,需評估是否值得新增
- 預算管理(同 v1.5 留下的候選)

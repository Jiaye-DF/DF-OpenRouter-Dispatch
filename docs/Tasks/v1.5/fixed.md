# v1.5 收尾修正(fixed)

v1.5 主體(專案維度串接 + 儀表板多維度篩選)合併進 `main` 後,UI / 文案 / 後台管理流程的修正項目集中於此。
與 [`tasks-v1.5.0.md`](./tasks-v1.5.0.md) 已完成的 DoD 分開追蹤。

## 修正項目總覽

| # | 項目 | 狀態 |
| --- | --- | --- |
| 01 | [模型 modality tag(可輸入 / 可輸出)+ Sync 白名單改名為模型白名單](#fix-01模型-modality-tag可輸入--可輸出--sync-白名單改名為模型白名單) | 已完成 |
| 02 | [SDK Key 後台可顯示明文 + 「Prefix」欄改名「部門金鑰」](#fix-02sdk-key-後台可顯示明文--prefix-欄改名部門金鑰) | 已完成 |
| 03 | [角色 badge `admin` / `user` 中文化為「管理員」/「成員」](#fix-03角色-badge-admin--user-中文化為管理員成員) | 已完成 |
| 04 | [SDK Key 儲存策略修正:放棄 AES-GCM 加密,改為純 TEXT 欄](#fix-04sdk-key-儲存策略修正放棄-aes-gcm-加密改為純-text-欄) | 已完成 |
| 05 | [user-guide 文案清理:移除 `(v1.5+ 必填)` 殘留描述](#fix-05user-guide-文案清理移除-v15-必填-殘留描述) | 已完成 |

---

## Fix 01 · 模型 modality tag(可輸入 / 可輸出)+ Sync 白名單改名為模型白名單

### 問題

- 既有 `models.modality` 是單一字串欄(例 `"text->text"`),無法清楚表達「這個模型能吃文字 / 圖片 / 檔案,只能吐文字」這類多重模態組合;UI 顯示的是 raw 字串,讀者要自行解讀箭頭。
- 側邊欄按鈕「Sync 白名單」字面突顯了「同步」這個內部機制,新使用者不知道按下去要幹嘛;業務上這就是「模型白名單」。

### 調整

#### DB / 後端

- Alembic `0007_model_modality_tags` 新增 `models.input_modalities` / `output_modalities`(`text[]`,預設 `'{}'`)。舊 `modality` 欄保留,維持歷史相容。
- `sync._parse_or_model()` 從 OpenRouter 的 `architecture.input_modalities` / `output_modalities` 萃取陣列;`_normalize_modalities()` 統一 lowercase + 去重保序,並相容字串(例 `"text+image"`)/ list 兩種輸入格式。
- `_sync_models()` UPSERT 新建 / 更新都會寫入兩個 tag 陣列。
- `ModelRead` / `AllowedModelRead` 兩個 schema 都加上新欄位;`ModelPatch` / `ModelCreateRequest` 開放 internal 模型 admin 自訂 tag(max 16)。
- `_INTERNAL_PATCHABLE` 加入兩欄;`_safe_json` 支援 list 寫入 audit log。

#### 前端

- `types/api.ts` `Model` 加 `input_modalities` / `output_modalities`。
- `admin/models/page.tsx` 新增 `<ModalityTags>` 組件:每個 token 一顆 pill(text / image / file / audio / video 各有 icon + 色),格式 `[輸入...] → [輸出...]`;若兩邊皆空,fallback 顯示舊 `modality` 字串。
- 套用於:`xl+` 表格、`< xl` 卡片、編輯 Drawer 三處。
- `Sidebar.tsx` 與 `allowed-models/page.tsx`(頁面標題、描述、權限不足 fallback)的「Sync 白名單」字串替換為「模型白名單」;後端 docstring 描述機制本身,維持不動。
- `user-guide/page.tsx` SDK 文件加上 `input_modalities` / `output_modalities` 欄位說明。

### 交付物

- 新增:`backend/alembic/versions/0007_model_modality_tags.py`
- 修改:`backend/app/models/model.py`、`backend/app/services/sync.py`、`backend/app/schemas/model.py`、`backend/app/api/v1/models.py`
- 修改:`frontend/src/types/api.ts`、`frontend/src/app/(main)/admin/models/page.tsx`、`frontend/src/app/(main)/admin/allowed-models/page.tsx`、`frontend/src/components/layout/Sidebar.tsx`、`frontend/src/app/(main)/user-guide/page.tsx`

---

## Fix 02 · SDK Key 後台可顯示明文 + 「Prefix」欄改名「部門金鑰」

### 問題

- v1.5 之前 `sdk_api_keys` 只存 argon2 hash,明文僅建立時一次性顯示,事後無法重新檢視;業務上 admin 需要能隨時把已建立的 key 發給對應部門的人,「掉了再開一把」流程過於繁瑣。
- 側邊「SDK Keys」頁面表頭「Prefix」對非開發背景的使用者語意不清。

### 調整

#### 第一版實作(已被 Fix 04 取代)

- 起初採「argon2 hash + AES-GCM 加密」雙寫策略:auth path 保留 argon2 hash 不動(零影響);新增 `key_encrypted BYTEA` 欄存 AES-GCM blob 供後台還原。
- 詳見 Alembic `0008_sdk_key_encrypted`;此版本已被 Fix 04 修正為純 TEXT 欄,本節僅保留交付物供追溯。

#### 通用調整(保留至本版)

- `SdkKeyResponse` 加 `key_values: str | None`(原本為 `key_plaintext`,於 Fix 04 改名),由 `_to_response()` 統一回填。
- 前端 `SdkKey` type 加上 `key_values: string | null`;`sdk-keys/page.tsx` 表頭「Prefix」改為「部門金鑰」,直接顯示完整明文 + `Copy` icon 複製(複製後 toast「已複製部門金鑰」);舊資料(`key_values` 為 null)顯示 `prefix··· (舊資料,請重新建立)`。
- 建立後 Dialog 文案改為「已建立完成,亦可從列表的部門金鑰欄位隨時複製」(原本是「請立即複製,關閉後無法再取得」)。

### 交付物

- 修改:`backend/app/api/v1/sdk_keys.py`、`backend/app/schemas/sdk_key.py`、`backend/app/models/sdk_api_key.py`、`backend/app/services/sdk_key.py`
- 修改:`frontend/src/types/api.ts`、`frontend/src/app/(main)/sdk-keys/page.tsx`

---

## Fix 03 · 角色 badge `admin` / `user` 中文化為「管理員」/「成員」

### 問題

`/users` 頁角色欄直接顯示 raw enum 字串 `admin` / `user`,與系統其他欄位的全中文化不一致;另外 sidebar 底部與 user-guide 文件混用「一般使用者」與 raw `user`,對外稱呼不統一。

### 調整

- `users/page.tsx` 表格角色 badge 由 `{u.role}` 改為三元運算式渲染中文:`u.role === "admin" ? "管理員" : "成員"`。
- 連帶調整「一般使用者」相關文案統一為「成員」:
  - `users/page.tsx` 建立 Dialog 下拉:`<option value="user">成員(...)</option>`,描述文字同步。
  - `Sidebar.tsx` 非 admin 底部標籤:「一般使用者檢視」→「成員檢視」。
  - `user-guide/page.tsx`:「管理員(admin)... 一般使用者只接觸...」→「... 成員(user)只接觸...」。

### 交付物

- 修改:`frontend/src/app/(main)/users/page.tsx`、`frontend/src/components/layout/Sidebar.tsx`、`frontend/src/app/(main)/user-guide/page.tsx`

---

## Fix 04 · SDK Key 儲存策略修正:放棄 AES-GCM 加密,改為純 TEXT 欄

### 問題

Fix 02 第一版採 AES-GCM 加密儲存(BYTEA 欄 `key_encrypted`),立意是「即使 DB 外洩,沒有 `ENCRYPTION_KEY` 仍無法還原」。但實際業務需要:

- admin 需要能**直接在 DB GUI(pgAdmin / DBeaver)編輯**該欄,以補回 v1.5 之前建立的舊 key 明文。
- BYTEA 欄在 GUI 一律跳「上傳檔案」widget,且即使能塞,還是要先在本機算 AES-GCM blob — 流程太繁瑣,違背「後台可隨時複製明文」的初衷。
- 既然業務已接受「admin 可隨時看到完整 key」,DB 外洩風險面已敞開,額外的 AES 層只是儀式感而非實質防護。

### 調整

#### DB

- Alembic `0009_sdk_key_values_plaintext`:`DROP COLUMN IF EXISTS key_encrypted` + `ADD COLUMN key_values TEXT NULL`。`IF EXISTS` 防呆:已套用 0008(BYTEA)的環境會把舊欄丟掉;未套用過的環境也能直接 upgrade。
- 舊 0008 期間建立的 `key_encrypted` 內容**無法保留**,需要的話 admin 自行在 `key_values` 新欄填入明文,或在後台重建 key。

#### 後端

- `SdkApiKey` model:移除 `key_encrypted: bytes | None`,改為 `key_values: Mapped[str | None] = mapped_column(Text)`;import 同步移除 `LargeBinary`,加入 `Text`。
- `services/sdk_key.py`:`create_sdk_key()` 直接寫 `key_values=full`(放棄 `encrypt_bytes()`);`reveal_sdk_key()` 改為單行 `return row.key_values`(放棄解密)。`app.core.crypto` 不再 import。
- `SdkKeyResponse` 欄位 `key_plaintext` 改名 `key_values`,語意對齊 DB 欄;`_to_response()` / `SdkKeyCreateResponse` 同步調整。

#### 前端

- `types/api.ts` `SdkKey.key_plaintext` → `SdkKey.key_values`。
- `sdk-keys/page.tsx` 內 `k.key_plaintext` 三處 reference 全部改為 `k.key_values`(複製、顯示、條件判斷)。

### 安全提醒

- 此版本後 SDK Key 明文**直接以明文形式儲存於 DB**(`sdk_api_keys.key_values`)。
- DB dump / replication slot / backup 一旦外流,所有部門金鑰等同明文外洩。
- `ENCRYPTION_KEY` 於 SDK Key 路徑不再參與保護(僅用於 OpenRouter Key 等其他欄位)。
- argon2 `key_hash` 仍保留並用於 auth 驗證,auth path 零改動;`key_values` 只供後台顯示用。

### 交付物

- 新增:`backend/alembic/versions/0009_sdk_key_values_plaintext.py`
- 修改:`backend/app/models/sdk_api_key.py`、`backend/app/services/sdk_key.py`、`backend/app/schemas/sdk_key.py`、`backend/app/api/v1/sdk_keys.py`
- 修改:`frontend/src/types/api.ts`、`frontend/src/app/(main)/sdk-keys/page.tsx`

---

## Fix 05 · user-guide 文案清理:移除 `(v1.5+ 必填)` 殘留描述

### 問題

`user-guide` 錯誤碼表 `project_code_required` 描述帶「(v1.5+ 必填)」字串。這類版本相對描述在 v1.5 釋出當下確實是必要提示;但對之後接入的 SDK 使用者只是雜訊 — 文件應描述「現在是怎樣」,而非「相對某個版本怎樣」。

### 調整

- `frontend/src/app/(main)/user-guide/page.tsx:180` 描述「未帶 X-Project-Code header(v1.5+ 必填)」改為「未帶 X-Project-Code header」。
- `docs/INTEGRATION.md` 為對外整合文件,保留原描述供 SDK 整合方了解版本相容性,本次不動。

### 交付物

- 修改:`frontend/src/app/(main)/user-guide/page.tsx`

> 註:此修正實際提交於 dev-v1.6 分支(commit `e8eaf0e`)併同 v1.6 propose 一起;追溯記在 v1.5 fixed 是因為這是 v1.5 期間累積的殘留文案。

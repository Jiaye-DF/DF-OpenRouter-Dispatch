# 串接整合說明(INTEGRATION）

SDK 使用者透過 **SDK Key + User Token** 雙因子呼叫代理端點的完整說明。
本文件內容與後台「使用者使用說明」頁面一致,可單獨交付給 SDK 使用者。

---

## 1. 概述

本平台為 OpenRouter API 的**代理層**:統一管理金鑰、模型白名單與用量稽核。

使用者**不需要**登入此網站,只需要拿到管理員發放的兩組憑證,即可在自己的程式碼或工具裡呼叫代理端點。

管理員(admin)透過後台集中發放與管理憑證、模型白名單與部門金鑰;一般使用者只接觸下面提到的「SDK Key + User Token」雙因子組合。

---

## 2. 取得憑證(由管理員發放)

呼叫代理端點需要三組憑證,皆由管理員在後台建立後**一次性**給予使用者:

| Header | 層級 | 說明 |
| --- | --- | --- |
| `X-SDK-Key` | 部門層級 · 存取金鑰 | 以部門為單位發放,代表「**哪個部門的程式在呼叫**」。由 admin 於後台「存取金鑰 / SDK Keys」建立,格式類似 `ordsk_xxxxxxxxxxxx_xxxx…`。 |
| `X-User-Token` | 使用者層級 · 加密 payload | 以個別使用者為單位發放,代表「**哪個人在呼叫**」。由 admin 於「使用者管理」頁針對 role=user 的使用者產生,為加密字串、內含使用者識別與發行時間。 |
| `X-Project-Code` | 專案層級 · 代碼 | 以部門底下的專案為單位發放(v1.5+),代表「**這次呼叫歸到哪個專案算用量**」。值為「專案管理」頁面顯示的 `代碼`(由系統自動產生的數字字串,例如 `53299897503322112`)。同一把 SDK Key 可呼叫同部門任一專案。 |

> ⚠ SDK Key 與 User Token 皆**只在建立時顯示一次**;Project Code 在後台可隨時複製。遺失 SDK Key / User Token 只能請管理員重新發放(同時舊憑證會被撤銷)。
>
> ⚠ **三者必須屬於同一部門**:SDK Key、User Token 各自綁部門,Project Code 必須屬於 SDK Key 的部門;否則代理端會回 `401 unauthorized` 或 `400 project_invalid`。

---

## 3. 呼叫環境

本平台提供**測試**與**正式**兩個環境,請依用途選用對應的 Base URL。

| 環境 | Base URL |
| --- | --- |
| 測試環境 | `https://df-it-openrouter-dispatch-stage-api.it.zerozero.tw` |
| 正式環境 | `https://df-it-openrouter-dispatch-api.it.zerozero.tw` |

> 本文件後續範例皆以**正式環境**為準,測試時將 Base URL 換成測試環境即可。

---

## 4. 端點與認證 Header

所有呼叫皆透過下面這支端點:

```http
POST https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat
Content-Type: application/json
X-SDK-Key: <SDK Key 明文>
X-User-Token: <User Token 明文>
X-Project-Code: <專案代碼>
```

- 三個 Header **皆必填**;缺 SDK Key / User Token 回 `401 unauthorized`,缺 X-Project-Code 回 `400 project_code_required`,Project 不屬該部門 / 已停用 回 `400 project_invalid`。
- 請勿把憑證寫死於前端 / 公開 repo / 客戶端 App;只能存放在受控的後端或 CI Secret 環境變數。

---

## 5. Request Body

JSON body 欄位如下:

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `model` | string | 是 | OpenRouter 模型 id(例:`openai/gpt-4o-mini`),須在管理員設定的白名單內 |
| `text` | string | 否 | 使用者輸入的文字 |
| `images` | string[] | 否 | 圖片 URL 或 `data:image/...;base64,...` 字串陣列 |
| `files` | object[] | 否 | 上傳檔案(如 PDF)陣列,每筆為 `{ "filename": string, "file_data": string }`;`file_data` 為 `data:application/pdf;base64,...` 或可公開存取的遠端 URL,見 §5.3。**自 v2.2.1 起,用量紀錄除 `filename` 外亦留存檔案內容**(存於公司自有 S3,見 §11) |
| `videos` | string[] | 否 | 暫不支援,送出即回 `400 feature_not_supported` |
| `tools` | object[] | 否 | 工具清單,格式同 OpenAI `tools` 規格,原樣透傳給下游。**目前僅支援 OpenRouter server 端內建工具**(如 web search,見 §5.2);會回 `tool_calls` 的 function calling 尚未開放 |
| `messages` | object[] | 否 | **多輪對話訊息陣列**(v2.1.2),每筆為 `{ "role": string, "content": string \| object[] }`。`role` 只收 `system` / `user` / `assistant`;`content` 為字串或 content parts 陣列(只收 `text` / `image_url` / `file` 三種 type)。**與 `text` / `images` / `files` 互斥**(同時帶回 `400`);不可為空陣列;無應用層筆數上限(模型 context window 為自然上限)。見 §5.4 |
| `temperature` | number | 否 | 生成隨機性,值域 **0–2**(v2.1.2);未帶 → 不注入,走**模型預設值**。見 §5.5 |
| `max_tokens` | integer | 否 | 回覆最大 token 數,**≥ 1**(v2.1.2);未帶 → 不注入,走**模型預設值**。見 §5.5 |
| `response_format` | object | 否 | 回覆格式(v2.1.2),`type` 只收 `json_object` / `json_schema`;`json_schema` 型別**必帶** `json_schema` 物件、`json_object` **不可帶**;未帶 → 不注入,走**模型預設**。見 §5.5 |

> v2.1.2 起內容支援兩種模式,**互斥擇一**:單輪模式(`text` / `images` / `files`,舊 client 行為完全不變)或多輪 `messages` 直傳模式(§5.4);`tools` 與生成參數(`temperature` / `max_tokens` / `response_format`,§5.5)**兩種模式皆可搭配**。

可用的 `model` 清單由管理員集中維護。你可隨時查詢已啟用的模型清單(見下方 §5.1),從中複製 `model_key` 填入此欄位;若呼叫時收到 `403 model_forbidden`,請向管理員確認該模型是否已啟用。

### 5.1 查詢可用模型清單

以 GET 取得目前**已啟用**的模型清單(精簡欄位):

```http
GET https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/allowed/models
```

- 此端點**不需任何憑證**,可直接於瀏覽器開啟。
- 回應 `data[]`(陣列)每筆的 `model_key` 即為呼叫 §4 端點時 `model` 欄位要填入的值;`provider`(來源,如 `openrouter`)、`name` 為模型顯示名稱、`description` / `context_length` / `modality` / `input_modalities` / `output_modalities` 供參考(modality tag 為陣列,例 `["text","image"]`)。
- 僅回傳已啟用(白名單內)的模型,清單與管理員後台維護結果同步。
- 定價、tokenizer 等內部欄位不對外;若需完整資訊請聯絡管理員。

**含圖片的 Request 範例:**

```json
{
  "model": "openai/gpt-4o-mini",
  "text": "請描述這張圖片",
  "images": [
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    "https://example.com/photo.jpg"
  ]
}
```

### 5.2 啟用工具(web search)

帶 `tools` 即可啟用 OpenRouter server 端內建工具。最常用的是 **web search** —— 由 OpenRouter 在伺服器端執行搜尋後,讓模型結合搜尋結果生成回覆;**回應仍是純文字**,呼叫方式與一般請求完全相同,無須額外處理 `tool_calls`。

```json
{
  "model": "openai/gpt-4o-mini",
  "text": "今天台積電(2330)的最新股價與相關新聞?",
  "tools": [{ "type": "openrouter:web_search" }]
}
```

- `tools` 內容原樣透傳給 OpenRouter;格式 / 可用工具型別以 OpenRouter 官方文件為準,本平台不另行驗證,傳錯會由 OpenRouter 回對應錯誤。
- 啟用 web search 會由 OpenRouter 額外計費,費用一併反映在用量統計中。
- 目前**僅支援 server 端工具**(回應為純文字);會回 `tool_calls` 的 function calling 尚未開放,如有需求請向管理員提出。

### 5.3 上傳檔案(PDF 等)

帶 `files` 即可隨訊息附上檔案(如 PDF),交由模型閱讀後回答。每筆檔案需提供 `filename` 與 `file_data` 兩個欄位:

```json
{
  "model": "openai/gpt-4o-mini",
  "text": "請摘要這份文件的重點",
  "files": [
    {
      "filename": "report.pdf",
      "file_data": "data:application/pdf;base64,JVBERi0xLjcKJ..."
    }
  ]
}
```

- `file_data` 可填 **base64 data URL**(`data:application/pdf;base64,...`)或**可公開存取的遠端 URL**(如 `https://example.com/doc.pdf`)。
- 檔案解析由 OpenRouter 處理:模型原生支援檔案輸入時直接傳入,否則由 OpenRouter 解析後再送模型;解析 / 額外 token 可能由 OpenRouter 計費,一併反映在用量統計。
- **保存政策(v2.2.1 起變更)**:用量紀錄自 v2.2.1 起會留存 `filename` **與檔案內容**;檔案存放於公司自有 AWS S3(private,不對外公開),取用一律經後端簽發的短期連結。**v2.2.1 之前的歷史紀錄只有檔名、沒有內容,不會也無法補上**。細節見 §11。
- 請仍避免在 `filename` 與檔案內容中夾帶不必要的敏感個資。

### 5.4 多輪對話(`messages` 直傳模式,v2.1.2)

帶 `messages` 即可自帶**完整多輪對話**——system prompt、user / assistant 歷史——取代單輪的 `text` / `images` / `files`,支撐對話記憶、角色設定等進階串接情境。三個入口(`/model/chat`、`/model/chat/stream`、deprecated `/model/openrouter/chat`)request body 完全相同;成功回應格式**不變**(§6,`data` 仍為模型回應的純文字)。

```json
{
  "model": "openai/gpt-4o-mini",
  "messages": [
    { "role": "system", "content": "你是客服助理" },
    { "role": "user", "content": "上次說到哪?" },
    { "role": "assistant", "content": "說到出貨進度。" },
    { "role": "user", "content": [
      { "type": "text", "text": "看一下這張圖與檔案" },
      { "type": "image_url", "image_url": { "url": "data:image/png;base64,..." } },
      { "type": "file", "file": { "filename": "report.pdf", "file_data": "data:application/pdf;base64,..." } }
    ] }
  ]
}
```

規則:

- **互斥**:`messages` 與 `text` / `images` / `files` **擇一**;同時帶回 `400`(detail 例:`Value error, messages 與 text 互斥,擇一提供`),不做隱式合併。
- **role 白名單**:只收 `system` / `user` / `assistant`;`tool` role 與 `tool_calls` 回傳鏈**不開放**。
- **content 形狀**:字串,或 parts 陣列——type 只收 `text` / `image_url`(內層 `{ "url": ... }`,值同 §5 `images`)/ `file`(內層同 §5.3 的 `{ "filename", "file_data" }`);`video` 仍不支援。
- **不可為空陣列**(回 `400`);**無應用層筆數上限**,模型 context window 為自然上限,超限由 OpenRouter 回錯誤。
- `tools`(§5.2)可照常搭配。
- **隱私**:用量紀錄會快照 `messages` 供稽核;其中的圖片與檔案自 v2.2.1 起改存公司自有 S3(快照只留物件位置,不再留 base64 字串),file part 除 `filename` 外亦留存檔案內容(同 §5.3 / §11)。**request 契約不變**,呼叫端照舊送 base64 data URI 即可。

### 5.5 生成參數(`temperature` / `max_tokens` / `response_format`,v2.1.2)

三個生成參數**單輪與 messages 模式皆可帶**(與內容模式正交);**未帶即走模型預設值**(後端不注入該欄位)。

| 參數 | 值域 / 形狀 | 用途 |
| --- | --- | --- |
| `temperature` | number,`0`–`2` | 控制生成隨機性(低 = 穩定、高 = 發散) |
| `max_tokens` | integer,`≥ 1` | 回覆最大 token 數(控制長度與成本;上限交由模型把關) |
| `response_format` | `{ "type": "json_object" }` 或 `{ "type": "json_schema", "json_schema": { ... } }` | 結構化輸出:`json_object` 讓模型回**合法 JSON 字串**;`json_schema` 依你附上的 schema 物件輸出 |

- 超出值域 / `type` 非白名單 → `400`(見 §9)。
- `response_format` 為 `json_object` 時**不可**帶 `json_schema` 物件;為 `json_schema` 時**必帶**。使用 `json_object` 時請在 prompt 中明確要求回 JSON(部分模型的要求)。
- **其餘生成參數(`top_p` / `stop` / `frequency_penalty` / `presence_penalty` / `seed` / `logit_bias` 等)一律不開放**,帶了也不會透傳給模型,請勿嘗試;如有需求請向管理員提出。

<!--
本段「本地模型」目前停用,等實際導入企業內部模型再開啟。
**本地模型(企業內部 server)**

呼叫方式**完全相同**(同 endpoint、同 header),只是 `model` 字串改成管理員給你的本地模型 id(慣例 `internal/<name>`)。本地模型可能因排隊或速率限制延後執行,若收到 `429 internal_busy` 並帶 `data.retry_after_seconds`,請依該秒數退避後重試。
-->


---

## 6. Response 格式

所有回應皆包在統一格式中。

**成功:**

```json
{
  "success": true,
  "code": 200,
  "data": "模型回答的文字內容...",
  "detail": "success"
}
```

**失敗:**

```json
{
  "success": false,
  "code": 403,
  "data": null,
  "detail": "model_forbidden"
}
```

- `success`:布林,程式判斷成功失敗。
- `code`:對應 HTTP status。
- `data`:成功時為**模型回應的純文字字串**(已剝除 id / usage / provider 等 OpenRouter 內部欄位;這些僅寫入後台 usage_logs,不外露)。
- `detail`:成功固定為 `"success"`;失敗為錯誤碼或中文描述。

---

## 7. 完整範例

### curl

```bash
curl -X POST 'https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat' \
  -H 'Content-Type: application/json' \
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'X-User-Token: <admin 發放的 User Token>' \
  -H 'X-Project-Code: 53299897503322112' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "text": "用一句話介紹台灣"
  }'
```

### Python (httpx)

```python
import httpx

API_URL = "https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat(model: str, text: str) -> str:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        json={"model": model, "text": text},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]  # data 即模型回應的純文字字串

if __name__ == "__main__":
    result = chat("openai/gpt-4o-mini", "用一句話介紹台灣")
    print(result)
```

### web search(查今日美元換台幣即時匯率)

帶 `tools: [{ "type": "openrouter:web_search" }]` 啟用 OpenRouter server 端 web search;模型會即時查網路後回答,**回應仍為純文字**,呼叫方式與一般請求相同。web search 會由 OpenRouter 額外計費。

```bash
curl -X POST 'https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat' \
  -H 'Content-Type: application/json' \
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'X-User-Token: <admin 發放的 User Token>' \
  -H 'X-Project-Code: 53299897503322112' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "text": "今天 1 美元可以換多少新台幣?請用最新即時匯率回答,並標註資料來源與查詢時間。",
    "tools": [{ "type": "openrouter:web_search" }]
  }'
```

```python
import httpx

API_URL = "https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat_with_web_search(model: str, text: str) -> str:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        # 帶 tools 啟用 OpenRouter server 端 web search;回應仍為純文字
        json={
            "model": model,
            "text": text,
            "tools": [{"type": "openrouter:web_search"}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    result = chat_with_web_search(
        "openai/gpt-4o-mini",
        "今天 1 美元可以換多少新台幣?請用最新即時匯率回答,並標註資料來源與查詢時間。",
    )
    print(result)
```

### 檔案上傳(PDF,讓模型讀文件)

帶 `files` 即可隨訊息附上檔案(如 PDF),交由模型閱讀後回答。每筆檔案需提供 `filename` 與 `file_data`(base64 data URL 或可公開存取的遠端 URL)。詳見 §5.3。

**遠端 URL(最簡單,可直接 copy 測試):**

```bash
curl -X POST 'https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat' \
  -H 'Content-Type: application/json' \
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'X-User-Token: <admin 發放的 User Token>' \
  -H 'X-Project-Code: 53299897503322112' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "text": "請用三點摘要這份文件的重點",
    "files": [
      {
        "filename": "bitcoin.pdf",
        "file_data": "https://bitcoin.org/bitcoin.pdf"
      }
    ]
  }'
```

**Python(讀本機 PDF → base64 data URL):**

```python
import base64
from pathlib import Path

import httpx

API_URL = "https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def to_data_url(path: str) -> str:
    """把本機 PDF 轉成 base64 data URL。"""
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:application/pdf;base64,{b64}"

def chat_with_file(model: str, text: str, file_path: str) -> dict:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "text": text,
            "files": [
                {
                    "filename": Path(file_path).name,
                    "file_data": to_data_url(file_path),
                }
            ],
        },
        timeout=120,  # 檔案較大,逾時放寬
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    result = chat_with_file(
        "openai/gpt-4o-mini",
        "請用三點摘要這份文件的重點",
        "report.pdf",
    )
    print(result["choices"][0]["message"]["content"])
```

> 保存政策:自 **v2.2.1** 起,用量紀錄除 `filename` 外**亦留存檔案內容**(存於公司自有 S3,private,取用經後端簽發的短期連結);v2.2.1 之前的歷史紀錄只有檔名、沒有內容。見 §5.3 / §10 / §11。

### 多輪對話(messages,含 system prompt 與對話歷史)

帶 `messages` 自帶完整多輪對話(規則見 §5.4);**與 `text` / `images` / `files` 互斥**,回應仍為純文字。

```bash
curl -X POST 'https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat' \
  -H 'Content-Type: application/json' \
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'X-User-Token: <admin 發放的 User Token>' \
  -H 'X-Project-Code: 53299897503322112' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      { "role": "system", "content": "你是客服助理,回答一律使用繁體中文。" },
      { "role": "user", "content": "上次說到哪?" },
      { "role": "assistant", "content": "說到出貨進度。" },
      { "role": "user", "content": "好,幫我總結一下目前狀態。" }
    ]
  }'
```

**Python(多輪歷史 + parts 混合:文字 / 圖片 / 檔案)**:

```python
import httpx

API_URL = "https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat_messages(model: str, messages: list[dict]) -> str:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        # messages 與 text / images / files 互斥,擇一提供
        json={"model": model, "messages": messages},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    history = [
        {"role": "system", "content": "你是客服助理,回答一律使用繁體中文。"},
        {"role": "user", "content": "上次說到哪?"},
        {"role": "assistant", "content": "說到出貨進度。"},
        # content 也可以是 parts 陣列(text / image_url / file 混合,見 §5.4)
        {"role": "user", "content": [
            {"type": "text", "text": "看一下這張圖與檔案,總結目前狀態"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo..."}},
            {"type": "file", "file": {
                "filename": "report.pdf",
                "file_data": "data:application/pdf;base64,JVBERi0xLjcK...",
            }},
        ]},
    ]
    print(chat_messages("openai/gpt-4o-mini", history))
```

### 生成參數與結構化輸出(temperature / max_tokens / response_format)

帶生成參數控制隨機性與回覆長度;`response_format: {"type": "json_object"}` 讓模型回**合法 JSON 字串**(規則見 §5.5;單輪與 messages 模式皆可帶,未帶走模型預設)。

```bash
curl -X POST 'https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat' \
  -H 'Content-Type: application/json' \
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'X-User-Token: <admin 發放的 User Token>' \
  -H 'X-Project-Code: 53299897503322112' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "text": "列出台灣三大城市與人口,回傳 JSON,鍵為 cities(陣列,每筆含 name 與 population)",
    "temperature": 0.2,
    "max_tokens": 256,
    "response_format": { "type": "json_object" }
  }'
```

> 回應仍是 §6 的統一格式,`data` 為字串——但內容是合法 JSON,可直接 `json.loads(body["data"])` 解析。`json_object` 模式下 prompt 需明確要求回 JSON。

---

## 8. 串流(SSE)回應

若想要「打字機」效果——模型生成的內容一段一段即時回傳,而非等整段生成完才一次回——可改用**串流端點**。

```http
POST https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat/stream
```

- 認證 Header(`X-SDK-Key` / `X-User-Token` / `X-Project-Code`)與 Request Body 欄位**與 §4 / §5 的 `/model/chat` 完全相同**——v2.1.2 起亦包含 `messages` 多輪模式(§5.4)與 `temperature` / `max_tokens` / `response_format` 生成參數(§5.5),互斥與值域規則一致;端點本身即代表串流,**不需**在 body 加 `stream` 欄位。
- **本版本串流僅支援 `provider=openrouter` 的模型**;其餘(如未來的本地模型)呼叫串流端點會回 `400 feature_not_supported`。
- `videos` 仍不支援,送出即回 `400 feature_not_supported`。

### 8.1 回應格式

回應為 **Server-Sent Events(`Content-Type: text/event-stream`)**,**不**套 §6 的統一 `ApiResponse` 包裝。逐段以下列格式送出,最後以 `[DONE]` 收尾:

```text
data: {"id":"gen-xxxx","content":"以"}

data: {"id":"gen-xxxx","content":"下是"}

data: {"id":"gen-xxxx","content":"回答"}

data: [DONE]
```

- 每個 `data:` 事件只含 **`id`(generation id)** 與 **`content`(本段新增的文字片段)**;把所有 `content` 依序串接即為完整回答。
- OpenRouter 內部欄位(供應商 / 成本 / 路由 / `role` / `finish_reason` / `usage` 等)**一律不外露**;keep-alive 註解與無文字的事件不會送給你。
- 收到 `data: [DONE]` 代表串流正常結束。

### 8.2 串流中途錯誤

開串流**前**的錯誤(憑證 / 白名單 / provider 不支援 / Key 全失敗)與 §9 錯誤碼對照一致——以 HTTP 4xx/5xx + `ApiResponse` 回絕,**不會**進入串流。

一旦開始串流(已回 `200`),即**不重試**;若中途失敗,會送一個 error 事件後關閉,**不會**靜默截斷:

| 事件 | 意義 |
| --- | --- |
| `data: {"error":"upstream_error"}` | OpenRouter 上游於串流中途回報錯誤;此事件後串流結束 |
| `data: {"error":"openrouter_unavailable"}` 接 `data: [DONE]` | 後端與上游的連線中途中斷 |

> 解析時請檢查每個事件:含 `error` 鍵即為失敗,已累積的部分內容仍有效但不完整。呼叫端若主動中斷連線,後端會立即取消上游請求以避免額外計費。

### 8.3 範例

**curl**(`-N` 關閉緩衝,即時印出每個事件):

```bash
curl -N -X POST 'https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat/stream' \
  -H 'Content-Type: application/json' \
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
  -H 'X-User-Token: <admin 發放的 User Token>' \
  -H 'X-Project-Code: 53299897503322112' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "text": "用三句話介紹台灣"
  }'
```

> Windows 請改用 `curl.exe`(PowerShell 的 `curl` 是 `Invoke-WebRequest` 別名,不支援上述參數)。

**Python (httpx)** — 逐事件解析並即時印出:

```python
import json
import httpx

API_URL = "https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat/stream"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat_stream(model: str, text: str) -> str:
    parts: list[str] = []
    with httpx.stream(
        "POST",
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        json={"model": model, "text": text},
        timeout=httpx.Timeout(300),  # 串流總時長可能較長
    ) as resp:
        # 開串流前的錯誤仍是 JSON ApiResponse(非 SSE),直接擋下
        if resp.status_code != 200:
            body = json.loads(resp.read())
            raise RuntimeError(f"{body['code']} {body['detail']}")

        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("error"):
                raise RuntimeError(f"stream error: {event['error']}")
            piece = event.get("content", "")
            parts.append(piece)
            print(piece, end="", flush=True)  # 即時呈現
    return "".join(parts)

if __name__ == "__main__":
    full = chat_stream("openai/gpt-4o-mini", "用三句話介紹台灣")
    print("\n--- 完整內容 ---")
    print(full)
```

---

## 9. 錯誤碼對照

| HTTP | detail | 說明 / 建議處理 |
| --- | --- | --- |
| 400 | `feature_not_supported` | 請求帶了不支援的欄位(目前 videos 暫不支援) |
| 400 | (具體驗證訊息,見下) | Request body 驗證失敗(v2.1.2 起含 messages / 生成參數):`messages` 與 `text`/`images`/`files` 同時帶、`messages` 空陣列、role / content parts / `response_format.type` 非白名單、`temperature` / `max_tokens` 超出值域;`data` 為 `null` |
| 400 | `project_code_required` | 未帶 `X-Project-Code` header(v1.5+ 必填) |
| 400 | `project_invalid` | `X-Project-Code` 對應專案不存在 / 已停用 / 不屬於 SDK Key 的部門 |
| 401 | `unauthorized` | SDK Key 或 User Token 無效 / 已被撤銷 / 兩者不屬同一部門 |
| 403 | `model_forbidden` | 模型未在白名單,或已被 admin 停用 |
| 404 | `model_not_found` | OpenRouter 找不到此模型 |
| 429 | `rate_limited` | OpenRouter Key 短時間呼叫過於頻繁;建議指數退避重試 |
<!-- | 429 | `internal_busy` | 本地模型排隊已超時(`data.retry_after_seconds`);依該秒數退避後重試 | -->
| 502 | `openrouter_unavailable` | OpenRouter 服務暫時不可用,請確認 OpenRouter Key 是否有正確加入 |
| 500 | `provider_misconfigured` | 僅 internal 模型:該模型後端設定不完整,請聯絡管理員 |
| 502 | `internal_unavailable` | 僅 internal 模型:內部模型服務暫時不可用,稍後再試 |
| 500 | `操作失敗` | 後端異常,請聯絡管理員並提供時間點 |

**400 驗證錯誤的 `detail` 直接指出錯誤欄位**(仍為 §6 統一格式,`data` 恆為 `null`),實例:

- `messages` 與單輪欄位互斥:`Value error, messages 與 text 互斥,擇一提供`
- `messages` 空陣列:`Value error, messages 不可為空陣列`
- `role` 非白名單:`欄位 messages.0.role Input should be 'system', 'user' or 'assistant'`
- `temperature` 越界:`欄位 temperature Input should be less than or equal to 2`
- `response_format.type` 非白名單:`欄位 response_format.type Input should be 'json_object' or 'json_schema'`

> 憑證缺失 / 無效時**一律先回 `401 unauthorized`**(認證先於 body 驗證),不會走到上述 400。

---

## 10. 安全注意事項

- **不要**把 SDK Key / User Token 寫死於前端(Browser / App)或 commit 到任何 git repo;只能存於後端服務、CI Secret、或加密的設定管理工具。
- 若懷疑憑證外洩,**立即**聯絡管理員撤銷:User Token 撤銷後對應使用者所有舊 token 立即失效;SDK Key 撤銷後對應部門所有呼叫立即失效。
- 所有呼叫都會記錄一筆 `usage_logs`(模型、token、耗時、是否成功);管理員可在後台**用量紀錄**頁面查詢。
- 本平台**不會**儲存 OpenRouter 回傳的內部 metadata;但會保留請求內容(`text`、`images`、`messages`)以利稽核,請**不要**在 prompt 中夾帶敏感個資。
- **附件保存(v2.2.1 起變更)**:圖片與檔案(`files`)的內容存放於公司自有 AWS S3(private,不對外公開),用量紀錄本身只留物件位置;`file_data` 的 base64 內容**任何情況下都不會寫入用量紀錄**。政策全文見 §11。

---

## 11. 附件儲存與保存政策(v2.2.1)

v2.2.1 起,請求中夾帶的圖片與檔案改存**公司自有 AWS S3**,用量紀錄(`usage_logs.request_content`)只留物件位置。本節說明這對呼叫端與管理端各代表什麼。

### 11.1 對呼叫端:**契約不變,零改動**

- `POST /api/v1/model/chat`、`POST /api/v1/model/chat/stream` 與 deprecated alias `POST /api/v1/model/openrouter/chat` 的 **request / response schema 完全不變**。
- 呼叫端**仍可照舊送 base64 data URI**(`images` / `files.file_data` / `messages` 的 `image_url` 與 `file` part),**不需要**改任何 SDK 端程式碼、不需要改送遠端 URL、無新增必填欄位。
- **送給模型的內容也不變**:平台轉送給下游模型的請求內容與 v2.2.0 **完全相同**(圖片仍為原本的 base64 或原始 URL、`file_data` 照舊),已由回歸測試逐欄驗證。因此**模型回應品質不受本版影響**,無須擔心「換了圖片傳法導致輸出劣化」。
- 本版改變的**只有平台後端寫進用量紀錄的儲存形式**。

### 11.2 附件存放位置與取用方式

- 上傳的圖片 / 檔案存放於**公司自有 AWS S3**,物件一律 **private,不對外公開**,無公開網址、無 CDN。
- 需要檢視時(管理端用量明細頁),一律透過後端**當場簽發的短期連結**取得,**預設有效期 15 分鐘**;連結過期即失效,需重新開啟頁面取得新連結。
- 呼叫端原本就送**遠端 `https://` URL** 的附件,平台**原樣保留該 URL、不代抓**,可讀性仍取決於該外部站台。

### 11.3 檔案(PDF 等)自 v2.2.1 起才留存內容

- v2.2.1 之前,`files` 的用量紀錄**只有檔名、沒有檔案內容**。
- **自 v2.2.1 起才開始留存檔案內容**;此為新功能,**只對新請求生效**——本版之前的歷史紀錄**不會、也無法**補上內容。
- 圖片內容則自始即有留存,本版只是換了存放位置。
- 本項為平台端設定,由管理員啟用物件儲存後生效;未啟用時維持 v2.2.0 行為(圖片原樣快照、檔案僅記檔名)。

### 11.4 管理端可見的行為變更

- 用量明細 API 回吐的 `request_content` 中,**圖片元素的語意由「base64 data URI 或遠端 URL」變更為「可直接顯示的短期 URL」**;檔案元素則由「只有 `filename`」變成「`filename` + 可開啟的短期 URL」。
- 這是**管理端可見的行為變更**;SDK 呼叫端的 request / response 不受影響(§11.1)。
- 歷史紀錄在遷移完成前新舊形態並存,明細頁對兩種形態皆可正常顯示。

### 11.5 S3 故障不影響代理可用性(best-effort)

- 附件上傳採 **best-effort**:S3 故障 / 逾時**不會**讓任何代理請求失敗——下游照常呼叫、回應照常返還、用量照常記帳。
- 失敗時**不會**退回把 base64 寫進用量紀錄,而是在該筆紀錄中標記「此附件未留存」並保留大小 / 型別等資訊,同時落結構化 log 供追查。
- 也就是說,最壞情況只是**該筆紀錄的附件內容沒留存**,對外行為完全正常。

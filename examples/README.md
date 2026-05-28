# Examples · SDK 使用者範例

## sdk_example.py · Python (httpx) 最小可用範例

一支 ~80 行的 Python 腳本,示範如何帶 3 個 header 呼叫代理端點。
可直接複製到下游使用者的專案改造使用。

完整串接說明請見 [`docs/INTEGRATION.md`](../docs/INTEGRATION.md)。

### 1. 安裝依賴

```bash
pip install httpx
```

### 2. 設定環境變數

| 變數 | 必填 | 說明 |
| --- | --- | --- |
| `DFOR_API_BASE` | 否 | 代理端 base URL,預設 `http://localhost:8800` |
| `DFOR_SDK_KEY` | 是 | admin 發放的 `X-SDK-Key` 明文 |
| `DFOR_USER_TOKEN` | 是 | admin 發放的 `X-User-Token` 加密字串 |
| `DFOR_PROJECT_CODE` | 是 | 後台「專案管理」頁顯示的「代碼」欄 |
| `DFOR_MODEL` | 否 | 模型 id,預設 `openai/gpt-4o-mini` |

**PowerShell:**

```powershell
$env:DFOR_API_BASE      = "http://localhost:8800"
$env:DFOR_SDK_KEY       = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:DFOR_USER_TOKEN    = "<admin 發放的 User Token>"
$env:DFOR_PROJECT_CODE  = "53354736136491008"
```

**Bash / zsh:**

```bash
export DFOR_API_BASE="http://localhost:8800"
export DFOR_SDK_KEY="ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export DFOR_USER_TOKEN="<admin 發放的 User Token>"
export DFOR_PROJECT_CODE="53354736136491008"
```

### 3. 執行

```bash
# 使用預設 prompt(「用一句話介紹台灣」)
python examples/sdk_example.py

# 自訂 prompt
python examples/sdk_example.py "你好,介紹一下你自己"
```

成功時印模型回應與 token 用量;失敗時印 HTTP code 與後端 detail(對照 [`docs/INTEGRATION.md` §8 錯誤碼](../docs/INTEGRATION.md))。

### 安全注意事項

- **不要**把 `DFOR_SDK_KEY` / `DFOR_USER_TOKEN` 寫死於程式碼或 commit 到 git;只能存於後端服務、CI Secret 或加密設定管理工具
- 若懷疑憑證外洩,立即聯絡管理員撤銷

# 03-passwords-and-pii — 密碼 / PII

> **何時讀**:處理使用者資料 / PII 才讀。
>
> **本專案密碼雜湊主路徑為 argon2id(`argon2-cffi`)**,非 HE 模板預設的 bcrypt;憑證性亂數(SDK Key / User Token secret)用 `secrets` 模組。

- 密碼**必** `argon2-cffi` 的 **argon2id**(本專案標準);**禁** bcrypt 以外的弱演算法(md5 / sha1 / 明文)。HE 模板允許 bcrypt,本專案統一收斂為 argon2id。
- argon2id 為 CPU 密集,在 async 上下文**必** `await asyncio.to_thread(...)` 包裝(見 `03-backend/03-async-and-tx.md`);`core/security.py` 應同時提供同步 + `*_async` 版。
- 不可逆雜湊欄位(argon2id hash 等)應與 PII 隔離(獨立 credential 表 / 欄位);明文密碼**禁**落地、**禁**入 log。
- SDK Key / User Token 等**密碼性質憑證**:secret 部分以 `secrets.token_hex` / `secrets.token_urlsafe` 產生,DB 僅存 argon2id hash + 公開 prefix;**禁**用可預測來源(見 `90-third-party-service/50-openrouter.md § 3`、`04-databases/90-project-database.md § 7 Snowflake`)。
- 對稱加密欄位(OpenRouter Key / User Token payload):**AES-256-GCM**(`cryptography`),金鑰由 `ENCRYPTION_KEY` env 注入,**禁**入版控。
- PII 欄位 schema 加 `comment="PII"` 或 `-- PII`。

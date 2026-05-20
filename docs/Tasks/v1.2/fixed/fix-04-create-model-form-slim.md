# Fix 04 · 新增本地模型表單精簡

## 問題

`/admin/models` 的「新增本地模型」Dialog 表單過長,且夾雜大量說明文字。

## 調整

移除冗餘文字:

- 頂部藍色說明框(provider=internal 用途說明)
- Model Key 下方格式提示文字(placeholder 已示範格式)
- 底部速率限制警告(⚠ 速率限制屬 Server 層級⋯)

欄位改雙欄排列縮短高度:

| 列 | 內容 |
| --- | --- |
| 1 | Model Key（整列) |
| 2 | 名稱 + 分級(雙欄) |
| 3 | Context Length + Modality(雙欄) |
| 4 | 說明（整列) |

## 交付物

- 修改:`frontend/src/app/(main)/admin/models/page.tsx`

"use client";

// 全域錯誤邊界：連 root layout 本身都壞掉時使用
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="zh-TW">
      <body>
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            alignItems: "center",
            justifyContent: "center",
            padding: 32,
            textAlign: "center",
            fontFamily: "system-ui, sans-serif",
          }}
        >
          <h2 style={{ fontSize: 20, fontWeight: 600 }}>系統錯誤</h2>
          <p style={{ color: "#888" }}>{error.message || "請稍後再試。"}</p>
          <button
            onClick={() => reset()}
            style={{
              padding: "8px 16px",
              borderRadius: 12,
              border: "1px solid #ccc",
              cursor: "pointer",
            }}
          >
            重新載入
          </button>
        </div>
      </body>
    </html>
  );
}

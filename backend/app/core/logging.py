import contextvars
import logging
import sys

from app.core.config import Settings, get_settings

_CONSOLE_FORMAT = "%(asctime)s %(levelname)s [%(name)s] [req:%(request_id)s] %(message)s"

# log_to_seq() 回傳的 SeqLogHandler;關閉前用來 flush 緩衝。未啟用 Seq 時為 None。
_seq_handler: logging.Handler | None = None

# 每個請求的關聯 ID;由 main.py 的 middleware 於請求進入時 set,離開時 reset。
# 非請求情境(啟動 Seed、背景 flush)取得預設值 "-"。
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    """將當前請求的 request_id 注入每筆 log record。

    掛在 handler 上(非 logger),確保子 logger 傳上來的 record 也會被填值;
    console 走 `%(request_id)s` 格式,Seq 走 record 屬性(support_extra_properties)。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def _install_request_id_filter() -> None:
    flt = _RequestIdFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(flt)


def configure_logging() -> None:
    """設定全域 logging。

    未設定 `SEQ_INGESTION_URL` 時只走 console(本機開發 / CI 不對外連線);
    有設定則額外掛上 Seq handler,現有 `logging` 呼叫會一併送往 Seq。
    """
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    seq_url = settings.SEQ_INGESTION_URL.strip()
    if not seq_url:
        logging.basicConfig(level=level, format=_CONSOLE_FORMAT, force=True)
        _install_request_id_filter()
        return

    _configure_with_seq(settings, level, seq_url)


def _console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    return handler


def _configure_with_seq(settings: Settings, level: int, seq_url: str) -> None:
    global _seq_handler

    try:
        import seqlog
    except ImportError:
        logging.basicConfig(level=level, format=_CONSOLE_FORMAT, force=True)
        _install_request_id_filter()
        logging.getLogger(__name__).warning(
            "SEQ_INGESTION_URL 已設定,但未安裝 seqlog 套件;改用 console。"
        )
        return

    # log_to_seq 內部以 basicConfig 設定 root logger:
    # - force=True 確保 handler 確實掛上(即使 root 已有 handler,basicConfig 預設會 no-op)
    # - additional_handlers 一併保留 console 輸出
    # SeqLogHandler.emit 僅將 record 入佇列,HTTP POST 在背景執行緒處理,不阻塞 event loop。
    _seq_handler = seqlog.log_to_seq(
        server_url=seq_url,
        api_key=settings.SEQ_API_KEY or None,
        level=level,
        batch_size=10,
        auto_flush_timeout=2,
        additional_handlers=[_console_handler()],
        support_extra_properties=True,
        ignore_seq_submission_errors=True,
        force=True,
    )
    seqlog.set_global_log_properties(
        Application=settings.APP_NAME,
        Environment=settings.APP_ENV,
    )
    _install_request_id_filter()
    logging.getLogger(__name__).info("Seq log 推送已啟用 → %s", seq_url)


def flush_logging() -> None:
    """服務關閉前主動 flush,確保 Seq 緩衝中的 log 全數送出。"""
    if _seq_handler is None:
        return
    try:
        _seq_handler.flush()
    except Exception:  # noqa: BLE001
        print("Seq log flush 失敗", file=sys.stderr)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

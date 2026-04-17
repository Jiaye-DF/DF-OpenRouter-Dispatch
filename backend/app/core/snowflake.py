"""Twitter Snowflake ID 產生器。

64-bit 結構：
- 41 bits: milliseconds since custom epoch (足夠 ~69 年)
- 10 bits: worker id (0–1023)
- 12 bits: sequence per ms (0–4095)

輸出為十進位字串（最多 19 字，符合 VARCHAR(64) 欄位）。
"""

import os
import threading
import time

# 自訂 epoch：2026-01-01T00:00:00Z
_EPOCH_MS = 1767225600000
_WORKER_BITS = 10
_SEQ_BITS = 12
_MAX_SEQ = (1 << _SEQ_BITS) - 1
_MAX_WORKER = (1 << _WORKER_BITS) - 1

try:
    _worker_id = int(os.environ.get("SNOWFLAKE_WORKER_ID", "1")) & _MAX_WORKER
except ValueError:
    _worker_id = 1

_lock = threading.Lock()
_last_ms = -1
_seq = 0


def _now_ms() -> int:
    return int(time.time() * 1000)


def generate_id() -> int:
    """產出一個 64-bit Snowflake int。"""
    global _last_ms, _seq
    with _lock:
        now = _now_ms()
        if now == _last_ms:
            _seq = (_seq + 1) & _MAX_SEQ
            if _seq == 0:
                while now <= _last_ms:
                    now = _now_ms()
                _last_ms = now
        else:
            _seq = 0
            _last_ms = now
        ts = (now - _EPOCH_MS) & ((1 << 41) - 1)
        return (ts << (_WORKER_BITS + _SEQ_BITS)) | (_worker_id << _SEQ_BITS) | _seq


def generate_id_str() -> str:
    return str(generate_id())

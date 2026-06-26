"""Broker + Result Backend 定義(taskiq + Redis)。

- broker:任務的「傳輸層」,發送端 .kiq 把序列化訊息丟進來、worker 從這裡拉。
- result backend:任務回傳值 / 例外的「結果倉」,發送端用 task_id 來這裡查結果。
- 兩者本版都用 Redis(不同 db);未來換 RabbitMQ 只動 broker 這一行,task 與呼叫端不變。

連線採 lazy:本模組 import 與 broker 建構**不**發起任何 Redis 連線;
實際連線於 worker 啟動(`broker.startup()`)或首次 `.kiq` 派發時才建立。

URL 由環境變數注入(對齊 `Settings.TASKIQ_BROKER_URL` / `TASKIQ_RESULT_BACKEND_URL`,
預設值兩處一致),禁硬編機密。此處直讀 `os.environ` 而非 `get_settings()`,
是為了讓 broker 可在「未備妥完整 .env(DB / JWT 等必填欄位)」的 worker / CI
情境下也能被 import,不被無關欄位的驗證牽連。
"""

import os

from taskiq.middlewares import SimpleRetryMiddleware
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

# 預設值與 app/core/config.py 的 Settings 對應欄位逐字一致。
BROKER_URL = os.environ.get("TASKIQ_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND_URL = os.environ.get("TASKIQ_RESULT_BACKEND_URL", "redis://localhost:6379/1")

# 連線參數(經 ListQueueBroker / RedisAsyncResultBackend 的 **connection_kwargs
# 直透傳給 redis-py 的 BlockingConnectionPool.from_url)。
# ⚠ ListQueueBroker.listen() 以「無 timeout」的 BRPOP 阻塞讀拉任務
# (taskiq_redis redis_broker.py:`redis_conn.brpop(self.queue_name)`,server 端永久阻塞);
# 若 client 端 socket_timeout 有值,該阻塞讀會在 socket_timeout 到點時被
# `redis.exceptions.TimeoutError: Timeout reading from ...` 打斷,worker 子進程被
# process-manager 反覆 reload。故 worker 端的阻塞讀必須 socket_timeout=None;
# 改以 TCP keepalive + 週期 health check 偵測真正斷線的連線。
broker = (
    ListQueueBroker(
        BROKER_URL,
        socket_timeout=None,
        socket_keepalive=True,
        health_check_interval=30,
    )
    .with_result_backend(
        RedisAsyncResultBackend(
            RESULT_BACKEND_URL,
            socket_timeout=None,
            socket_keepalive=True,
            health_check_interval=30,
        )
    )
    # 任務失敗自動重試(對應 AI_EVAL_TASK_MAX_RETRIES);
    # 缺此 middleware,task 上的 retry_on_error 標籤不會生效(task-106 依賴)。
    .with_middlewares(SimpleRetryMiddleware())
)

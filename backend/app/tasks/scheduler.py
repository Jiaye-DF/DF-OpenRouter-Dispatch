"""TaskiqScheduler 進程入口(task-106;對齊 propose-v2.0.1 §4)。

啟動:`taskiq scheduler app.tasks.scheduler:scheduler`

scheduler 不執行任務,只負責「到點把帶 schedule label 的 task 送進 broker」,
真正執行的是 worker(兩者分開進程,各自常駐)。本版唯一排程任務為
`dispatch_unevaluated`(於 `app.tasks.ai_model_eval` 以
`@broker.task(schedule=[{"interval": AI_EVAL_BEAT_INTERVAL_SECONDS}])` 標註),
由 `LabelScheduleSource` 依其 interval 週期觸發。
"""

from __future__ import annotations

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

import app.tasks.ai_model_eval  # noqa: F401  載入帶 schedule label 的 task,scheduler 才看得到排程
from app.tasks.broker import broker

scheduler = TaskiqScheduler(broker=broker, sources=[LabelScheduleSource(broker)])

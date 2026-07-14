"""`request_snapshot` 正規化層 + 三個讀取端的雙快照形狀迴歸測試(v2.1.3)。

v2.1.2 開放 messages 直傳後,`usage_logs.request_content` 出現第二種形狀,但 AI 評估 /
重跑 / 總覽三個讀取端仍寫死 `request_content["text"]`,導致 messages 模式的紀錄被當成
「空輸入」:裁判對空白提問評分、challenger 拿空 prompt 真實計費呼叫。本檔鎖住修正。
"""

from app.services import request_snapshot
from app.services.ai_model_eval_prompt import _render_input
from app.services.ai_model_eval_rerun_result import _input_text_of

# ── fixtures:兩種快照形狀 ──

SINGLE_TURN = {
    "model": "openai/gpt-4o",
    "text": "幫我摘要這份合約",
    "images": ["data:image/png;base64,AAAA"],
    "files": ["contract.pdf"],
}

MESSAGES = {
    "model": "openai/gpt-4o",
    "messages": [
        {"role": "system", "content": "你是法務助理"},
        {"role": "user", "content": "幫我摘要這份合約"},
        {"role": "assistant", "content": "好的,重點如下…"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "第三條再展開"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                {"type": "file", "file": {"filename": "contract.pdf"}},
            ],
        },
    ],
    "temperature": 0.2,
}


# ── is_messages_snapshot / messages_of ──


def test_is_messages_snapshot_discriminates_both_shapes():
    assert request_snapshot.is_messages_snapshot(MESSAGES) is True
    assert request_snapshot.is_messages_snapshot(SINGLE_TURN) is False
    assert request_snapshot.is_messages_snapshot(None) is False
    assert request_snapshot.is_messages_snapshot({}) is False


def test_messages_of_normalizes_single_turn_to_one_user_message():
    """單輪快照 → 等價的單則 user 訊息(text / images / files 併為 content parts)。"""
    msgs = request_snapshot.messages_of(SINGLE_TURN)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == [
        {"type": "text", "text": "幫我摘要這份合約"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        {"type": "file", "file": {"filename": "contract.pdf"}},
    ]


def test_messages_of_passes_messages_mode_through():
    msgs = request_snapshot.messages_of(MESSAGES)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]


def test_messages_of_empty_inputs():
    assert request_snapshot.messages_of(None) == []
    assert request_snapshot.messages_of({}) == []
    assert request_snapshot.messages_of({"model": "m", "text": None, "images": []}) == []


# ── input_text_of:v2.1.2 的核心缺陷點 ──


def test_input_text_of_single_turn_matches_legacy_text_field():
    assert _input_text_of(SINGLE_TURN) == "幫我摘要這份合約"


def test_input_text_of_messages_takes_last_user_message_not_none():
    """回歸:messages 模式過去回 None(無 text 鍵)→ 前端「任務輸入」整欄空白。"""
    assert _input_text_of(MESSAGES) == "第三條再展開"


def test_input_text_of_missing_or_empty():
    assert _input_text_of(None) is None
    assert _input_text_of({"model": "m"}) is None
    assert _input_text_of({"model": "m", "text": ""}) is None
    # 只有 assistant 訊息(無 user)→ 無任務輸入
    assert _input_text_of({"messages": [{"role": "assistant", "content": "hi"}]}) is None


# ── replay_messages:challenger 重跑 payload ──


def test_replay_messages_single_turn_keeps_v2_1_1_behaviour():
    """單輪重跑行為不變:只重放 text(不含圖片 / 檔案),避免擴大既有重跑成本。"""
    assert request_snapshot.replay_messages(SINGLE_TURN) == [
        {"role": "user", "content": "幫我摘要這份合約"}
    ]


def test_replay_messages_messages_mode_replays_full_conversation():
    """回歸:messages 模式過去重放成 content=""(拿空 prompt 真實計費呼叫 challenger)。"""
    replayed = request_snapshot.replay_messages(MESSAGES)
    assert [m["role"] for m in replayed] == ["system", "user", "assistant", "user"]
    assert replayed[0]["content"] == "你是法務助理"
    # file part 快照無 file_data,無法重放 → 剔除;text / image_url 保留
    last_parts = replayed[-1]["content"]
    assert [p["type"] for p in last_parts] == ["text", "image_url"]


def test_replay_messages_never_returns_empty_list():
    assert request_snapshot.replay_messages(None) == [{"role": "user", "content": ""}]
    assert request_snapshot.replay_messages({"messages": []}) == [{"role": "user", "content": ""}]


# ── _render_input:裁判 prompt(judge + discriminator 共用同一實作)──


def test_render_input_single_turn_output_unchanged():
    """單輪渲染逐字不變(既有裁判 prompt 行為不得因本次修正而漂移)。"""
    rendered = _render_input(SINGLE_TURN, lambda t: t)
    assert rendered == (
        "文字輸入:\n幫我摘要這份合約\n圖片數量:1\n附帶檔案數量:1"
    )


def test_render_input_messages_exposes_every_turn():
    """回歸:messages 模式過去渲染成「文字輸入:(無)」→ 裁判對空白提問評分。"""
    rendered = _render_input(MESSAGES, lambda t: t)
    assert "(無)" not in rendered
    assert "共 4 則" in rendered
    assert "你是法務助理" in rendered
    assert "幫我摘要這份合約" in rendered
    assert "好的,重點如下…" in rendered
    assert "第三條再展開" in rendered
    assert "圖片數量:1" in rendered
    assert "附帶檔案數量:1" in rendered


def test_render_input_messages_applies_text_masker_to_every_turn():
    """PII 遮罩 hook 必須套用到每一則,不可只遮第一則。"""
    rendered = _render_input(MESSAGES, lambda t: "[遮罩]")
    assert "你是法務助理" not in rendered
    assert "第三條再展開" not in rendered
    assert rendered.count("[遮罩]") == 4


def test_render_input_unknown_role_does_not_crash():
    """未來若開放 tool role,舊裁判鏈不得因未知 role 炸掉。"""
    rendered = _render_input(
        {"messages": [{"role": "tool", "content": "工具回傳"}]}, lambda t: t
    )
    assert "tool" in rendered
    assert "工具回傳" in rendered

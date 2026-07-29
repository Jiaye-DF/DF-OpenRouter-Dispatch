"""`request_snapshot` 對 v2.2.1 第三種附件形態(S3 物件 key / upload_failed)的迴歸測試。

v2.2.1 把附件從「base64 存 JSONB」改成「S3 存物件、DB 只留路徑」,`request_content` 內的
附件值因此出現新形狀(產出端見 `services/attachment.py`),其中單輪 `images[i]` 在上傳失敗
時**由字串變成 dict**。所有讀取端(明細頁 / AI 評估 / 重跑)都經本正規化層,只要這裡把新
形態濾成「無附件」,就會複製一次 v2.1.2 的靜默失效(判分全錯且不報錯)。本檔鎖住這件事。

遷移期新舊並存,因此每組斷言都同時涵蓋「舊 data URI」與「新形態」。
"""

from pathlib import Path

from app.services import request_snapshot

# ── fixtures:同一份輸入的四種快照結果(對齊 attachment.build_attachment_snapshot)──

TEXT = "幫我摘要這份合約"
DATA_URI = "data:image/png;base64,AAAA"
IMAGE_KEY = "dev/chat/2026/07/29/req-uid/0-0123456789abcdef.png"
FILE_KEY = "dev/chat/2026/07/29/req-uid/1-fedcba9876543210.pdf"
REMOTE_URL = "https://cdn.example.com/a.png"

IMAGE_FAILED: dict[str, object] = {
    "type": "image_url",
    "upload_failed": True,
    "mime": "image/png",
    "bytes": 3,
    "sha256": "ab" * 32,
    "reason": "s3_upload_failed",
}
FILE_FAILED: dict[str, object] = {
    "type": "file",
    "file": {
        "filename": "contract.pdf",
        "upload_failed": True,
        "mime": "application/pdf",
        "bytes": 4,
        "sha256": "cd" * 32,
        "reason": "s3_upload_failed",
    },
}
FILE_OK: dict[str, object] = {
    "type": "file",
    "file": {"filename": "contract.pdf", "key": FILE_KEY},
}

IMAGE_PART_S3: dict[str, object] = {"type": "image_url", "image_url": {"url": IMAGE_KEY}}
IMAGE_PART_LEGACY: dict[str, object] = {"type": "image_url", "image_url": {"url": DATA_URI}}
IMAGE_PART_REMOTE: dict[str, object] = {"type": "image_url", "image_url": {"url": REMOTE_URL}}
FILE_PART_LEGACY: dict[str, object] = {"type": "file", "file": {"filename": "contract.pdf"}}

# 單輪模式(v2.2.0 舊形狀 / S3 成功 / 上傳失敗 / 遠端 URL)
SINGLE_LEGACY = {"model": "m", "text": TEXT, "images": [DATA_URI], "files": ["contract.pdf"]}
SINGLE_S3 = {"model": "m", "text": TEXT, "images": [IMAGE_KEY], "files": [FILE_OK]}
SINGLE_FAILED = {"model": "m", "text": TEXT, "images": [IMAGE_FAILED], "files": [FILE_FAILED]}
SINGLE_REMOTE = {"model": "m", "text": TEXT, "images": [REMOTE_URL], "files": []}


def _messages_snapshot(image: dict[str, object], file: dict[str, object]) -> dict[str, object]:
    return {
        "model": "m",
        "messages": [
            {"role": "system", "content": "你是法務助理"},
            {"role": "user", "content": [{"type": "text", "text": TEXT}, image, file]},
        ],
    }


MESSAGES_LEGACY = _messages_snapshot(IMAGE_PART_LEGACY, FILE_PART_LEGACY)
MESSAGES_S3 = _messages_snapshot(IMAGE_PART_S3, FILE_OK)
MESSAGES_FAILED = _messages_snapshot(IMAGE_FAILED, FILE_FAILED)


# ── attachment_form / attachment_ref_of / is_upload_failed:四態判別 ──


def test_attachment_form_covers_four_states():
    assert request_snapshot.attachment_form(DATA_URI) == "data_uri"
    assert request_snapshot.attachment_form(IMAGE_KEY) == "object_key"
    assert request_snapshot.attachment_form(REMOTE_URL) == "remote_url"
    assert request_snapshot.attachment_form(IMAGE_FAILED) == "upload_failed"
    assert request_snapshot.attachment_form(FILE_FAILED) == "upload_failed"


def test_attachment_form_of_parts():
    assert request_snapshot.attachment_form(IMAGE_PART_S3) == "object_key"
    assert request_snapshot.attachment_form(IMAGE_PART_LEGACY) == "data_uri"
    assert request_snapshot.attachment_form(IMAGE_PART_REMOTE) == "remote_url"
    assert request_snapshot.attachment_form(FILE_OK) == "object_key"
    # v2.2.0 的 file 快照只有檔名,沒有任何內容參照
    assert request_snapshot.attachment_form(FILE_PART_LEGACY) == "empty"
    assert request_snapshot.attachment_form("") == "empty"
    assert request_snapshot.attachment_form(None) == "empty"


def test_attachment_ref_of_extracts_key_or_url():
    assert request_snapshot.attachment_ref_of(IMAGE_KEY) == IMAGE_KEY
    assert request_snapshot.attachment_ref_of(IMAGE_PART_S3) == IMAGE_KEY
    assert request_snapshot.attachment_ref_of(FILE_OK) == FILE_KEY
    assert request_snapshot.attachment_ref_of(REMOTE_URL) == REMOTE_URL
    # 失敗標記與「只有檔名」皆無內容可取 → None(但不代表沒有附件,見計數測試)
    assert request_snapshot.attachment_ref_of(IMAGE_FAILED) is None
    assert request_snapshot.attachment_ref_of(FILE_FAILED) is None
    assert request_snapshot.attachment_ref_of(FILE_PART_LEGACY) is None


def test_is_upload_failed_discriminates_marker_from_normal_value():
    assert request_snapshot.is_upload_failed(IMAGE_FAILED) is True
    assert request_snapshot.is_upload_failed(FILE_FAILED) is True
    assert request_snapshot.is_upload_failed(FILE_OK) is False
    assert request_snapshot.is_upload_failed(IMAGE_KEY) is False
    assert request_snapshot.is_upload_failed(None) is False


# ── messages_of:單輪快照的新形態不得被吞掉 ──


def test_messages_of_single_turn_s3_key_yields_one_image_part():
    """S3 路徑仍是「有內容的圖片」:一則 user 訊息、1 個 image part、url 原樣保留 key。"""
    msgs = request_snapshot.messages_of(SINGLE_S3)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == [
        {"type": "text", "text": TEXT},
        {"type": "image_url", "image_url": {"url": IMAGE_KEY}},
        FILE_OK,
    ]


def test_messages_of_single_turn_upload_failed_keeps_marker_as_part():
    """失敗標記(dict)不得被塞進 `image_url.url`,也不得被丟掉。"""
    content = request_snapshot.messages_of(SINGLE_FAILED)[0]["content"]
    assert content == [{"type": "text", "text": TEXT}, IMAGE_FAILED, FILE_FAILED]


def test_messages_of_single_turn_legacy_shape_unchanged():
    """回歸:舊 data URI / 純檔名形狀逐字不變(遷移期新舊並存)。"""
    assert request_snapshot.messages_of(SINGLE_LEGACY) == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": TEXT},
                {"type": "image_url", "image_url": {"url": DATA_URI}},
                {"type": "file", "file": {"filename": "contract.pdf"}},
            ],
        }
    ]


def test_messages_of_messages_mode_keeps_s3_and_failed_parts():
    """messages 模式:S3 路徑與失敗標記皆原樣保留,不被過濾。"""
    for snapshot in (MESSAGES_S3, MESSAGES_FAILED):
        msgs = request_snapshot.messages_of(snapshot)
        assert [m["role"] for m in msgs] == ["system", "user"]
        assert len(msgs[1]["content"]) == 3
    assert request_snapshot.messages_of(MESSAGES_S3)[1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": IMAGE_KEY},
    }
    assert request_snapshot.messages_of(MESSAGES_FAILED)[1]["content"][1] == IMAGE_FAILED


# ── as_parts / count_parts:附件「存在」的計數不因形態改變 ──


def test_count_parts_counts_every_attachment_form():
    """三種形態的附件數量一致 —— 失敗標記代表「有附件、內容不可用」,仍計數為 1。"""
    for snapshot in (SINGLE_LEGACY, SINGLE_S3, SINGLE_FAILED):
        content = request_snapshot.messages_of(snapshot)[0]["content"]
        assert request_snapshot.count_parts(content, "image_url") == 1
        assert request_snapshot.count_parts(content, "file") == 1
        assert request_snapshot.count_parts(content, "text") == 1

    for snapshot in (MESSAGES_LEGACY, MESSAGES_S3, MESSAGES_FAILED):
        content = request_snapshot.messages_of(snapshot)[1]["content"]
        assert request_snapshot.count_parts(content, "image_url") == 1
        assert request_snapshot.count_parts(content, "file") == 1


def test_as_parts_does_not_drop_new_forms():
    for snapshot in (SINGLE_S3, SINGLE_FAILED, MESSAGES_S3, MESSAGES_FAILED):
        msgs = request_snapshot.messages_of(snapshot)
        assert len(request_snapshot.as_parts(msgs[-1]["content"])) == 3


# ── text_of / input_text_of:文字路徑不受附件形態影響 ──


def test_text_paths_identical_across_all_attachment_forms():
    for snapshot in (SINGLE_LEGACY, SINGLE_S3, SINGLE_FAILED, SINGLE_REMOTE):
        content = request_snapshot.messages_of(snapshot)[0]["content"]
        assert request_snapshot.input_text_of(snapshot) == TEXT
        assert request_snapshot.text_of(content) == TEXT

    for snapshot in (MESSAGES_LEGACY, MESSAGES_S3, MESSAGES_FAILED):
        content = request_snapshot.messages_of(snapshot)[1]["content"]
        assert request_snapshot.input_text_of(snapshot) == TEXT
        assert request_snapshot.text_of(content) == TEXT


# ── replay_messages:不擴大重跑行為,但不得畸形、不得回空 ──


def test_replay_messages_single_turn_unchanged_for_every_form():
    """單輪仍只重放 text(v2.1.1 行為),附件形態不影響結果。"""
    for snapshot in (SINGLE_LEGACY, SINGLE_S3, SINGLE_FAILED, SINGLE_REMOTE):
        assert request_snapshot.replay_messages(snapshot) == [{"role": "user", "content": TEXT}]


def test_replay_messages_legacy_data_uri_still_replayed():
    """回歸:舊 data URI 圖片照舊重放(file part 照舊剔除)。"""
    parts = request_snapshot.replay_messages(MESSAGES_LEGACY)[-1]["content"]
    assert parts == [
        {"type": "text", "text": TEXT},
        {"type": "image_url", "image_url": {"url": DATA_URI}},
    ]


def test_replay_messages_drops_object_key_and_failed_marker():
    """S3 路徑 / 失敗標記送下游只會是畸形 payload(非 URL 字串 / 一坨 metadata)→ 剔除。

    presign 需要 I/O,不屬本純函式層;本版不擴大重跑行為。
    """
    for snapshot in (MESSAGES_S3, MESSAGES_FAILED):
        replayed = request_snapshot.replay_messages(snapshot)
        assert [m["role"] for m in replayed] == ["system", "user"]
        assert replayed[-1]["content"] == [{"type": "text", "text": TEXT}]
        # 畸形防線:留下的 part 一律是白名單型別,且沒有任何 upload_failed metadata
        for part in replayed[-1]["content"]:
            assert part["type"] in {"text", "image_url"}
            assert "upload_failed" not in part


def test_replay_messages_remote_url_part_still_replayed():
    """遠端 URL(§D.2 原樣保留)仍可直接送下游。"""
    snapshot = {"messages": [{"role": "user", "content": [IMAGE_PART_REMOTE]}]}
    assert request_snapshot.replay_messages(snapshot) == [
        {"role": "user", "content": [IMAGE_PART_REMOTE]}
    ]


def test_replay_messages_never_empty_when_only_unreplayable_attachments():
    """整則只有 S3 圖片 / 失敗標記 → 不得回 `[]`,退回既有的單一則空 user 訊息。"""
    for part in (IMAGE_PART_S3, IMAGE_FAILED, FILE_FAILED):
        snapshot = {"messages": [{"role": "user", "content": [part]}]}
        assert request_snapshot.replay_messages(snapshot) == [{"role": "user", "content": ""}]


# ── 純函式約束(task-526 硬規則:本層禁 import 任何 app 模組 / 禁 I/O)──


def test_module_imports_no_app_modules():
    """機械鎖:一旦有人在本層 import S3 client 或其他 service,循環相依與 I/O 就跟著進來。"""
    source = Path(request_snapshot.__file__).read_text(encoding="utf-8")
    offenders = [
        line
        for line in source.splitlines()
        if line.startswith(("from app.", "import app.", "from app ", "import app"))
    ]
    assert offenders == []

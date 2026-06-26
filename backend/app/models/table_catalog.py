from uuid import UUID

from sqlalchemy import BigInteger, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TableCatalog(Base, TimestampMixin):
    """資料表名稱對照字典:實體表名 → 中文顯示名(+ 分組 / 說明)。

    人類可維護的資料字典(未來可接 UI / 給前端做欄位中文化下拉、報表標題);
    與 DB `COMMENT` 同源互補。沿用專案慣例:pid BIGSERIAL PK +
    table_catalog_uid UUID unique + 必備四欄 + set_updated_at trigger;
    `table_name` UNIQUE,新表須自我登錄一筆(Design-Base § 3.5)。

    `comment=` 與 migration 0021 逐字一致(雙軌一致,避免 autogenerate 誤判)。
    """

    __tablename__ = "table_catalog"
    __table_args__ = {
        "comment": (
            "資料表名稱對照字典:實體表名 → 中文顯示名 | "
            "data dictionary of table names"
        )
    }

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    table_catalog_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    table_name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="實體表名(如 users) | physical table name",
    )
    display_name_zh: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="中文顯示名(如 使用者) | display name (zh)",
    )
    category: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="分組(帳號/金鑰/計量/AI 分析…),利搜尋與分類 | category",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="用途說明(與該表 COMMENT ON TABLE 同源) | description",
    )
    sort_order: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="顯示排序 | display sort order",
    )

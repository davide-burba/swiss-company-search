from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ZefixCompany(Base):
    __tablename__ = "zefix_companies"

    uid: Mapped[str] = mapped_column(String(15), primary_key=True)
    org: Mapped[str] = mapped_column(Text)
    legal_name: Mapped[str] = mapped_column(Text)
    legal_form: Mapped[str] = mapped_column(String(4))
    canton: Mapped[str] = mapped_column(String(2))
    city: Mapped[str] = mapped_column(Text)
    street: Mapped[str | None] = mapped_column(Text, nullable=True)
    zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_lang: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector_section: Mapped[str | None] = mapped_column(String(1), nullable=True)
    sector_division: Mapped[str | None] = mapped_column(String(2), nullable=True)
    lat: Mapped[float | None] = mapped_column(nullable=True)
    lng: Mapped[float | None] = mapped_column(nullable=True)
    search_vector: Mapped[object | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[object | None] = mapped_column(Vector(384), nullable=True)

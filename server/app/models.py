from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.db import Base


class TrainingStatus(str, enum.Enum):
    pending = "pending"
    uploading = "uploading"
    training = "training"
    ready = "ready"
    failed = "failed"


class GenerationStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Package(Base):
    """Тарифный пакет. total_photos фиксирован, распределяется по выбранным сценам."""
    __tablename__ = "packages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    scenes_pool: Mapped[int] = mapped_column(Integer, default=10)    # сколько сцен доступно в каталоге
    max_scenes: Mapped[int] = mapped_column(Integer, default=3)      # верхняя граница выбора
    total_photos: Mapped[int] = mapped_column(Integer, default=30)   # сколько фото получит пользователь
    price_rub: Mapped[int] = mapped_column(Integer)


class Purchase(Base):
    __tablename__ = "purchases"
    # Один и тот же токен не должен начислить пакет дважды. Проверка в billing.py
    # ловит повтор запросом, но два одновременных запроса успевают проскочить мимо
    # неё — ограничение в базе закрывает эту щель.
    __table_args__ = (UniqueConstraint("provider", "provider_token", name="uq_purchase_provider_token"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id"))
    provider: Mapped[str] = mapped_column(String(32))
    provider_token: Mapped[str] = mapped_column(String(512), index=True)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scenes_selected: Mapped[dict] = mapped_column(JSON, default=list)
    photos_remaining: Mapped[int] = mapped_column(Integer, default=0)


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    status: Mapped[TrainingStatus] = mapped_column(Enum(TrainingStatus), default=TrainingStatus.pending)
    provod_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    photo_keys: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    training_id: Mapped[int] = mapped_column(ForeignKey("training_jobs.id"))
    style_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[GenerationStatus] = mapped_column(Enum(GenerationStatus), default=GenerationStatus.pending)
    provod_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result_keys: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GenerationEvent(Base):
    """Одна выданная генерация. Нужна, чтобы считать скорость расхода.

    Отдельная таблица, а не счётчик в users: счётчик отвечает «сколько всего»,
    а нам нужно «сколько за последний час» и «сколько с момента покупки» —
    на такие вопросы отвечают только события с временными метками.
    """
    __tablename__ = "generation_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True)
    scene_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

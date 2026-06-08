from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    contacts = relationship("Contact", back_populates="organisation", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organisation", cascade="all, delete-orphan")
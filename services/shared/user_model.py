"""
LoanFlow – Shared User ORM model.
Lives in `shared` so every service that maps tables with a foreign key to
`users.id` (e.g. loan_app) registers the same table in its metadata,
without importing the auth service.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime

from .database import Base
from .security import ROLE_CUSTOMER


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=ROLE_CUSTOMER)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

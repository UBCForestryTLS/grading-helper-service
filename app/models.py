"""SQLAlchemy models for the grading helper service."""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class GradingSession(Base):
    """A grading session for an assignment."""

    __tablename__ = "grading_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    canvas_course_id: Mapped[str] = mapped_column(String(50))
    canvas_assignment_id: Mapped[str] = mapped_column(String(50))
    assignment_name: Mapped[str] = mapped_column(String(255), default="")
    instructor_id: Mapped[str] = mapped_column(String(50))
    access_token: Mapped[str] = mapped_column(Text)  # Canvas OAuth token
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, grading, review, submitted

    # Relationship to submissions
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<GradingSession {self.id[:8]}... assignment={self.canvas_assignment_id}>"
        )


class Submission(Base):
    """A student submission within a grading session."""

    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("grading_sessions.id")
    )
    canvas_submission_id: Mapped[str] = mapped_column(String(50))
    canvas_user_id: Mapped[str] = mapped_column(String(50))
    student_name: Mapped[str] = mapped_column(String(255), default="")
    student_answer: Mapped[str] = mapped_column(Text)

    # AI grading results
    llm_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, default=1.0)

    # Instructor review
    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    instructor_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, graded, approved, overridden

    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship to session
    session: Mapped["GradingSession"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<Submission {self.id[:8]}... user={self.canvas_user_id}>"

from datetime import datetime,timezone

from sqlalchemy import CheckConstraint,DateTime,Index,Text
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column

def _now() ->datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class StepState(Base):
    "Current picture of one step for the learner. Overwritten as they progress."
    __tablename__='step_state'
    __table_args__ = (
        CheckConstraint("status IN ('open', 'solved', 'gave_up', 'completed')",
                        name="step_status_valid"),
    )

    course_id:Mapped[str]=mapped_column(primary_key=True)
    step_id:Mapped[str]=mapped_column(primary_key=True)
    generation:Mapped[int]=mapped_column(default=1)
    status:Mapped[str]=mapped_column(default='open')
    hints_revealed:Mapped[int]=mapped_column(default=0)
    failed_submits:Mapped[int]=mapped_column(default=0)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

class Attempt(Base):
    "Stores history of submits."

    __tablename__='attempts'
    __table_args__ = (
        Index("attempts_by_step", "course_id", "step_id", "generation"),
    )

    id:Mapped[int]=mapped_column(primary_key=True)
    course_id:Mapped[str]
    step_id:Mapped[str]
    generation:Mapped[int]
    attempt_no:Mapped[int]
    status:Mapped[str]
    passed_count:Mapped[int]
    total:Mapped[int]
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=_now)

class Draft(Base):
    "The learner's last code for a step."
    __tablename__ = "drafts"

    course_id: Mapped[str] = mapped_column(primary_key=True)
    step_id: Mapped[str] = mapped_column(primary_key=True)
    files_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
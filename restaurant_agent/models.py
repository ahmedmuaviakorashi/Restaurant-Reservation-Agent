from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Intent = Literal["make_reservation", "modify_reservation", "cancel_reservation"]


class ReservationEntities(BaseModel):
    reservation_id: int | None = None
    user_name: str | None = None
    email_id: EmailStr | None = None
    num_persons: int | None = Field(default=None, ge=1, le=20)
    reservation_type: str | None = None
    res_date: str | None = None
    res_time: str | None = None

    @field_validator("res_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from datetime import date

        date.fromisoformat(value)
        return value

    @field_validator("res_time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from datetime import time

        parsed = time.fromisoformat(value)
        return parsed.replace(second=0, microsecond=0).strftime("%H:%M")


class ParsedInput(BaseModel):
    intent: Intent | None = None
    entities: ReservationEntities = Field(default_factory=ReservationEntities)


class ConversationState(BaseModel):
    intent: Intent | None = None
    entities: ReservationEntities = Field(default_factory=ReservationEntities)
    awaiting_confirmation: bool = False
    messages: list[dict[str, str]] = Field(default_factory=list)


class Reservation(BaseModel):
    reservation_id: int
    user_name: str
    email_id: EmailStr
    num_persons: int
    reservation_type: str
    res_date: str
    res_time: str
    status: Literal["confirmed", "cancelled"]


class AgentReply(BaseModel):
    message: str
    state: ConversationState

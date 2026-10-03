from restaurant_agent.database import (
    ReservationError,
    ReservationNotFound,
    ReservationStore,
    SlotUnavailable,
)
from restaurant_agent.extraction import Extractor
from restaurant_agent.models import AgentReply, ConversationState, ReservationEntities


class ReservationAgent:
    required_fields = (
        ("user_name", "What name should I use for the reservation?"),
        ("email_id", "What email address should I attach to the reservation?"),
        ("num_persons", "How many people will be attending?"),
        ("res_date", "What date would you like? Please use YYYY-MM-DD."),
        ("res_time", "What time would you like? Please use 24-hour HH:MM format."),
        ("reservation_type", "Is this for dinner, a meeting, a party, or another occasion?"),
    )

    def __init__(self, store: ReservationStore, extractor: Extractor) -> None:
        self.store = store
        self.extractor = extractor

    def respond(self, message: str, state: ConversationState | None = None) -> AgentReply:
        current = state or ConversationState()
        current.messages.append({"role": "user", "content": message})
        if current.awaiting_confirmation:
            return self._confirm(message, current)

        try:
            parsed = self.extractor.extract(message, current)
        except ValueError:
            return self._finish(
                "I couldn't validate those details. Check the email, party size, date, and time.",
                current,
            )
        current.intent = parsed.intent or current.intent
        current.entities = self._merge(current.entities, parsed.entities)

        if current.intent == "make_reservation":
            reply = self._prepare_reservation(current)
        elif current.intent == "cancel_reservation":
            reply = self._cancel(current)
        elif current.intent == "modify_reservation":
            reply = self._modify(current)
        else:
            reply = (
                "I can book, modify, or cancel a reservation. "
                "For an offline demo, use: book | name=Ahmed | email=ahmed@example.com | "
                "party=2 | date=2026-10-10 | time=19:00 | type=dinner"
            )
        return self._finish(reply, current)

    @staticmethod
    def _merge(existing: ReservationEntities, incoming: ReservationEntities) -> ReservationEntities:
        values = existing.model_dump()
        values.update(incoming.model_dump(exclude_none=True))
        return ReservationEntities(**values)

    def _prepare_reservation(self, state: ConversationState) -> str:
        for field, question in self.required_fields:
            if getattr(state.entities, field) is None:
                return question
        if not self.store.is_available(state.entities.res_date, state.entities.res_time):
            alternatives = self.store.alternative_slots(
                state.entities.res_date, state.entities.res_time
            )
            suggestion = ", ".join(alternatives) if alternatives else "none available nearby"
            return f"That time is full. Nearby available times: {suggestion}."
        state.awaiting_confirmation = True
        return (
            f"Confirm {state.entities.reservation_type} for {state.entities.num_persons} on "
            f"{state.entities.res_date} at {state.entities.res_time} under "
            f"{state.entities.user_name}? Reply yes or no."
        )

    def _confirm(self, message: str, state: ConversationState) -> AgentReply:
        answer = message.strip().lower()
        if answer not in {"yes", "y", "confirm", "no", "n", "cancel"}:
            return self._finish("Please reply yes to confirm or no to discard it.", state)
        if answer in {"no", "n", "cancel"}:
            return self._finish("The pending reservation was discarded.", self._reset(state))
        try:
            reservation = self.store.create(state.entities)
            reply = (
                f"Reservation confirmed. Your reservation ID is {reservation.reservation_id}. "
                "Keep this ID and your email address to modify or cancel it."
            )
        except SlotUnavailable as error:
            reply = str(error)
        return self._finish(reply, self._reset(state))

    def _cancel(self, state: ConversationState) -> str:
        if state.entities.reservation_id is None:
            return "What is the reservation ID?"
        if state.entities.email_id is None:
            return "What email address was used for the reservation?"
        try:
            reservation = self.store.cancel(
                state.entities.reservation_id, str(state.entities.email_id)
            )
            self._reset(state)
            return f"Reservation {reservation.reservation_id} has been cancelled."
        except ReservationNotFound as error:
            return str(error)

    def _modify(self, state: ConversationState) -> str:
        if state.entities.reservation_id is None:
            return "What is the reservation ID?"
        if state.entities.email_id is None:
            return "What email address was used for the reservation?"
        changes = state.entities.model_dump(
            exclude_none=True,
            exclude={"reservation_id", "email_id"},
        )
        if not changes:
            return "What would you like to change?"
        try:
            reservation = self.store.modify(state.entities)
            self._reset(state)
            return (
                f"Reservation {reservation.reservation_id} was updated to "
                f"{reservation.res_date} at {reservation.res_time}."
            )
        except (ReservationError, ReservationNotFound, SlotUnavailable) as error:
            return str(error)

    @staticmethod
    def _reset(state: ConversationState) -> ConversationState:
        state.intent = None
        state.entities = ReservationEntities()
        state.awaiting_confirmation = False
        return state

    @staticmethod
    def _finish(message: str, state: ConversationState) -> AgentReply:
        state.messages.append({"role": "assistant", "content": message})
        return AgentReply(message=message, state=state)

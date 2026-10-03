from pathlib import Path

from restaurant_agent.agent import ReservationAgent
from restaurant_agent.database import ReservationStore
from restaurant_agent.extraction import HybridExtractor


def test_offline_booking_and_cancellation(tmp_path: Path) -> None:
    agent = ReservationAgent(ReservationStore(tmp_path / "restaurant.db"), HybridExtractor())
    booking = agent.respond(
        "book | name=Ahmed | email=ahmed@example.com | party=2 | "
        "date=2026-10-10 | time=19:00 | type=dinner"
    )
    assert booking.state.awaiting_confirmation is True

    confirmation = agent.respond("yes", booking.state)
    assert "reservation ID is 1" in confirmation.message

    cancellation = agent.respond("cancel | id=1 | email=ahmed@example.com", confirmation.state)
    assert cancellation.message == "Reservation 1 has been cancelled."


def test_agent_requests_missing_fields(tmp_path: Path) -> None:
    agent = ReservationAgent(ReservationStore(tmp_path / "restaurant.db"), HybridExtractor())
    result = agent.respond("book | name=Ahmed")
    assert result.message == "What email address should I attach to the reservation?"


def test_cancel_reservation_is_not_misread_as_booking(tmp_path: Path) -> None:
    agent = ReservationAgent(ReservationStore(tmp_path / "restaurant.db"), HybridExtractor())
    result = agent.respond("cancel reservation | id=42 | email=ahmed@example.com")
    assert result.message == "No active reservation matches that ID and email address."


def test_invalid_details_return_a_clear_message(tmp_path: Path) -> None:
    agent = ReservationAgent(ReservationStore(tmp_path / "restaurant.db"), HybridExtractor())
    result = agent.respond(
        "book | name=Ahmed | email=invalid | party=30 | date=2026-10-10 | time=19:00 | type=dinner"
    )
    assert result.message.startswith("I couldn't validate")

from pathlib import Path

import pytest

from restaurant_agent.database import ReservationNotFound, ReservationStore, SlotUnavailable
from restaurant_agent.models import ReservationEntities


def details(**changes: object) -> ReservationEntities:
    values = {
        "user_name": "Ahmed",
        "email_id": "ahmed@example.com",
        "num_persons": 2,
        "reservation_type": "dinner",
        "res_date": "2026-10-10",
        "res_time": "19:00",
    }
    values.update(changes)
    return ReservationEntities(**values)


def test_create_modify_and_cancel(tmp_path: Path) -> None:
    store = ReservationStore(tmp_path / "restaurant.db")
    reservation = store.create(details())
    assert reservation.status == "confirmed"

    updated = store.modify(
        ReservationEntities(
            reservation_id=reservation.reservation_id,
            email_id="ahmed@example.com",
            res_time="20:00",
        )
    )
    assert updated.res_time == "20:00"

    cancelled = store.cancel(reservation.reservation_id, "AHMED@example.com")
    assert cancelled.status == "cancelled"
    assert cancelled.res_date == "2026-10-10"


def test_slot_capacity_is_enforced_atomically(tmp_path: Path) -> None:
    store = ReservationStore(tmp_path / "restaurant.db", slot_capacity=1)
    store.create(details())
    with pytest.raises(SlotUnavailable):
        store.create(details(email_id="second@example.com", user_name="Second Guest"))


def test_email_is_required_for_cancellation(tmp_path: Path) -> None:
    store = ReservationStore(tmp_path / "restaurant.db")
    reservation = store.create(details())
    with pytest.raises(ReservationNotFound):
        store.cancel(reservation.reservation_id, "wrong@example.com")

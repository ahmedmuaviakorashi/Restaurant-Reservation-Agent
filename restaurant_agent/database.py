import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from restaurant_agent.models import Reservation, ReservationEntities


class ReservationError(Exception):
    pass


class ReservationNotFound(ReservationError):
    pass


class SlotUnavailable(ReservationError):
    pass


class ReservationStore:
    def __init__(self, path: Path, slot_capacity: int = 5) -> None:
        if slot_capacity < 1:
            raise ValueError("slot_capacity must be at least 1")
        self.path = path
        self.slot_capacity = slot_capacity
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_name TEXT NOT NULL,
                    email_id TEXT NOT NULL COLLATE NOCASE,
                    num_persons INTEGER NOT NULL CHECK (num_persons BETWEEN 1 AND 20),
                    reservation_type TEXT NOT NULL,
                    res_date TEXT NOT NULL,
                    res_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reservation_slot
                ON reservations (res_date, res_time, status)
                """
            )

    def is_available(
        self,
        res_date: str,
        res_time: str,
        excluding_reservation_id: int | None = None,
    ) -> bool:
        query = """
            SELECT COUNT(*)
            FROM reservations
            WHERE res_date = ? AND res_time = ? AND status = 'confirmed'
        """
        parameters: list[Any] = [res_date, res_time]
        if excluding_reservation_id is not None:
            query += " AND reservation_id <> ?"
            parameters.append(excluding_reservation_id)
        with self.connect() as connection:
            count = connection.execute(query, parameters).fetchone()[0]
        return count < self.slot_capacity

    def create(self, entities: ReservationEntities) -> Reservation:
        required = {
            "user_name": entities.user_name,
            "email_id": entities.email_id,
            "num_persons": entities.num_persons,
            "reservation_type": entities.reservation_type,
            "res_date": entities.res_date,
            "res_time": entities.res_time,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ReservationError("Missing fields: " + ", ".join(missing))

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            count = connection.execute(
                """
                SELECT COUNT(*) FROM reservations
                WHERE res_date = ? AND res_time = ? AND status = 'confirmed'
                """,
                (entities.res_date, entities.res_time),
            ).fetchone()[0]
            if count >= self.slot_capacity:
                raise SlotUnavailable("The requested time is no longer available.")
            cursor = connection.execute(
                """
                INSERT INTO reservations (
                    user_name, email_id, num_persons, reservation_type,
                    res_date, res_time, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'confirmed')
                """,
                (
                    entities.user_name,
                    str(entities.email_id),
                    entities.num_persons,
                    entities.reservation_type,
                    entities.res_date,
                    entities.res_time,
                ),
            )
            reservation_id = cursor.lastrowid
        return self.get(reservation_id)

    def get(self, reservation_id: int) -> Reservation:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()
        if row is None:
            raise ReservationNotFound(f"Reservation {reservation_id} was not found.")
        return Reservation.model_validate(dict(row))

    def cancel(self, reservation_id: int, email_id: str) -> Reservation:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reservations
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                WHERE reservation_id = ? AND email_id = ? AND status = 'confirmed'
                """,
                (reservation_id, email_id),
            )
            if cursor.rowcount == 0:
                raise ReservationNotFound(
                    "No active reservation matches that ID and email address."
                )
        return self.get(reservation_id)

    def modify(self, entities: ReservationEntities) -> Reservation:
        if entities.reservation_id is None or entities.email_id is None:
            raise ReservationError("Reservation ID and email are required.")
        current = self.get(entities.reservation_id)
        if current.email_id.lower() != str(entities.email_id).lower():
            raise ReservationNotFound("No reservation matches that ID and email address.")
        if current.status != "confirmed":
            raise ReservationError("Cancelled reservations cannot be modified.")

        updates = {
            "user_name": entities.user_name,
            "num_persons": entities.num_persons,
            "reservation_type": entities.reservation_type,
            "res_date": entities.res_date,
            "res_time": entities.res_time,
        }
        updates = {key: value for key, value in updates.items() if value is not None}
        if not updates:
            raise ReservationError("Provide at least one field to modify.")

        new_date = str(updates.get("res_date", current.res_date))
        new_time = str(updates.get("res_time", current.res_time))
        assignments = ", ".join(f"{column} = ?" for column in updates)
        values = [*updates.values(), entities.reservation_id, str(entities.email_id)]
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if (new_date, new_time) != (current.res_date, current.res_time):
                count = connection.execute(
                    """
                    SELECT COUNT(*) FROM reservations
                    WHERE res_date = ? AND res_time = ? AND status = 'confirmed'
                        AND reservation_id <> ?
                    """,
                    (new_date, new_time, current.reservation_id),
                ).fetchone()[0]
                if count >= self.slot_capacity:
                    raise SlotUnavailable("The requested replacement time is unavailable.")
            cursor = connection.execute(
                f"""
                UPDATE reservations
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE reservation_id = ? AND email_id = ? AND status = 'confirmed'
                """,
                values,
            )
            if cursor.rowcount == 0:
                raise ReservationNotFound(
                    "No active reservation matches that ID and email address."
                )
        return self.get(entities.reservation_id)

    def alternative_slots(self, res_date: str, res_time: str, limit: int = 3) -> list[str]:
        requested = datetime.combine(date.fromisoformat(res_date), time.fromisoformat(res_time))
        alternatives: list[str] = []
        for offset in (1, -1, 2, -2, 3, -3):
            candidate = requested + timedelta(hours=offset)
            if candidate.date() != requested.date() or not 12 <= candidate.hour <= 22:
                continue
            candidate_time = candidate.strftime("%H:%M")
            if self.is_available(res_date, candidate_time):
                alternatives.append(candidate_time)
            if len(alternatives) == limit:
                break
        return alternatives

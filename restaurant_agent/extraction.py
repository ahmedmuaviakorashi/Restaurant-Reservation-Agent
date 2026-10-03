import json
import re
from typing import ClassVar, Protocol

from openai import OpenAI, OpenAIError

from restaurant_agent.models import ConversationState, ParsedInput, ReservationEntities


class Extractor(Protocol):
    def extract(self, message: str, state: ConversationState) -> ParsedInput: ...


class CommandExtractor:
    intent_words: ClassVar[dict[str, str]] = {
        "cancel": "cancel_reservation",
        "modify": "modify_reservation",
        "change": "modify_reservation",
        "update": "modify_reservation",
        "book": "make_reservation",
        "reserve": "make_reservation",
        "reservation": "make_reservation",
    }
    aliases: ClassVar[dict[str, str]] = {
        "id": "reservation_id",
        "reservation_id": "reservation_id",
        "name": "user_name",
        "email": "email_id",
        "party": "num_persons",
        "people": "num_persons",
        "type": "reservation_type",
        "date": "res_date",
        "time": "res_time",
    }

    def extract(self, message: str, state: ConversationState) -> ParsedInput:
        lowered = message.lower()
        intent = next(
            (value for word, value in self.intent_words.items() if word in lowered),
            state.intent,
        )
        values: dict[str, object] = {}
        for part in message.split("|")[1:]:
            if "=" not in part:
                continue
            key, value = (item.strip() for item in part.split("=", 1))
            field = self.aliases.get(key.lower())
            if field:
                if field in {"reservation_id", "num_persons"}:
                    if value.isdigit():
                        values[field] = int(value)
                else:
                    values[field] = value

        email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", message)
        iso_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
        clock = re.search(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", message)
        reservation_id = re.search(r"(?:reservation\s*(?:id)?|id)\s*#?:?\s*(\d+)", lowered)
        party = re.search(r"(?:for|party(?:\s+of)?)\s+(\d+)\b", lowered)
        name = re.search(r"(?:name is|name=)\s*([A-Za-z][A-Za-z .'-]{1,60})", message)
        if email:
            values.setdefault("email_id", email.group(0))
        if iso_date:
            values.setdefault("res_date", iso_date.group(0))
        if clock:
            values.setdefault("res_time", clock.group(0))
        if reservation_id:
            values.setdefault("reservation_id", int(reservation_id.group(1)))
        if party:
            values.setdefault("num_persons", int(party.group(1)))
        if name:
            values.setdefault("user_name", name.group(1).strip())
        return ParsedInput(intent=intent, entities=ReservationEntities(**values))


class GroqExtractor:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        self.model = model

    def extract(self, message: str, state: ConversationState) -> ParsedInput:
        prompt = {
            "role": "system",
            "content": (
                "Extract restaurant reservation intent and fields. Return one JSON object with "
                "intent and entities. Allowed intents are make_reservation, modify_reservation, "
                "cancel_reservation, or null. Entity keys are reservation_id, user_name, email_id, "
                "num_persons, reservation_type, res_date, and res_time. Dates must be YYYY-MM-DD "
                "and times HH:MM in 24-hour format. Use null for unknown values."
            ),
        }
        context = json.dumps(state.model_dump(mode="json"), default=str)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[prompt, {"role": "user", "content": f"State: {context}\nMessage: {message}"}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The language model returned an empty response.")
        return ParsedInput.model_validate_json(content)


class HybridExtractor:
    def __init__(self, llm: GroqExtractor | None = None) -> None:
        self.command = CommandExtractor()
        self.llm = llm

    def extract(self, message: str, state: ConversationState) -> ParsedInput:
        parsed = self.command.extract(message, state)
        if "|" in message or self.llm is None:
            return parsed
        try:
            return self.llm.extract(message, state)
        except (OpenAIError, ValueError):
            return parsed

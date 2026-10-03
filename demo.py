import os
from pathlib import Path

from dotenv import load_dotenv

from restaurant_agent.agent import ReservationAgent
from restaurant_agent.database import ReservationStore
from restaurant_agent.extraction import GroqExtractor, HybridExtractor
from restaurant_agent.models import ConversationState


def main() -> None:
    load_dotenv()
    store = ReservationStore(Path(os.getenv("RESTAURANT_DB_PATH", "data/restaurant.db")))
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL")
    llm = GroqExtractor(api_key, model) if api_key and model else None
    agent = ReservationAgent(store, HybridExtractor(llm))
    state = ConversationState()
    print("Restaurant Reservation Agent. Type exit to stop.")
    while True:
        message = input("You: ").strip()
        if message.lower() in {"exit", "quit"}:
            break
        result = agent.respond(message, state)
        state = result.state
        print("Agent:", result.message)


if __name__ == "__main__":
    main()

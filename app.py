import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from restaurant_agent.agent import ReservationAgent
from restaurant_agent.database import ReservationStore
from restaurant_agent.extraction import GroqExtractor, HybridExtractor
from restaurant_agent.models import ConversationState

load_dotenv()


def build_agent() -> tuple[ReservationAgent, bool]:
    database_path = Path(os.getenv("RESTAURANT_DB_PATH", "data/restaurant.db"))
    store = ReservationStore(database_path)
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL")
    llm = GroqExtractor(api_key, model) if api_key and model else None
    return ReservationAgent(store, HybridExtractor(llm)), llm is not None


def main() -> None:
    st.set_page_config(page_title="Restaurant Reservation Agent", page_icon="🍽️")
    st.title("Restaurant Reservation Agent")
    st.caption("Groq extraction is optional; reservation actions are deterministic.")
    agent, llm_enabled = build_agent()
    st.sidebar.write("Natural-language extraction:", "Enabled" if llm_enabled else "Offline mode")

    if "reservation_state" not in st.session_state:
        st.session_state.reservation_state = ConversationState().model_dump(mode="json")

    state = ConversationState.model_validate(st.session_state.reservation_state)
    for item in state.messages:
        st.chat_message(item["role"]).write(item["content"])

    if prompt := st.chat_input("Book, modify, or cancel a reservation"):
        with st.chat_message("user"):
            st.write(prompt)
        result = agent.respond(prompt, state)
        st.session_state.reservation_state = result.state.model_dump(mode="json")
        with st.chat_message("assistant"):
            st.write(result.message)


if __name__ == "__main__":
    main()

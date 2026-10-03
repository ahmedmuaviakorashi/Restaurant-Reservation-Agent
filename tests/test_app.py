from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_in_offline_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RESTAURANT_DB_PATH", str(tmp_path / "restaurant.db"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    app = AppTest.from_file(app_path).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "Restaurant Reservation Agent"
    assert app.chat_input[0].placeholder == "Book, modify, or cancel a reservation"

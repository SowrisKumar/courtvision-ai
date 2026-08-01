"""AI layer tests: provider detection, SQL guard, agent loop, endpoints.

All tests use a scripted FakeLLM -- no network, no API keys required.
"""

import json

import pytest
from fastapi.testclient import TestClient

from courtvision.config import DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="database not ingested yet")


class FakeLLM:
    provider = "fake"
    model = "fake-1"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def complete(self, system: str, messages: list[dict]) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


@pytest.fixture()
def con():
    from courtvision.db.connection import get_connection

    con = get_connection(read_only=True)
    yield con
    con.close()


# ---------- provider detection ----------

def test_detect_provider_priority_and_override(monkeypatch):
    from courtvision.ai.llm import detect_provider

    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                "COURTVISION_LLM"):
        monkeypatch.delenv(var, raising=False)
    assert detect_provider() is None

    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    assert detect_provider() == ("gemini", "g-key")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    assert detect_provider() == ("anthropic", "a-key")  # anthropic outranks

    monkeypatch.setenv("COURTVISION_LLM", "gemini")
    assert detect_provider() == ("gemini", "g-key")  # explicit override wins

    monkeypatch.setenv("COURTVISION_LLM", "openai")
    assert detect_provider() is None  # override without a key -> unconfigured


# ---------- SQL guard ----------

def test_sql_guard(con):
    from courtvision.ai.assistant import SQLGuardError, safe_execute

    rows, total = safe_execute(con, "SELECT team FROM v_team_season LIMIT 3")
    assert len(rows) == 3 and total == 3

    for bad in ("DROP TABLE teams", "DELETE FROM teams", "SELECT 1; SELECT 2",
                "UPDATE teams SET id = 1"):
        with pytest.raises(SQLGuardError):
            safe_execute(con, bad)


# ---------- agent loop ----------

def test_ask_runs_sql_then_answers(con):
    from courtvision.ai.assistant import ask

    fake = FakeLLM([
        json.dumps({"sql": "SELECT team_name, w FROM v_team_season WHERE season = '2025-26' ORDER BY w DESC LIMIT 1"}),
        json.dumps({"answer": "The best team had the most wins — per the data."}),
    ])
    result = ask(con, fake, "Who had the best record in 2025-26?")
    assert len(result["steps"]) == 1
    assert result["steps"][0]["total_rows"] == 1
    assert "—" not in result["answer"]  # em dashes sanitized
    # second call saw the query result
    assert "Query result" in fake.calls[1][-1]["content"]


def test_ask_recovers_from_bad_sql(con):
    from courtvision.ai.assistant import ask

    fake = FakeLLM([
        json.dumps({"sql": "DROP TABLE teams"}),
        json.dumps({"answer": "done"}),
    ])
    result = ask(con, fake, "test")
    assert result["answer"] == "done"
    assert "rejected" in fake.calls[1][-1]["content"]
    assert result["steps"] == []


def test_ask_query_limit(con):
    from courtvision.ai.assistant import MAX_SQL_ROUNDS, ask

    fake = FakeLLM(
        [json.dumps({"sql": "SELECT 1 AS x"})] * (MAX_SQL_ROUNDS + 1)
        + [json.dumps({"answer": "capped"})]
    )
    result = ask(con, fake, "loop forever")
    assert result["answer"] == "capped"
    assert len(result["steps"]) == MAX_SQL_ROUNDS


# ---------- scouting ----------

def test_scouting_report_grounding(con):
    from courtvision.ai.scouting import gather_player_data, scouting_report

    jokic = 203999
    data = gather_player_data(con, jokic)
    assert data["player_name"] == "Nikola Jokić"
    assert len(data["seasons"]) >= 3
    assert data["similar_players"]

    fake = FakeLLM(["PROFILE: elite center.\nOFFENSE: efficient."])
    report = scouting_report(con, fake, jokic)
    assert report["player_name"] == "Nikola Jokić"
    assert "PROFILE" in report["report"]
    # the prompt contained real grounded data, not just the player name
    sent = fake.calls[0][0]["content"]
    assert "ts_pct" in sent and "similar_players" in sent

    assert scouting_report(con, fake, 42) is None


# ---------- endpoints ----------

@pytest.fixture()
def client_with_fake_llm():
    from courtvision.api import main as api_main

    fake = FakeLLM([json.dumps({"answer": "forty-two"})] * 5)
    api_main.app.dependency_overrides[api_main.llm] = lambda: fake
    with TestClient(api_main.app) as c:
        yield c
    api_main.app.dependency_overrides.clear()


def test_ask_endpoint(client_with_fake_llm):
    body = client_with_fake_llm.post("/ask", json={"question": "How good are the Nuggets?"}).json()
    assert body["answer"] == "forty-two"
    assert body["provider"] == "fake"
    assert client_with_fake_llm.post("/ask", json={"question": "x"}).status_code == 400


def test_ask_unconfigured_returns_503(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                "COURTVISION_LLM"):
        monkeypatch.delenv(var, raising=False)
    from courtvision.api.main import app

    with TestClient(app) as c:
        response = c.post("/ask", json={"question": "anything at all"})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]

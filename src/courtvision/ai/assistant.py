"""Natural-language analytics: an LLM agent that answers basketball questions
by writing SQL against the warehouse views.

Grounding contract: the model may only use numbers that came back from its own
SQL queries, and every executed query is returned to the caller so the UI can
show exactly where an answer came from.
"""

import json
import re

import duckdb

from courtvision.ai.llm import LLMClient

MAX_SQL_ROUNDS = 4
MAX_RESULT_ROWS = 40

SCHEMA_DOC = """
You can query a DuckDB warehouse of NBA statistics through these views
(seasons are strings like '2025-26'; percentages are 0-1 fractions):

v_player_season -- one row per player per season:
  player_id, player_name, team_id, team (abbreviation), season, age, gp (games),
  win_pct, min_pg, pts_pg, reb_pg, ast_pg, stl_pg, blk_pg, tov_pg (all per game),
  fg_pct, fg3_pct, ft_pct, fg3a_pg, ts_pct, efg_pct, usg_pct,
  off_rating, def_rating, net_rating, ast_pct, reb_pct, pie, team_count

v_team_season -- one row per team per season:
  team_id, team_name, team, season, gp, w, l, win_pct, pts_pg, reb_pg, ast_pg,
  tov_pg, off_rating, def_rating, net_rating, pace, efg_pct, ts_pct,
  oreb_pct, dreb_pct, reb_pct, tov_pct, ast_pct, pie

v_team_game -- one row per team per game (2 rows per game, joined on game_id):
  game_id, season, game_date, team_id, team, matchup, is_home, is_win,
  pts, plus_minus, fg_pct, fg3m, reb, ast, tov

Notes: player name matching should use
strip_accents(lower(player_name)) LIKE '%name%'. Ratings are points per 100
possessions (lower def_rating is better). DuckDB SQL dialect.
""".strip()

SYSTEM_PROMPT = f"""
You are CourtVision, an NBA analytics assistant. Answer questions using ONLY
data you retrieve from the warehouse described below. Never invent statistics.

{SCHEMA_DOC}

Respond with EXACTLY ONE JSON object per turn, nothing else:
- To run a query: {{"sql": "SELECT ..."}} (single SELECT statement, add LIMIT)
- To answer: {{"answer": "..."}}

Rules for the final answer: cite the numbers you found; plain text with short
paragraphs or simple '-' bullet lists (no markdown tables, no headers); if the
data cannot answer the question, say so plainly. Do not use em dashes.
""".strip()


class SQLGuardError(ValueError):
    pass


def safe_execute(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[list[dict], int]:
    """Run one guarded SELECT. Returns (rows as dicts, total row count)."""
    statement = sql.strip().rstrip(";").strip()
    if ";" in statement:
        raise SQLGuardError("only a single statement is allowed")
    if not re.match(r"^(select|with)\b", statement, re.IGNORECASE):
        raise SQLGuardError("only SELECT queries are allowed")
    df = con.execute(statement).df()
    total = len(df)
    rows = json.loads(df.head(MAX_RESULT_ROWS).to_json(orient="records"))
    return rows, total


def _parse_response(text: str) -> dict:
    """Extract the JSON object from a model response (tolerates code fences)."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def strip_em_dashes(text: str) -> str:
    return text.replace(" — ", ", ").replace("—", "-")


def ask(con: duckdb.DuckDBPyConnection, llm: LLMClient, question: str) -> dict:
    """Run the SQL-agent loop. Returns {answer, steps: [{sql, rows, total_rows}]}."""
    messages = [{"role": "user", "content": question}]
    steps: list[dict] = []

    # Hard cap on LLM calls: SQL rounds + retries for rejected queries + the
    # final forced answer.
    for _ in range(MAX_SQL_ROUNDS * 2 + 2):
        raw = llm.complete(SYSTEM_PROMPT, messages)
        try:
            action = _parse_response(raw)
        except (json.JSONDecodeError, AttributeError):
            # Model ignored the protocol; treat its text as the answer.
            return {"answer": strip_em_dashes(raw.strip()), "steps": steps}

        if "answer" in action:
            return {"answer": strip_em_dashes(str(action["answer"]).strip()), "steps": steps}

        sql = action.get("sql", "")
        messages.append({"role": "assistant", "content": raw})
        if len(steps) >= MAX_SQL_ROUNDS:
            messages.append({
                "role": "user",
                "content": "Query limit reached. Answer now from the data you already have.",
            })
            continue
        try:
            rows, total = safe_execute(con, sql)
            steps.append({"sql": sql, "rows": rows, "total_rows": total})
            payload = json.dumps({"total_rows": total, "rows": rows})
            messages.append({"role": "user", "content": f"Query result: {payload}"})
        except SQLGuardError as exc:
            messages.append({"role": "user", "content": f"Query rejected: {exc}. Try again."})
        except Exception as exc:  # noqa: BLE001 - SQL errors go back to the model to fix
            messages.append({"role": "user", "content": f"SQL error: {exc}. Fix the query."})

    return {
        "answer": "I could not produce an answer from the warehouse for this question.",
        "steps": steps,
    }

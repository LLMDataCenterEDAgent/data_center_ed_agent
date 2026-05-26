import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class LocalStore:
    def __init__(self, db_path: str = "data/app_history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @property
    def enabled(self) -> bool:
        return True

    def insert_scenario(self, name: str, description: str, config: dict[str, Any]) -> dict[str, Any]:
        created_at = _now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into scenarios (name, description, config, created_at)
                values (?, ?, ?, ?)
                """,
                (name, description, json.dumps(config, ensure_ascii=False), created_at),
            )
            conn.commit()
            scenario_id = cursor.lastrowid
        return {
            "id": scenario_id,
            "name": name,
            "description": description,
            "config": config,
            "created_at": created_at,
        }

    def insert_run(
        self,
        scenario_id: Optional[str],
        status: str,
        metrics: dict[str, Any],
        result_table: list[dict[str, Any]],
        report_text: str,
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        created_at = _now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into runs (
                    scenario_id, status, metrics, result_table, report_text, error_message, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario_id,
                    status,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(result_table, ensure_ascii=False),
                    report_text,
                    error_message,
                    created_at,
                ),
            )
            conn.commit()
            run_id = cursor.lastrowid
        return {
            "id": run_id,
            "scenario_id": scenario_id,
            "status": status,
            "metrics": metrics,
            "result_table": result_table,
            "report_text": report_text,
            "error_message": error_message,
            "created_at": created_at,
        }

    def list_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    r.id,
                    r.scenario_id,
                    r.status,
                    r.metrics,
                    r.result_table,
                    r.report_text,
                    r.error_message,
                    r.created_at,
                    s.name as scenario_name,
                    s.description as scenario_description,
                    s.config as scenario_config
                from runs r
                left join scenarios s on s.id = r.scenario_id
                order by r.created_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_run(row) for row in rows]

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists scenarios (
                    id integer primary key autoincrement,
                    name text not null,
                    description text,
                    config text not null,
                    created_at text not null
                );

                create table if not exists runs (
                    id integer primary key autoincrement,
                    scenario_id integer references scenarios(id) on delete set null,
                    status text not null,
                    metrics text not null,
                    result_table text not null,
                    report_text text,
                    error_message text,
                    created_at text not null
                );
                """
            )

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_run(self, row: sqlite3.Row) -> dict[str, Any]:
        scenario = None
        if row["scenario_name"]:
            scenario = {
                "name": row["scenario_name"],
                "description": row["scenario_description"],
                "config": _loads(row["scenario_config"], {}),
            }
        return {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "status": row["status"],
            "metrics": _loads(row["metrics"], {}),
            "result_table": _loads(row["result_table"], []),
            "report_text": row["report_text"],
            "error_message": row["error_message"],
            "created_at": row["created_at"],
            "scenarios": scenario,
        }


def _loads(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

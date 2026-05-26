import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests


class SupabaseStore:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = (url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.key)

    def insert_scenario(self, name: str, description: str, config: dict[str, Any]) -> Optional[dict[str, Any]]:
        return self._request(
            "POST",
            "scenarios",
            {
                "name": name,
                "description": description,
                "config": config,
                "created_at": _now_iso(),
            },
            prefer="return=representation",
        )

    def insert_run(
        self,
        scenario_id: Optional[str],
        status: str,
        metrics: dict[str, Any],
        result_table: list[dict[str, Any]],
        report_text: str,
        error_message: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        return self._request(
            "POST",
            "runs",
            {
                "scenario_id": scenario_id,
                "status": status,
                "metrics": metrics,
                "result_table": result_table,
                "report_text": report_text,
                "error_message": error_message,
                "created_at": _now_iso(),
            },
            prefer="return=representation",
        )

    def list_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self._request(
            "GET",
            f"runs?select=*,scenarios(name,description,config)&order=created_at.desc&limit={limit}",
        )
        return rows if isinstance(rows, list) else []

    def _request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None, prefer: Optional[str] = None):
        if not self.enabled:
            return None

        headers = {
            "apikey": self.key,
            "Content-Type": "application/json",
        }
        if not self.key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {self.key}"
        if prefer:
            headers["Prefer"] = prefer

        response = requests.request(
            method,
            f"{self.url}/rest/v1/{path}",
            headers=headers,
            data=json.dumps(payload) if payload is not None else None,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"Supabase request failed: {response.status_code} {response.text}") from exc
        if not response.text:
            return None
        data = response.json()
        if isinstance(data, list) and len(data) == 1 and method == "POST":
            return data[0]
        return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

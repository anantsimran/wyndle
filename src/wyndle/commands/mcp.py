"""Local MCP tools backed by the running dashboard's serialized API."""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


class DashboardClient:
    """Call only the loopback dashboard; it owns the task and state lock."""

    def __init__(self, port: int) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("Dashboard port must be between 1 and 65535.")
        self.base_url = f"http://127.0.0.1:{port}"
        self.port = port
        self.opener = build_opener(ProxyHandler({}))

    def _request(self, path: str, payload: dict | None = None) -> dict:
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json", "X-Wyndle-Client": "dashboard"}
        request = Request(f"{self.base_url}{path}", data=body, headers=headers)
        try:
            with self.opener.open(request, timeout=10) as response:
                result = json.load(response)
        except HTTPError as exc:
            try:
                message = json.load(exc).get("error", "Wyndle rejected the request.")
            except (ValueError, AttributeError):
                message = "Wyndle rejected the request."
            raise ValueError(message) from exc
        except OSError as exc:
            raise ConnectionError(
                f"Start the dashboard with `wyndle ui --no-browser --port {self.port}` "
                "before using the MCP tools."
            ) from exc
        if not isinstance(result, dict):
            raise ValueError("The local server returned an invalid response.")
        if result.get("app") != "wyndle" and path == "/api/status":
            raise ValueError("The local server is not a Wyndle dashboard.")
        return result

    def status(self) -> dict:
        return self._request("/api/status")

    def action(self, name: str, data: dict) -> dict:
        self.status()  # Confirm that this port belongs to Wyndle before posting.
        return self._request("/api/action", {"action": name, "data": data})


def _task_summary(task: dict) -> dict:
    return {
        "title": task["title"], "group": task["parent"], "done": task["done"],
        "estimateMinutes": task["estimate"], "trackedMinutes": task["elapsed"] // 60,
        "type": "p0" if task["priority"] else "optional" if task["optional"] else "regular",
        "noteCount": len(task["notes"]),
    }


def _day_summary(status: dict) -> dict:
    return {
        "date": status["date"], "started": status["started"],
        "wrapped": status["wrapped"], "carryover": status["carryover"],
        "groups": status["groups"],
        "tasks": [_task_summary(task) for task in status["tasks"]],
    }


def _find_task(status: dict, title: str) -> dict:
    matching = [task for task in status["tasks"] if task["title"].casefold() == title.casefold()]
    if len(matching) != 1:
        raise ValueError("Find one task by its exact title from get_today, then try again.")
    return matching[0]


def create_server(ui_port: int = 8765):
    """Create a stdio MCP server that uses the running local Wyndle dashboard."""
    from mcp.server.mcpserver import MCPServer

    dashboard = DashboardClient(ui_port)
    server = MCPServer(
        "Wyndle",
        instructions=(
            "Use get_today to see the current plan. Start the day before adding work. "
            "Task and group names are user-facing; use the exact task title for notes. "
            "Wyndle stores work in local Markdown on the computer running the dashboard."
        ),
    )

    @server.tool(description="Read today's Wyndle groups, subtasks, and unfinished carryover.")
    def get_today() -> dict:
        return _day_summary(dashboard.status())

    @server.tool(description="Start today's plan. Carry over all unfinished groups or none.")
    def start_day(carryover: bool = True) -> dict:
        return _day_summary(dashboard.action("morning", {"carryover": carryover}))

    @server.tool(description="Add a high-level task to today's plan.")
    def add_group(title: str) -> dict:
        status = dashboard.action("add_group", {"title": title})
        return {"groups": status["groups"]}

    @server.tool(description="Add a subtask to today's plan. Estimate is for the whole task.")
    def add_task(title: str, group: str = "Today", estimate_minutes: int = 15,
                 task_type: str = "regular") -> dict:
        if task_type not in ("regular", "p0", "optional"):
            raise ValueError("task_type must be regular, p0, or optional.")
        status = dashboard.action("add", {
            "title": title, "parent": group, "estimate": estimate_minutes,
            "priority": task_type == "p0", "optional": task_type == "optional",
        })
        return {"added": _task_summary(_find_task(status, title))}

    @server.tool(description="Attach a short note to one task, identified by its exact title.")
    def add_task_note(task_title: str, note: str) -> dict:
        task = _find_task(dashboard.status(), task_title)
        status = dashboard.action("note", {"id": task["id"], "note": note})
        return {"updated": _task_summary(_find_task(status, task_title))}

    return server

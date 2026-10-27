"""Exercise the local MCP tools against the real dashboard API."""

import asyncio
import json
import threading

import pytest

pytest.importorskip("mcp")
from mcp.client import Client  # noqa: E402

from wyndle.commands.mcp import create_server  # noqa: E402
from wyndle.commands.ui import make_server  # noqa: E402


def test_mcp_tools_share_dashboard_rules(cfg, state, clock):
    dashboard = make_server(cfg, state, 0)
    thread = threading.Thread(target=dashboard.serve_forever, daemon=True)
    thread.start()

    async def exercise():
        async with Client(create_server(dashboard.server_port)) as client:
            available = await client.list_tools()
            assert {tool.name for tool in available.tools} == {
                "get_today", "start_day", "add_group", "add_task", "add_task_note",
            }

            async def call(name, arguments=None):
                response = await client.call_tool(name, arguments or {})
                assert not response.is_error, response
                return json.loads(response.content[0].text)

            assert not (await call("get_today"))["started"]
            assert (await client.call_tool("add_task", {"title": "Too early"})).is_error
            assert (await call("start_day", {"carryover": False}))["started"]
            assert "Project A2" in (await call("add_group", {"title": "Project A2"}))["groups"]
            added = await call("add_task", {
                "title": "Read the A2 ticket", "group": "Project A2",
                "estimate_minutes": 10, "task_type": "p0",
            })
            assert added["added"]["type"] == "p0"
            assert (await call("add_task_note", {
                "task_title": "Read the A2 ticket", "note": "Check the acceptance criteria",
            }))["updated"]["noteCount"] == 1
            assert any(task["title"] == "Read the A2 ticket"
                       for task in (await call("get_today"))["tasks"])

    try:
        asyncio.run(exercise())
    finally:
        dashboard.shutdown()
        dashboard.server_close()
        thread.join()

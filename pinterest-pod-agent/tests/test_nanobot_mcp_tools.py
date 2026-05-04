from scripts.nanobot_mcp_server import mcp


def test_key_nanobot_tools_are_registered() -> None:
    tool_manager = getattr(mcp, "_tool_manager")
    tools = set(getattr(tool_manager, "_tools", {}).keys())

    assert {
        "check_health",
        "check_account_proxies",
        "list_tasks",
        "get_task_detail",
        "get_recent_errors",
        "get_status_dashboard",
        "store_trend_signals",
        "get_trend_snapshot",
        "refresh_pinterest_trends",
        "generate_image",
    }.issubset(tools)

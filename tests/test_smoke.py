"""Smoke test: 実際の poranos.com に対してツールを呼び出して動作確認。

実行前に PORANOS_API_KEY を export しておくこと:

    export PORANOS_API_KEY=pk_...
    pytest tests/test_smoke.py -v -s
"""

import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("PORANOS_API_KEY"),
    reason="PORANOS_API_KEY env var not set",
)


def test_list_scenarios():
    # import inside test so PORANOS_API_KEY check at module-load happens with env set
    from poranos_mcp_ainpc.server import list_scenarios

    result = list_scenarios()
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) > 0, "本番には Library Tour が seed されているはず"
    for s in result:
        assert "id" in s and "name" in s and "content_version" in s
    print(f"\n  ✓ {len(result)} scenarios:")
    for s in result:
        print(f"    - {s['name']} (v{s['content_version']})")


def test_get_scenario_round_trip():
    from poranos_mcp_ainpc.server import get_scenario, list_scenarios

    scenarios = list_scenarios()
    target = next((s for s in scenarios if s["name"] == "Casual Chat"), None) \
        or scenarios[0]
    detail = get_scenario(target["id"])
    assert detail["id"] == target["id"]
    assert "focus_block_template" in detail
    assert "role_addendums" in detail
    print(f"\n  ✓ get_scenario({target['name']}): "
          f"v{detail['content_version']}, {len(detail.get('cast_slots', []))} slots")


def test_get_scenario_versions():
    from poranos_mcp_ainpc.server import get_scenario_versions, list_scenarios

    scenarios = list_scenarios()
    target = scenarios[0]
    versions = get_scenario_versions(target["id"])
    assert isinstance(versions, list)
    assert len(versions) >= 1, "少なくとも backfill 版があるはず"
    print(f"\n  ✓ {target['name']}: {len(versions)} version(s)")
    for v in versions[:3]:
        print(f"    - v{v['content_version']} src={v['edit_source']}")


def test_list_conversation_logs():
    from poranos_mcp_ainpc.server import list_conversation_logs

    logs = list_conversation_logs()
    assert isinstance(logs, list)
    print(f"\n  ✓ {len(logs)} conversation log(s)")
    if logs:
        print(f"    most recent: {logs[0].get('client_session_id')}")


def test_list_personalities():
    from poranos_mcp_ainpc.server import list_personalities, get_personality

    personalities = list_personalities()
    assert isinstance(personalities, list)
    print(f"\n  ✓ {len(personalities)} personalit(ies)")
    if personalities:
        target = personalities[0]
        print(f"    first: {target.get('name')} ({target.get('character_id')})")
        # detail fetch
        detail = get_personality(target["id"])
        assert "system_prompt" in detail
        sp_len = len(detail.get("system_prompt") or "")
        print(f"    system_prompt length: {sp_len}")


def test_create_scenario_round_trip():
    """create_scenario → 即削除はせずに残してしまうので、minimum で smoke のみ。
    実 DB を汚さないため自動 cleanup する。"""
    from poranos_mcp_ainpc.server import _request

    # 最小フィールド (name のみ) で作成
    created = _request("POST", "/ai-npc/scenarios/", json={
        "name": "MCP smoke test (auto-cleanup)",
        "description": "smoke test",
    })
    sid = created["id"]
    print(f"\n  ✓ created scenario {sid[:8]}... v{created['content_version']}")
    assert created["name"] == "MCP smoke test (auto-cleanup)"
    # 即削除
    _request("DELETE", f"/ai-npc/scenarios/{sid}/")
    print(f"    cleaned up.")

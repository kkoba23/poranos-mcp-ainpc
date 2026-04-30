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

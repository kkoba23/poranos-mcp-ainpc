"""Poranos MCP server.

非エンジニア運用担当が Claude Desktop / Claude Code から自然言語で
AI NPC のシナリオ・会話ログを操作するための MCP サーバ。

設定:
    PORANOS_API_KEY  (必須)  poranos.com の AccountDetail で発行する API キー
    PORANOS_API_BASE (任意)  既定: https://api.poranos.com

Claude Desktop 設定例:
    {
      "mcpServers": {
        "poranos-ainpc": {
          "command": "uvx",
          "args": ["poranos-mcp-ainpc"],
          "env": {
            "PORANOS_API_KEY": "pk_..."
          }
        }
      }
    }
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ────────────────────────────────────────────────────────────
# 設定
# ────────────────────────────────────────────────────────────

API_BASE = os.environ.get("PORANOS_API_BASE", "https://api.poranos.com").rstrip("/")
API_KEY = os.environ.get("PORANOS_API_KEY", "").strip()

if not API_KEY:
    print(
        "[poranos-mcp-ainpc] ERROR: PORANOS_API_KEY env var is required.\n"
        "  Issue an API key at https://poranos.com/app/account/ "
        "(AI NPC API キー section) and set it in your MCP config.",
        file=sys.stderr,
    )
    sys.exit(1)

# 共通 HTTP クライアント。X-Edit-Source=mcp で送信し、サーバ側 ScenarioVersion に
# `edit_source='mcp'` として記録される (poranos_manager 側 _resolve_edit_source 参照)。
_client = httpx.Client(
    base_url=API_BASE,
    headers={
        "X-API-Key": API_KEY,
        "X-Edit-Source": "mcp",
        "User-Agent": "poranos-mcp-ainpc/0.1.0",
    },
    timeout=30.0,
)


def _request(method: str, path: str, **kwargs: Any) -> Any:
    """共通 HTTP リクエスト。HTTP エラーは例外メッセージに本文を含めて再 raise。"""
    try:
        resp = _client.request(method, path, **kwargs)
    except httpx.RequestError as exc:
        raise RuntimeError(f"poranos.com への通信に失敗: {exc}") from exc

    if resp.status_code >= 400:
        body = resp.text[:500]
        raise RuntimeError(
            f"poranos.com から {resp.status_code} 応答 ({method} {path}): {body}"
        )

    if resp.status_code == 204 or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return resp.text


# ────────────────────────────────────────────────────────────
# MCP server インスタンス
# ────────────────────────────────────────────────────────────

mcp = FastMCP("poranos-ainpc")


# ────────────────────────────────────────────────────────────
# Scenario tools
# ────────────────────────────────────────────────────────────

@mcp.tool()
def list_scenarios() -> list[dict[str, Any]]:
    """利用可能な AI NPC シナリオの一覧を返す。

    各要素には id / name / description / locale / content_version /
    role_assignment / cast_slot_count / enabled_tool_count / opening_kickoff /
    is_public / is_active / is_owner / updated_at が含まれる。
    """
    data = _request("GET", "/ai-npc/scenarios/")
    return data.get("results", []) if isinstance(data, dict) else []


@mcp.tool()
def get_scenario(scenario_id: str) -> dict[str, Any]:
    """指定 ID のシナリオの全フィールド (focus_block_template / role_addendums /
    ui_panels / cast_slots / 等) を返す。
    """
    return _request("GET", f"/ai-npc/scenarios/{scenario_id}/")


@mcp.tool()
def update_scenario(scenario_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """シナリオを部分更新する。fields は変更したいフィールドのみ含めればよい
    (PATCH 相当)。

    更新成功時は新しい content_version が +1 され、ScenarioVersion 履歴に
    edit_source='mcp' で自動記録される (Web 管理画面の「履歴」セクションで
    確認できる、ロールバック可能)。

    重要: このツールを呼ぶ前に、必ずユーザーに変更内容の diff を提示して
    承認を取ること。一度に大量のフィールドを変えず、1-3 フィールドの編集に
    絞ること。
    """
    return _request("PATCH", f"/ai-npc/scenarios/{scenario_id}/", json=fields)


@mcp.tool()
def duplicate_scenario(scenario_id: str) -> dict[str, Any]:
    """シナリオを現在のユーザー所有の private コピーとして複製する。
    元のシナリオは変更されない。複製版の name には ' (コピー)' が付与される。
    """
    return _request("POST", f"/ai-npc/scenarios/{scenario_id}/duplicate/")


@mcp.tool()
def get_scenario_versions(scenario_id: str) -> list[dict[str, Any]]:
    """シナリオの編集履歴を返す (最新版が先頭)。

    各要素には content_version / edit_source ('web' / 'admin' / 'mcp' /
    'rollback' 等) / edited_by_email / note / created_at が含まれる。
    snapshot 本体は含まれないので、特定版の中身を見るには
    `get_scenario_version` を使う。
    """
    data = _request("GET", f"/ai-npc/scenarios/{scenario_id}/versions/")
    return data.get("results", []) if isinstance(data, dict) else []


@mcp.tool()
def get_scenario_version(scenario_id: str, content_version: int) -> dict[str, Any]:
    """特定 content_version の snapshot (当時のシナリオ全体) を返す。
    diff 表示や rollback 前の確認に使う。
    """
    return _request(
        "GET", f"/ai-npc/scenarios/{scenario_id}/versions/{content_version}/"
    )


@mcp.tool()
def rollback_scenario(
    scenario_id: str, content_version: int, note: str = ""
) -> dict[str, Any]:
    """シナリオを指定 content_version の snapshot に戻す。

    実装: 古い snapshot を新しい content_version として書き戻す
    (履歴は消えない)。例えば現在 v9、v3 にロールバックした場合、v3 と同内容
    の v10 が生成される。

    重要: 実行前にユーザーに「v{N} の内容に戻します。よろしいですか?」と
    確認を取ること。
    """
    return _request(
        "POST",
        f"/ai-npc/scenarios/{scenario_id}/rollback/",
        json={"content_version": content_version, "note": note},
    )


# ────────────────────────────────────────────────────────────
# ConversationLog tools
# ────────────────────────────────────────────────────────────

@mcp.tool()
def list_conversation_logs(
    scenario_id: str | None = None,
    personality_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    """会話ログの一覧を返す (新しい順)。フィルタは全て任意。

    Args:
        scenario_id: 特定シナリオに絞る
        personality_id: 特定 Personality が含まれるログに絞る
        since: ISO 形式 (例: "2026-04-01") この日以降のログ
        until: ISO 形式 この日以前のログ
    """
    params = {
        k: v for k, v in {
            "scenario_id": scenario_id,
            "personality_id": personality_id,
            "since": since,
            "until": until,
        }.items() if v
    }
    data = _request("GET", "/ai-npc/conversation-logs/", params=params)
    return data.get("results", []) if isinstance(data, dict) else []


@mcp.tool()
def get_conversation_log(log_id: str) -> dict[str, Any]:
    """会話ログの詳細を返す (utterances / personalities_snapshot / metadata 含む)。

    utterances は Unity 側のスキーマ次第だが、典型的に:
        [{"t": <session 開始からの秒>, "kind": "player"|"npc"|"system",
          "text": "...", "speaker_id": "...", "displayName": "..."}, ...]
    """
    return _request("GET", f"/ai-npc/conversation-logs/{log_id}/")


# ────────────────────────────────────────────────────────────
# MCP Prompts (定型ワークフロー)
# ────────────────────────────────────────────────────────────

@mcp.prompt()
def analyze_log(scenario_id: str, log_id: str) -> str:
    """指定された会話ログを scenario の現行プロンプトと照合し、違反と改善点を
    抽出するワークフロー。
    """
    return f"""以下の手順で会話ログを scenario と照合してください。

# 入力
- scenario_id: {scenario_id}
- log_id: {log_id}

# 手順

1. `get_scenario("{scenario_id}")` でシナリオ全体を取得
   - focus_block_template / focus_block_template_supplementary / role_addendums /
     forbidden_phrases / response_format_rules を読み、ルールを把握する

2. `get_conversation_log("{log_id}")` でログを取得
   - utterances を時系列で読む
   - personalities_snapshot で誰が誰だったかを把握する

3. ルールと発話を照合し、以下を箇条書きで報告:
   a. **禁止フレーズ違反** (例: 「了解」「なるほど」を冒頭で使った発話)
   b. **応答ルール違反** (例: 1 展示 1 発話のはずが複数発話、遷移予告など)
   c. **役割逸脱** (例: Sub が事実を語る、Guide が場つなぎを口に出す)
   d. **その他気になる点** (繰り返し、自然さの欠如、テンポなど)

4. 各違反について:
   - 該当発話の時刻と話者
   - 違反の根拠 (scenario のどのルールに反するか引用)
   - 修正案 (どのフィールドをどう変えれば防げるか)

5. **編集はまだ実行しない**。報告のみで、ユーザーが「直して」と言ったら
   `propose_edit` プロンプトの流れに移る。
"""


@mcp.prompt()
def propose_edit(scenario_id: str, feedback: str) -> str:
    """ユーザーフィードバックに基づいて scenario の編集 diff を提案し、
    承認を取ってから反映するワークフロー。
    """
    return f"""以下のフィードバックに基づいて scenario "{scenario_id}" の編集案を提案してください。

# フィードバック
{feedback}

# 手順

1. `get_scenario("{scenario_id}")` で現行プロンプトを取得

2. フィードバックの各点について、変更すべきフィールドと変更内容を決める:
   - **focus_block_template**: 主役 NPC のメイン指示
   - **focus_block_template_supplementary**: Sub 役向け指示
   - **role_addendums.guide / .supplementary**: 役割別の追加指示
   - **forbidden_phrases**: 完全禁止フレーズ
   - **response_format_rules**: 応答フォーマット規則
   - その他 (cast_slots / enabled_tools / ui_panels 等)

3. **編集前に必ずユーザーに変更案を見せて承認を取る**。形式は:

   ```
   フィールド: role_addendums.supplementary
   変更内容: 末尾に以下を追加

     - 発話の冒頭で「了解」「OK」「なるほど」を使わない (Guide 用 focus block の
       禁止語と同等のルールを Sub にも適用する)
     - 「次の展示」「次のテーマ」など遷移に言及しない (それは Guide の専権事項)

   理由: ログ +0:56, +1:10, +1:27, +2:03 で Sub が冒頭禁止語と遷移予告を
   行っていたため。Sub には現在この禁止リストが渡されていない。

   この内容で適用しますか?
   ```

4. ユーザーから「OK」「適用して」等の承認を得たら:
   `update_scenario("{scenario_id}", {{<変更したいフィールドのみ>}})` を呼ぶ

5. 反映後、`get_scenario_versions("{scenario_id}")` で履歴を確認:
   - 最新エントリの edit_source が 'mcp' になっていることを確認
   - content_version が +1 されたことを確認
   - 必要なら 「履歴は管理 UI のシナリオ編集画面で確認できます」とユーザーに伝える

# 注意

- **一度に大量のフィールドを変えない**。1-3 フィールドの編集に絞る
- 元のスタイル (関西弁、絵文字なし、Bullet 形式等) は維持する
- 変更前後の対比を明確に提示
- 承認なしに `update_scenario` を呼ばない
"""


# ────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────

def main() -> None:
    """エントリーポイント (pyproject.toml の [project.scripts] から参照)。

    FastMCP.run() はデフォルトで stdio transport を使う (Claude Desktop 等の
    ローカル MCP クライアント向け)。SSE / HTTP transport は将来 Remote MCP
    対応時に検討する。
    """
    mcp.run()


if __name__ == "__main__":
    main()

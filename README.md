# poranos-mcp-ainpc

Claude Desktop / Claude Code から **Poranos AI NPC** のシナリオ・会話ログを操作するための MCP (Model Context Protocol) サーバ。

非エンジニアの運用担当が会話ログを読みながら自然言語で「Sub が冒頭で『なるほど』と言ってる、修正して」と Claude に伝えれば、Claude が必要なツールを呼び出してシナリオの prompt を編集する — というワークフローを実現する。

## 何ができるか

会話ログ閲覧 → 違反抽出 → プロンプト編集 → 履歴記録 までを Claude Desktop / Claude Code 内で完結させる:

- シナリオの一覧・詳細取得・編集 (PATCH)
- シナリオの複製、過去版へのロールバック
- 編集履歴 (audit log) の閲覧
- 会話ログの一覧・詳細取得 (Unity からアップロードされたセッションログ)

全編集は poranos.com 側の `ScenarioVersion` に `edit_source='mcp'` で自動記録され、**Web 管理画面の「履歴」セクション**から 1-click でロールバック可能。

## セットアップ

### 1. API キーを発行する

[https://poranos.com/app/account/](https://poranos.com/app/account/) にログインし、「**AI NPC API キー**」セクションから新しいキーを発行する。

- アクセスレベルは **「閲覧 + 編集」** (`ai-npc:write`) を推奨。「閲覧のみ」を選ぶと編集系の Tool が 403 を返す
- 発行直後に表示される `pk_...` を必ずコピーして保管する (二度と表示できない)

### 2. uv のインストール (まだなら)

`uvx` は [uv](https://docs.astral.sh/uv/) に同梱されています。

**Linux / macOS**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Claude Desktop の設定

設定ファイルに以下を追加:

**Linux**: `~/.config/Claude/claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "poranos-ainpc": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/kkoba23/poranos-mcp-ainpc.git",
        "poranos-mcp-ainpc"
      ],
      "env": {
        "PORANOS_API_KEY": "pk_あなたのキー"
      }
    }
  }
}
```

設定を保存したら Claude Desktop を再起動。

> **メモ**: 初回起動時に `uvx` が自動でリポジトリを clone + 依存解決するため少し時間がかかります (10-30 秒程度)。2 回目以降はキャッシュされます。

### Claude Code で使う場合

```bash
claude mcp add poranos-ainpc \
  -e PORANOS_API_KEY=pk_あなたのキー \
  -- uvx --from git+https://github.com/kkoba23/poranos-mcp-ainpc.git poranos-mcp-ainpc
```

#### ローカル開発

```bash
git clone https://github.com/kkoba23/poranos-mcp-ainpc.git
cd poranos-mcp-ainpc
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 環境変数で API キーをセット
export PORANOS_API_KEY=pk_あなたのキー

# サーバー起動 (stdio transport)
poranos-mcp-ainpc
```

## 提供される MCP Tools

### Scenario 系

| Tool | 用途 |
|---|---|
| `list_scenarios()` | シナリオ一覧 |
| `get_scenario(scenario_id)` | シナリオ詳細 (focus_block_template / role_addendums 等を含む) |
| `create_scenario(fields)` | 新規シナリオ作成 (name 必須、他はサーバ既定値) |
| `update_scenario(scenario_id, fields)` | シナリオを部分更新 (PATCH) |
| `duplicate_scenario(scenario_id)` | シナリオを private コピーとして複製 |
| `get_scenario_versions(scenario_id)` | 編集履歴 (meta のみ) |
| `get_scenario_version(scenario_id, content_version)` | 特定版の snapshot |
| `rollback_scenario(scenario_id, content_version, note?)` | 過去版に戻す |

### Personality 系

| Tool | 用途 |
|---|---|
| `list_personalities()` | NPC 人格 (Personality) 一覧 |
| `get_personality(personality_id)` | 人格詳細 (system_prompt / voice / character_id 等) |
| `create_personality(fields)` | 新規人格作成 (name / system_prompt / character_id 必須) |
| `update_personality(personality_id, fields)` | 人格を部分更新 |

### ConversationLog 系

| Tool | 用途 |
|---|---|
| `list_conversation_logs(scenario_id?, personality_id?, since?, until?)` | 会話ログ一覧 (フィルタ可) |
| `get_conversation_log(log_id)` | 会話ログ詳細 (utterances / personalities_snapshot / metadata) |

## 提供される MCP Prompts (定型ワークフロー)

| Prompt | 用途 |
|---|---|
| `analyze_log(scenario_id, log_id)` | ログを scenario と照合して違反を抽出 |
| `propose_edit(scenario_id, feedback)` | 自然言語フィードバックから編集案を提案 → 承認 → 反映 |

これらは Claude Desktop の `/` メニュー (slash commands) から呼び出せる。

## 典型的な使い方

1. Claude Desktop を開く
2. `/propose_edit` を選択 (または「Library Tour の昨日のログを見て、Sub が冒頭で『なるほど』と言ってるから直して」のように直接話しかける)
3. Claude が `list_scenarios` → `list_conversation_logs` → `get_conversation_log` で材料を集める
4. Claude が違反を抽出して報告し、編集案 (diff) を提示
5. **ユーザーが「OK」と承認**
6. Claude が `update_scenario` を呼んで反映、`get_scenario_versions` で履歴記録を確認

## セキュリティ

- API キーは SHA-256 ハッシュで poranos.com 側に保存され、生キーは発行時のみ表示される
- スコープは `ai-npc:read` / `ai-npc:write` の 2 種。read は GET のみ、write は read + 編集系
- キー漏洩時は [Account Detail 画面](https://poranos.com/app/account/) の「無効にする」ボタンで即座に失効可能 (DB 側 ソフト削除)
- 全編集が `ScenarioVersion` に `edit_source='mcp'` + `edited_by` 付きで記録される
- 不安なら **read scope のキー** で運用を始め、誤編集の心配を排除してから write に切り替えるのが安全

## 環境変数

| 変数 | 必須 | 既定 | 用途 |
|---|---|---|---|
| `PORANOS_API_KEY` | ✓ | — | poranos.com で発行した API キー |
| `PORANOS_API_BASE` | — | `https://api.poranos.com` | テスト用に dev サーバを指す等 |

## ライセンス

MIT

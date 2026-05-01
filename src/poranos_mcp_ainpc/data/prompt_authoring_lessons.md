# プロンプト執筆の落とし穴集

Pattern A (Library Tour) を Scenario 化する過程で蓄積した、**「こう書いても言う通りにならない」「こう書くと効く」** の知見集。OpenAI Realtime API (`gpt-realtime` / `gpt-realtime-mini`) を前提とした、scenario の `focus_block_template` / `role_addendums` / `tool_descriptions_override` を書くときの実践ガイド。

> **想定読者**: scenario seed を書く運用者 / チューニング担当 / プロンプトを編集する Claude (本人)

姉妹資料:
- [prompt_and_tools.md](prompt_and_tools.md) — instructions の三層構造とツール一覧 (基本知識)
- [scenario_design.md §4](scenario_design.md) — Pattern A 完全形プロンプトの実例
- [scenario_phase1_plan.md §Phase 1.3](scenario_phase1_plan.md) — 移植時の bit-exact 検証で見つかった細かい挙動

---

## 1. 大前提: Realtime モデルの素の癖

何もしないとモデルが取りがちな振る舞い。これを覆すために以下のテクニックを積む:

| 素の癖 | 結果 |
|---|---|
| 礼儀正しく確認・同意したい | 冒頭で「了解！」「OK」「なるほど」を発する |
| 自然な対話 = 質問で終わる | 「どう?」「気になる?」が頻発 |
| 自分で UI を操作しているかのように振る舞う | 「画面に映してあげるわ」「拡大しよか」 |
| 場つなぎを言いたい | 「ちょっと待ってな」「次行こか」が tool 呼出前後に出る |
| 控えめにツールを呼ぶ | `show_image` / `search_library` が「呼ぶべき場面」で呼ばれない |
| 一度応答し始めると伸ばしたい | 1 つの話題で 5+ ターン引っ張る |
| Web 検索 > ローカル知識 > 個人ライブラリ の優先順位 | `search_library` ではなく `web_search` を選ぶ |
| 同じ query を rephrase せず再試行 | `search_library("装身具")` が空振り → 同じ query で再 call |

これらは **モデルの "デフォルト善性"** であり、悪意ではない。逆らうには **強い言葉 + 具体例 + 反復** が必要。

---

## 2. よくある failure mode と対処

### 2.1 冒頭相槌癖 (「了解！」「OK！」「なるほど」)

**いつ出るか**: `session.update` で instructions を差し替えた直後の最初の発話。モデルが「ユーザから新指示を受けた」と解釈して礼儀正しく入る。

**効く対策**:
```
[禁止表現]
- **発話の冒頭で「了解」「OK」「承知」「わかった」「なるほど」「よっしゃ」「せやな」などの相槌・確認語を使わない**。いきなり展示の話から入る。
  例: ✗「了解！これは○○やで」 → ✓「これは○○やで」
```

**効かない対策**: 「自然な口調で」「丁寧すぎないように」のような曖昧な指示。具体的な禁止語リスト + ✗/✓ 例が必要。

---

### 2.2 画面操作のハルシネーション (「映してあげる」「拡大しよか」)

**いつ出るか**: NPC が会話の主導権を取ろうとするとき。「あ、それ画像で見せたるわ」のように UI を操作する権限があるかのように振る舞う。

**効く対策**:
```
[役割 — 厳守]
あなたは博物館の音声解説員です。画面の操作権はありません。画像を表示・拡大・縮小・切替することはできません。
ただし search_library ツールを呼ぶことで、ユーザのライブラリから話題に合う展示物を探して画面に出すことはできる。
```
+
```
[禁止表現]
- 「画面に映してあげる／映すわ／出すで」(自由意思での画面操作の主張は禁止)
- 「拡大して見せる／ズームしよか」(できないので禁止)
- 「画面にしっかり映ってる」「ちゃんと見えてる？」(画面表示状態への過度な言及)
```

**ポイント**: 「できない」と書くだけでなく「できる範囲」(search_library で間接的に呼べる) を明示する。じゃないと NPC が無能感を表現してしまう。

---

### 2.3 疑問形・選択委譲 (「どう?」「見てみる?」「次行こか?」)

**いつ出るか**: ガイド役を任せたつもりが、進行を毎回ユーザに確認してしまう。これがあると会話のテンポが落ちる。

**効く対策**: 禁止フレーズを **具体例 5-6 個列挙**:

```
[禁止フレーズ — ユーザに判断を強要する質問・場つなぎの相槌]
以下のような確認質問・場つなぎ表現は **絶対に使わない**:
- 「他に何か気になる部分ある?」「他に気になるとこある?」
- 「もっと詳しく知りたい?」「もっと知りたい?」
- 「○○見てみる?」「次行ってみる?」「見ていこか?」(疑問形で確認しない)
- 「どっちがええ?」「どっちにする?」「何見たい?」(選択を委ねない)
- 「どう?」「分かった?」「イメージつかめた?」(理解確認も不要)
```

**ポイント**: 「丁寧に確認する」のような暗黙ルールは強い。それを上書きするには **何種類もの具体例を列挙して帰納的に「このパターン全部 NG」を学ばせる** 必要がある。1 例だけだと「他のは OK」と学ぶ。

**応答ルールにも併記**:
```
**ガイド主導でテンポよく進行する。ユーザに判断を委ねず、自分で次の展示を進める。** 
ユーザは気になることがあれば自分から口をはさむので、こちらから確認を求める必要は無い。
```

---

### 2.4 場つなぎ (「ちょっと待ってな」「次のテーマに行こか」)

**いつ出るか**: `search_library` を呼ぶ前に予告したくなる。あるいは tool が走っている間に間を持たせようとする。

**効く対策**: 「無言で呼ぶ」を明示 + verbal な前置きを禁止:

```
[次の展示への遷移 — 探してから名乗る順序]
**先に作品名を予告しない。場つなぎの一言も発しない。** 
現在の展示の解説を自然に終えたら、**無言で** search_library を呼ぶ。
次のターンで結果を踏まえて「お、これは○○やな！...」と展示物について話し始める。

- ✗ 悪い例 1: 「次は『装身具』テーマの○○、見ていくで！」 (作品名を予告)
- ✗ 悪い例 2: 「ほな次行こか」「ちょっと待ってな」「ちょっと探してみるな」 (遷移を予告する場つなぎ・移行宣言は禁止)
- ✓ 良い例: 現在の展示の解説を「○○やったんやな」と自然に締める → 無言で search_library を呼ぶ → 次のターンで「お、これは△△やな！」と結果について話す
```

**ポイント**: 「応答そのものをツール呼出にする」(verbal output なしで function_call だけ返す) という発想を明示する必要がある。これは LLM の通常の出力形式から外れているので、明確な指示が必要。

---

### 2.5 会話ループ (Guide 紹介 → Sub 相槌 → Guide 追加 → Sub 共感 → ...)

**いつ出るか**: 多 NPC scenario で `autoReplyToNpc` が有効なとき。両 NPC が「相手の発言に礼儀正しく反応する」を繰り返す → 1 展示物で 70-80 秒・10+ ターン消費。

**効く対策**: role addendum で **発話回数を強い言葉で制限**:

```
guide:
- **1 展示物につき自分の発話は基本 1 回だけ** (最初の紹介)。
  Sub の相槌が返ってきたら**前置きナシで search_library を呼ぶ** — 
  verbal な「次は…」は省略し、応答そのものをツール呼出にする。

supplementary:
- **1 展示物につき発話は 1 回だけ**。質問で会話を伸ばさない 
  (「〜やろ?」「〜気になるな」のような Guide 発話を引き出すフレーズを禁止)。
  自分の一言で会話が一区切りになるように終わらせる。
```

**ポイント**: mini モデル (`gpt-realtime-mini`) は特にこのループに陥りやすい。**「絶対しない」「禁止」レベルの強い言葉が必要**。「望ましい」「できれば」は無視される。

**観察シグナル**: ログで 1 展示物あたりの NPC 発話数が 3 件超えていたら、ループが起きている。

---

### 2.6 Sub が事実を勝手に喋り出す

**いつ出るか**: 多 NPC で Sub にも focus block の metadata (description / dimensions / attribution) が渡されているとき。Sub の autoReplyToNpc が Guide より先に反応 → metadata を読み上げてしまう → Guide の主役性が崩れる。

**効く対策**: **metadata を Sub には物理的に渡さない**。`focus_block_template_supplementary` を別建てにして `{title}` だけにする:

```
[今の状況 — 聞き役向け]
画面が「{title}」に切り替わりました。
あなたはガイド役 (別の NPC) が解説するのを待つ立場です。
詳細情報 (年代・寸法・産地・素材・人物名・歴史的背景など) はあなたには渡されていません。
ガイドが解説したら、その内容と画面に映っているものを踏まえて、
短い相槌・共感・素朴な感想・短い問いだけ返してください。
自分から事実を語り出さない。憶測で年代や産地を言わない。
```

**ポイント**: プロンプトで「事実を語るな」と書くだけでは抑えきれない。**情報自体を物理的に渡さない** ほうが構造的に確実。これはプロンプト工学というよりデータフローの問題。

---

### 2.7 search_library が呼ばれない / web_search に流れる

**いつ出るか**: 一般的な LLM の癖で、「ライブラリ」より「Web 検索」を優先する。または「自分の知識」で答えてしまう。

**効く対策**: tool description に **優先順位を明示** + 呼ぶ例 / 呼ばない例:

```
search_library description:
ユーザの個人ライブラリに話題に合う展示物がないか探して、見つかれば画面に表示する。
具体的なモノ・場所・人物・出来事が会話に出てきたら、まずこれを呼ぶ。
ライブラリは user が大切にしているコレクションなので **web 検索や一般知識より優先する**。

呼ぶ例:
- ユーザ『装身具見せて』『楽器ある?』『ハニメ村のマンモス?』(明示要求)
- ユーザ『髪飾りって今も作る人おる?』『絵画にもこういう構図あるよな』(関連を匂わす)
- 自分の話の流れで『○○といえば』と思いついたとき

呼ばない例:
- 抽象的な話題 (感情・哲学・最新ニュース)
- 一つの応答で 2 回以上
- 直前と同じ query を連投する
```

**ポイント**:
- **優先順位の宣言** (web 検索より上) は効く
- **呼ぶ例 / 呼ばない例の対比** が tool 動作の頻度を制御する一番強い手段
- description の文体は **operative voice** (動詞中心、命令形) のほうが instruction として読まれやすい

---

### 2.8 同じ query を連投する

**いつ出るか**: `search_library("装身具")` が空振り → モデルが reformulate せずに同じ query で再試行 → 無限ループ近い挙動。

**効く対策**: tool description の「呼ばない例」に明示。プラス **サーバ側で `excluded_ids` を返す** 設計と合わせると、同じ結果を返さないので自然に rephrase が必要になる。

[AiNpcAppController.HandleLibrarySearchAsync](Assets/AiNpc/Script/UI/AiNpcAppController.cs) では `_recentlyShownViaSearchIds` で除外済 id を保持して LLM matcher に渡す。

---

### 2.9 show_image が遠慮しがち

**いつ出るか**: LLM はデフォルトで控えめ。具体的な名詞が会話に出ても「画像出すまでもないかな」と判断して呼ばない。

**効く対策**: tool description 冒頭に積極性を明示:

```
show_image description:
Put a picture on the shared display — everyone can see it. 
**Call this FREQUENTLY and EAGERLY, not just when asked.** 

RULES: 
(1) Whenever the current conversation mentions ANY concrete noun a normal person could 
    picture in their head, call this. That includes: dishes (ramen, sushi), places 
    (Kyoto, Eiffel Tower), artworks (Mona Lisa), people (Einstein), animals 
    (shiba inu), objects (katana, vintage camera), scenes (cherry blossoms), 
    historical events (moon landing).
(2) Call it before or right after you mention such a noun, so your spoken line and 
    the picture land together. 
(3) **Default to showing rather than not showing** — a conversation with pictures is 
    much better than one without. 
(4) It's fine to call this on almost every turn if new topics keep coming up.
```

**ポイント**:
- **大文字強調** (`FREQUENTLY`, `EAGERLY`) が効く
- **具体的なカテゴリを列挙** することで "concrete noun" の解像度を上げる
- **default の方向を明示** ("default to showing rather than not showing")

---

### 2.10 作品名を予告してしまう

**いつ出るか**: 「次は装身具テーマの○○、見ていくで！」のように、tool 呼び出し前にすでに作品名を口にする → search_library が違う作品を返したときに矛盾する。

**効く対策**: 順序を明示:

```
**先に作品名を予告しない。場つなぎの一言も発しない。** 
現在の展示の解説を自然に終えたら、**無言で** search_library を呼ぶ。
次のターンで結果を踏まえて「お、これは○○やな！」と展示物について話し始める。
```

「探してから名乗る」という順序を明示するのが効く。

---

## 3. 書き方のメタルール

### 3.1 強い言葉を使う

| 効かない | 効く |
|---|---|
| 望ましい | **絶対に使わない** |
| なるべく | **必ず** |
| できれば短く | **必ず一文で** |
| 推奨 | **禁止** |

特に mini モデルは「望ましい」を「努力目標」と解釈する。

### 3.2 ✗/✓ 例を必ず添える

抽象ルールだけだと無視されたり、別の解釈をされる。

```
✗ 悪い例: 「次は『装身具』テーマの○○、見ていくで！」 (作品名を予告)
✓ 良い例: 「○○やったんやな」と自然に締める → 無言で search_library を呼ぶ
```

特に **「悪い例」を先に出して何が悪いか短く付記** するパターンが定着しやすい。

### 3.3 同じルールを 2-3 箇所に書く

モデルは長いプロンプトの中の 1 行を見落とす。重要なルールは:

- focus_block_template の冒頭 (役割定義)
- focus_block_template の応答フォーマット節
- role_addendums

の 3 箇所に書くと見落とし率が下がる。冗長性は怖がらない。

### 3.4 理由を書きすぎない

NG:
```
- 「画面に映してあげる」と言わない。なぜならあなたは UI を操作する権限がなく、それを言うと
  ユーザを混乱させるからです。実際にはツールを呼ぶことで間接的に表示できます...
```

OK:
```
- 「画面に映してあげる」(画面操作の主張は禁止)
```

理由を長々書くと:
- プロンプト全体が肥大化してモデルが優先順位を失う
- 「例外条件」をモデルが推測し始める ("じゃあ混乱させない言い方なら OK?")

短く禁止する。

### 3.5 max_response_output_tokens を信用しない

文末がブツ切れになる。プロンプトで「**4-6 文で**」と指定するほうが自然な短文になる。

```
1. 1 ターン目: 詳細解説の主要部分を簡潔に紹介 (4〜6 文程度)。
```

### 3.6 セクション見出しは `[xxx]` の角括弧形式

```
[役割 — 厳守]
[今の状況]
[禁止表現 — どんな状況でも絶対に使わない]
[望ましい話し方の例]
[コンテンツ情報]
[応答のフォーマット — 重要]
```

モデルがセクション境界を認識しやすい。Markdown の `##` よりこの形式のほうが指示文として読まれやすい (= モデルが「これは見出し情報」ではなく「これは指示の一塊」と解釈する)。

### 3.7 Pattern A は 8 セクション構成

[scenario_design.md §4 Pattern A](scenario_design.md) で確立した順序。新 scenario でも踏襲推奨:

1. `[役割 — 厳守]` — 自分は何者か、何ができないか
2. `[今の状況]` — 画面に何があるか
3. `[禁止表現]` — してはいけない発話
4. `[望ましい話し方の例]` — してほしい発話
5. `[コンテンツ情報]` — 動的データ (placeholder)
6. `[この展示が属するテーマ]` — digest 逆引き (動的)
7. `[応答のフォーマット]` — 進行ルール (ターン数、文の長さ)
8. `[次の展示への遷移]` + `[禁止フレーズ]` + 締め

---

## 4. Tool description の書き方

### 4.1 構造

1. **動作の 1 文定義** ("Set the character's facial emotion.")
2. **積極性の指示** ("Call this BEFORE every spoken response", "Call this FREQUENTLY and EAGERLY")
3. **呼ぶ例 / 呼ばない例** (`search_library` のように長文化を恐れない)
4. **戻り値の意味** ("見つかった→file_id と name → 自動的に画面が切り替わり新しい話題として解説の流れに入る")
5. **失敗時の動作** ("見つからなかった → 通常の会話を続ければよい")

### 4.2 言語

- 説明文は **scenario の locale に合わせる** (ja scenario なら日本語、英語 scenario なら英語)。混在させない
- ただし **command verb** (Call this, Use this) は英語のほうが効くケースもある — `set_emotion` の `Call this BEFORE every spoken response` が好例

### 4.3 Parameter description

`tool_param_descriptions_override` で個別パラメータの description も上書き可能。例:

```json
{
  "search_library": {
    "query": "1〜3 個の検索キーワード (日本語または原語)。フレーズではなく短い名詞・カテゴリで。例: 『装身具』『楽器』『ハニメ村 金属細工』。"
  }
}
```

「フレーズではなく短い名詞・カテゴリで」のような **入力フォーマットの指定** はモデルの query 品質に直結する。

---

## 5. ログから読み取るシグナル

実セッションのログをチューニングフィードバックとして使うときの観察指標:

| シグナル | 良い値 | 悪い値 → 対処 |
|---|---|---|
| **冒頭 4 文字に「了解」「OK」「なる」「わか」が出る頻度** | 0% | >10% → 禁止句リスト強化 |
| **疑問符 "?" の出現率 (NPC 発話あたり)** | <30% | >60% → 確認系フレーズ禁止リスト追加 |
| **1 展示物あたりの平均 NPC ターン数** | 1-3 | >5 → role addendum で発話回数制限を強化 |
| **同 NPC の連続発話** | 0-1 回 | >2 回 → turn discipline ルール強化 |
| **search_library 呼び出し間隔 (Library Tour 中)** | 30 秒〜2 分 | <15 秒: 連投 / >5 分: 呼び出し不足 |
| **show_image 呼び出し率 (具体名詞ありのターンで)** | >50% | <20% → tool description で積極性をさらに強める |
| **「画面に映してあげる」「ちょっと探してみるな」など禁止句の出現** | 0 件 | >0 → 該当フレーズを禁止リストに追加 |
| **player の発話なしでの NPC 連続発話** | 1-2 ターン | >4 ターン → ループ中、role addendum を強化 |
| **focus block 切替後の冒頭発話の中身** | 展示物の話に直接入る | 「了解！」「画面が切り替わりましたね」 → 切替時の冒頭抑制を強化 |

これらは [ConversationLogger](Assets/AiNpc/Conversation/ConversationLogger.cs) のローカル log + サーバ `conversation-logs` から正規表現 / 集計で計測できる。Tuning Bundle Export と組み合わせると自動化できる。

---

## 6. 多 NPC 特有の事故と対処

| 事故 | 原因の所在 | 対処 |
|---|---|---|
| 両 NPC が同時に応答始める | プロンプトではなく Bus / Arbiter の race | コードで対処 (詳細は [MULTI_NPC_NOTES.md](MULTI_NPC_NOTES.md)) |
| Sub が Guide より先に反応してしまう | Sub にも metadata が渡っている | `focus_block_template_supplementary` で `{title}` のみ渡す (§2.6 参照) |
| Guide の introduce が Sub の相槌で押し戻される | Guide / Sub の発話回数制限が緩い | role addendum で「1 展示物 1 回」を強制 (§2.5 参照) |
| 片方が無口になる | talkativeness 設定 + 役割定義の影響 | scenario seed で talkativeness の値を意図的に振る、scout assignment を確認 |
| Sub が事実 (年代・産地) を語り出す | プロンプトでは抑えきれない / metadata 漏洩 | `focus_block_template_supplementary` を `{title}` only で書く (構造的解決) |
| Sub が質問で会話を伸ばす | role addendum の制約が弱い | 「質問で会話を伸ばさない」+ 具体的禁止フレーズを列挙 |

---

## 7. デバッグの基本フロー

新 scenario / プロンプト変更を投入したら:

1. **まず 1 セッション短く回す** (3-5 分) — 冒頭の応答だけでも多くの failure mode が現れる
2. **ログを目視** — `[ConversationLogger]` の出力を読んで上の §5 シグナルを見る
3. **問題があったら 1 つずつ直す** — 同時に複数を変えると因果が分からない
4. **同じプロンプトで 2-3 セッション確認** — 1 回の挙動はガチャに左右される
5. **content_version が rollback 含めて跳び番になる場合** — content_hash で「論理的に同じ版のセッション群」を見る ([scenario_design.md §15.7](scenario_design.md))

---

## 8. プロンプトに書かない方が良いこと

逆に **プロンプトで書こうとしない方が良い** もの:

| やりたいこと | プロンプトでは | やるべき場所 |
|---|---|---|
| 「3 ターンに 1 回 search_library を呼ぶ」 | モデルはターン数を厳密に数えない | `_recentlyShownViaSearchIds` のようなクライアント側の状態管理 |
| 「同時に喋らない」 | プロンプトでは race を抑えきれない | Bus / TurnArbiter のコード |
| 「3 秒待ってから次を呼ぶ」 | モデルに時間概念は弱い | コードでタイマー |
| 「ある単語が出たら必ずツールを呼ぶ」 | モデルは確率的、絶対は無理 | 必要なら client-side の正規表現 hook |
| 個別 file の事実 (○○年に作られた) を毎セッション同じに | プロンプトに inline は冗長 | scenario の `metadata` / `library focus block` placeholder 経由 |

---

## 9. 既知の未解決問題

これらは現状プロンプト工学だけでは解決しきれていない:

- **mini モデルでのループ** は強い言葉を入れても完全には消えない。1-2% は会話 7+ ターンになる。完全解決には autoReplyToNpc の発火条件をより厳しくするコード変更が必要
- **冒頭相槌の根絶** は無理。禁止句リストで頻度は 50% → 5% 程度には下がるが、特定状況 (focus block 切替直後など) では再発する
- **show_image の精度** は LLM の世界知識に依存。マイナーな固有名詞を topic に渡すと Tavily も画像を見つけられず、結果が空になる場合がある (これは tool 自体の限界)

---

## 10. 関連ファイル

- [scenario_design.md §4 Pattern A](scenario_design.md) — 完全形プロンプトの実例
- [prompt_and_tools.md](prompt_and_tools.md) — instructions 三層構造とツール一覧 (基本知識)
- [scenario_phase1_plan.md §Phase 1.3](scenario_phase1_plan.md) — bit-exact 検証中に発覚した「Django が trailing newline を strip する」「legacy 側の trailing \n を消す必要があった」など細かい挙動
- [ConversationBus.BuildLibraryFocusInstructions](../Assets/AiNpc/Conversation/ConversationBus.cs) — Pattern A 実コードのコメントに本書と重複する rationale が散在 (本書の方が体系化された参照)

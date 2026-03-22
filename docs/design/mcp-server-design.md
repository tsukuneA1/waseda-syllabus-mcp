# 設計ドキュメント: MCP Server Implementation

## 概要

早稲田大学シラバス情報を LLM (Claude 等) から利用可能にする MCP (Model Context Protocol) サーバーの実装設計。
`packages/mcp-server` パッケージとして実装し、FastAPI (`packages/api`) 経由でシラバスデータにアクセスする。

## 目標

- **主要な目標**
  - Claude Desktop から早稲田大学シラバスを検索・参照できる MCP ツールを提供する
  - Python MCP SDK を使い、MCP プロトコルに準拠したサーバーを実装する
  - API パッケージ経由でデータアクセスを行い、責務を分離する

- **非目標**
  - データベースへの直接アクセス（API パッケージが担う）
  - シラバスデータのクロール・収集（libs パッケージが担う）
  - HTTP トランスポートによる公開 API（初期実装は stdio のみ）

## 背景

早稲田大学のシラバス情報は Web 上に分散しており、LLM から直接参照するには不便。
MCP サーバーを構築することで Claude がシラバスを検索・参照し、履修計画のサポートなどを行えるようにする。

アーキテクチャの詳細は [backend-architecture.md](./backend-architecture.md) を参照。
MCP サーバーは `mcp-server → api → libs` の依存チェーンの最上位に位置する。

## 設計

### アーキテクチャ

```
Claude Desktop
    ↓ MCP protocol (stdio)
mcp-server (packages/mcp-server)
    ↓ HTTP (httpx)
api (packages/api / FastAPI)
    ↓
libs → PostgreSQL
```

MCP サーバーは stdio トランスポートで起動し、Claude Desktop からサブプロセスとして呼び出される。
データアクセスは `api` パッケージの HTTP エンドポイント経由で行う（直接 DB アクセスはしない）。

### ディレクトリ構造

```
packages/mcp-server/
├── pyproject.toml
└── src/
    └── waseda_mcp/
        ├── __init__.py
        ├── server.py        # MCP サーバー起動・設定
        ├── client.py        # API クライアント (httpx)
        ├── tools/
        │   ├── __init__.py
        │   ├── search.py    # search_syllabus ツール
        │   ├── get.py       # get_syllabus ツール
        │   └── recommend.py # recommend_courses ツール
        └── types.py         # ツール入出力の型定義
```

### ツール定義

#### `search_syllabus`

シラバスをキーワード・条件で検索する。

```python
@mcp.tool()
async def search_syllabus(
    query: str,
    year: int | None = None,
    semester: Literal["spring", "fall", "full_year"] | None = None,
    language: Literal["ja", "en"] | None = None,
    limit: int = 10,
) -> list[CourseSummary]:
    ...
```

#### `get_syllabus`

科目コードを指定してシラバス詳細を取得する。

```python
@mcp.tool()
async def get_syllabus(
    course_code: str,
    year: int | None = None,
) -> CourseDetail:
    ...
```

#### `recommend_courses`

指定した条件・興味に基づいて履修候補を推薦する。

```python
@mcp.tool()
async def recommend_courses(
    interests: list[str],
    year: int | None = None,
    semester: Literal["spring", "fall", "full_year"] | None = None,
    limit: int = 5,
) -> list[CourseSummary]:
    ...
```

### 入力スキーマ設計

MCP SDK の `@mcp.tool()` デコレータが Python の型アノテーションから JSON Schema を自動生成する。
パラメータの説明は docstring で記述する。

```python
@mcp.tool()
async def search_syllabus(
    query: str,
    year: int | None = None,
    semester: Literal["spring", "fall", "full_year"] | None = None,
    language: Literal["ja", "en"] | None = None,
    limit: int = 10,
) -> list[CourseSummary]:
    """
    早稲田大学のシラバスをキーワードで検索する。

    Args:
        query: 検索キーワード（科目名、教員名、キーワード等）
        year: 対象年度（省略時は最新年度）
        semester: 開講学期。"spring"=春学期, "fall"=秋学期, "full_year"=通年
        language: 授業実施言語。"ja"=日本語, "en"=英語
        limit: 取得件数上限（デフォルト: 10、最大: 50）
    """
```

### 出力フォーマット設計

#### `CourseSummary`（一覧表示用）

```python
class CourseSummary(BaseModel):
    course_code: str       # 科目コード (例: "2D00000001")
    title: str             # 科目名
    title_en: str | None   # 英語科目名
    instructor: str        # 担当教員名
    semester: str          # 開講学期
    credits: int           # 単位数
    language: str          # 授業実施言語
    campus: str            # 開講キャンパス
    year: int              # 対象年度
```

#### `CourseDetail`（詳細表示用）

```python
class CourseDetail(CourseSummary):
    description: str            # 授業概要
    objectives: str             # 学習目標
    schedule: list[WeeklyTopic] # 週ごとの授業計画
    grading: str                # 成績評価方法
    textbooks: list[str]        # 教科書
    references: list[str]       # 参考文献
    notes: str | None           # 備考・注意事項
    url: str                    # 早稲田シラバスページ URL
```

#### `WeeklyTopic`

```python
class WeeklyTopic(BaseModel):
    week: int      # 第N回
    topic: str     # 授業内容
```

MCP ツールの戻り値は Pydantic モデルを `model_dump()` して JSON 文字列として返す。
LLM が読みやすいよう `ensure_ascii=False` で日本語をそのまま出力する。

### DB アクセス方法

**API 経由（HTTP）を採用。直接 DB アクセスはしない。**

理由:
- 責務の分離: DB スキーマ変更の影響を MCP サーバーから隔離できる
- 将来の拡張: MCP サーバーを別ホストにデプロイする際に変更不要
- テスト容易性: API クライアントをモックするだけでテスト可能

API クライアントは `httpx.AsyncClient` を使い、接続先 URL は環境変数 `WASEDA_API_BASE_URL` で設定する（デフォルト: `http://localhost:8000`）。

```python
# client.py
import httpx
import os

class SyllabusApiClient:
    def __init__(self):
        self.base_url = os.getenv("WASEDA_API_BASE_URL", "http://localhost:8000")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def search(self, **params) -> list[dict]:
        resp = await self._client.get("/courses/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_course(self, course_code: str, year: int | None) -> dict:
        resp = await self._client.get(f"/courses/{course_code}", params={"year": year})
        resp.raise_for_status()
        return resp.json()
```

### エラーハンドリング

MCP ツール内で発生した例外は MCP SDK が `isError: true` のレスポンスとして LLM に返す。
ユーザーが意味のあるメッセージを受け取れるよう、例外を適切にラップする。

| エラー種別 | 対処 |
|---|---|
| API 接続失敗 (`httpx.ConnectError`) | 「APIサーバーに接続できません。サーバーが起動しているか確認してください。」を返す |
| 科目が見つからない (`404`) | 「指定された科目コードが見つかりません: {code}」を返す |
| API エラー (`5xx`) | 「サーバーエラーが発生しました。しばらく待ってから再試行してください。」を返す |
| タイムアウト (`httpx.TimeoutException`) | 「リクエストがタイムアウトしました。再試行してください。」を返す |
| バリデーションエラー | パラメータの説明を含むメッセージを返す |

```python
# tools/search.py の例外処理パターン
try:
    results = await client.search(query=query, ...)
except httpx.ConnectError:
    raise McpError("API サーバーに接続できません。サーバーが起動しているか確認してください。")
except httpx.HTTPStatusError as e:
    if e.response.status_code == 404:
        raise McpError(f"検索結果が見つかりませんでした: {query}")
    raise McpError(f"API エラー: {e.response.status_code}")
except httpx.TimeoutException:
    raise McpError("リクエストがタイムアウトしました。再試行してください。")
```

### Claude Desktop 設定方法

Claude Desktop の設定ファイル (`claude_desktop_config.json`) に以下を追加する。

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "waseda-syllabus": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/waseda-syllabus-mcp/apps/backend",
        "--package",
        "waseda-mcp",
        "python",
        "-m",
        "waseda_mcp.server"
      ],
      "env": {
        "WASEDA_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

**注意**: `/path/to/waseda-syllabus-mcp` は実際のリポジトリパスに置き換える。
Claude Desktop を再起動すると設定が反映される。

API サーバーは別途起動しておく必要がある:

```bash
cd apps/backend
uv run --package waseda-api uvicorn waseda_api.main:app --reload
```

## 検討した代替案

| 案 | 採用しなかった理由 |
|---|---|
| DB への直接アクセス | 責務が混在し、スキーマ変更時の影響範囲が広がる |
| HTTP トランスポート (SSE) | Claude Desktop は stdio 接続を前提にしており、初期実装には不要 |
| `recommend_courses` を LLM プロンプトで実装 | サーバー側でロジックを持つことで再現性が高く、テストしやすい |
| ツールを1つに統合 | 引数が複雑になり LLM が使いづらくなる |

## 未解決の質問

- [ ] `recommend_courses` の推薦ロジック: ルールベース vs ベクトル検索
- [ ] MCP サーバーの stdio 以外のトランスポート対応タイミング
- [ ] API サーバーの認証・API キー管理

## セキュリティ/プライバシーの考慮事項

- シラバス情報は公開情報のため、個人情報は含まない
- API の接続先 URL は環境変数で管理し、ハードコードしない
- Claude Desktop はローカル実行のため、ネットワーク公開は不要

## テスト戦略

- **Unit テスト**: 各ツール関数を `httpx.MockTransport` でAPIモックしてテスト
- **Integration テスト**: 実 API サーバーに接続してエンドツーエンドでツール呼び出しをテスト
- **エラーケーステスト**: 接続エラー・タイムアウト・404 等の異常系を網羅

```bash
# テスト実行
uv run pytest packages/mcp-server/tests/ -v
```

## 参考資料

- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP 仕様書](https://spec.modelcontextprotocol.io/)
- [Claude Desktop MCP 設定ガイド](https://docs.anthropic.com/en/docs/build-with-claude/mcp)
- [backend-architecture.md](./backend-architecture.md) - バックエンド全体のアーキテクチャ

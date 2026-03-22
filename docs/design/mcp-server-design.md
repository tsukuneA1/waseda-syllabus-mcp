# 設計ドキュメント: MCP Server Implementation

## 概要

早稲田大学シラバス情報を MCP (Model Context Protocol) クライアントから利用可能にするサーバーの実装設計。
`packages/mcp-server` パッケージとして実装し、FastAPI (`packages/api`) 経由でシラバスデータにアクセスする。

## 目標

- **主要な目標**
  - MCP クライアントから早稲田大学シラバスを検索できる MCP ツールを提供する（MVP: `search_syllabus` のみ）
  - Python MCP SDK を使い、MCP プロトコルに準拠したサーバーを実装する
  - API パッケージ経由でデータアクセスを行い、責務を分離する

- **非目標**
  - データベースへの直接アクセス（API パッケージが担う）
  - シラバスデータのクロール・収集（libs パッケージが担う）
  - HTTP トランスポートによる公開 API（初期実装は stdio のみ）

## 背景

早稲田大学のシラバス情報は Web 上に分散しており、LLM から直接参照するには不便。
MCP サーバーを構築することで MCP 対応クライアントがシラバスを検索・参照し、履修計画のサポートなどを行えるようにする。

アーキテクチャの詳細は [backend-architecture.md](./backend-architecture.md) を参照。
MCP サーバーは `mcp-server → api → libs` の依存チェーンの最上位に位置する。

## 設計

### アーキテクチャ

```
MCP クライアント (Claude Desktop, Cursor 等)
    ↓ MCP protocol (stdio)
mcp-server (packages/mcp-server)
    ↓ HTTP (httpx)
api (packages/api / FastAPI)
    ↓
libs → PostgreSQL
```

MCP サーバーは stdio トランスポートで起動し、MCP クライアントからサブプロセスとして呼び出される。
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
        │   └── search.py    # search_syllabus ツール (MVP)
        └── types.py         # ツール入出力の型定義
```

### ツール定義

#### `search_syllabus`（MVP）

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

MCP SDK の `@mcp.tool()` デコレータが Python の型アノテーションから JSON Schema を自動生成する。
パラメータの説明は docstring で記述する。

### 出力フォーマット設計

#### `CourseSummary`

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

MCP ツールの戻り値は Pydantic モデルを `model_dump()` して JSON 文字列として返す。
`ensure_ascii=False` で日本語をそのまま出力する。

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
```

### エラーハンドリング

MCP ツール内で発生した例外は MCP SDK が `isError: true` のレスポンスとしてクライアントに返す。
ユーザーが意味のあるメッセージを受け取れるよう、例外を適切にラップする。

| エラー種別 | 対処 |
|---|---|
| API 接続失敗 (`httpx.ConnectError`) | 「APIサーバーに接続できません。サーバーが起動しているか確認してください。」を返す |
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
    raise McpError(f"API エラー: {e.response.status_code}")
except httpx.TimeoutException:
    raise McpError("リクエストがタイムアウトしました。再試行してください。")
```

### MCP クライアント設定方法

stdio トランスポートで起動するため、MCP クライアント側でサブプロセスとして登録する。
以下は Claude Desktop を例にした設定だが、他の MCP 対応クライアント（Cursor 等）も同様の方式で設定できる。

**設定ファイル例** (`claude_desktop_config.json` または各クライアントの設定):

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

API サーバーは別途起動しておく必要がある:

```bash
cd apps/backend
uv run --package waseda-api uvicorn waseda_api.main:app --reload
```

## 検討した代替案

| 案 | 採用しなかった理由 |
|---|---|
| DB への直接アクセス | 責務が混在し、スキーマ変更時の影響範囲が広がる |
| HTTP トランスポート (SSE) | 初期実装には不要、将来の要件に応じて追加検討 |
| MVP で複数ツールを実装 | `get_syllabus` や `recommend_courses` は LLM 側で代替可能な部分が多く、まず `search_syllabus` で価値検証する |

## 未解決の質問

- [ ] MVP 以降に追加するツールの優先順位（`get_syllabus` vs `recommend_courses` vs 他）
- [ ] MCP サーバーの stdio 以外のトランスポート対応タイミング
- [ ] API サーバーの認証・API キー管理

## セキュリティ/プライバシーの考慮事項

- シラバス情報は公開情報のため、個人情報は含まない
- API の接続先 URL は環境変数で管理し、ハードコードしない
- ローカル実行（stdio）のため、ネットワーク公開は不要

## テスト戦略

- **Unit テスト**: `search_syllabus` ツールを `httpx.MockTransport` で API モックしてテスト
- **Integration テスト**: 実 API サーバーに接続してエンドツーエンドでツール呼び出しをテスト
- **エラーケーステスト**: 接続エラー・タイムアウト等の異常系を網羅

```bash
uv run pytest packages/mcp-server/tests/ -v
```

## 参考資料

- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP 仕様書](https://spec.modelcontextprotocol.io/)
- [backend-architecture.md](./backend-architecture.md) - バックエンド全体のアーキテクチャ

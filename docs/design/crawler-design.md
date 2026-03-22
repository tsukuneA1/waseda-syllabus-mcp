# 設計ドキュメント: Crawler Strategy

## 概要

早稲田大学シラバスサイト (`wsl.waseda.jp/syllabus/`) からシラバスデータを収集するクローラーの設計。
学部ごとに異なるpKey構造に対応するため、**pKey生成方式**と**検索API方式**の2つの戦略を使い分ける。

## 目標

- **主要な目標**
  - 基幹理工学部のシラバスをpKey生成方式で効率的に収集する
  - 他学部のシラバスを検索API経由で収集する
  - サイトに不必要な負荷をかけないレート制限を実装する

- **非目標**
  - リアルタイムクローリング（定期バッチ実行を想定）
  - ログイン後のコンテンツ取得（公開シラバスのみ対象）
  - 807,127件の全データを常時最新化（年度単位での更新を想定）

## 背景

早稲田大学のシラバスシステムは以下の3ページで構成される：

```
JAA101.php  検索条件入力
    ↓
JAA103.php  検索結果一覧（JavaScriptで動的生成）
    ↓
JAA104.php?pKey=XXXX  シラバス詳細
```

シラバス詳細ページ（JAA104.php）は28文字の `pKey` パラメータで一意に識別される。
pKeyが判明すれば直接アクセスが可能。検索結果ページのリンクはJavaScript動的生成のため、
静的HTMLスクレイピングではpKeyを取得できない。

## 設計

### アーキテクチャ

```
CrawlerOrchestrator
    ├── KSRICrawler (基幹理工学部)
    │   └── PKeyGenerator → httpx → SyllabusParser
    └── GenericCrawler (他学部)
        └── PlaywrightSearcher → pKey抽出 → httpx → SyllabusParser
                    ↓
              PostgreSQL (syllabuses テーブル)
```

### pKey構造（基幹理工学部）

pKeyは**28文字固定**で前半16文字 + 後半12文字で構成される。

```
位置   文字数  内容              例
1-2    2       年度下2桁         26      (2026年度)
3-4    2       学科コード        03
5-6    2       科目区分コード    01
7-10   4       科目コード        2001    (学年+連番)
11-12  2       クラスコード      01
13-16  4       開講年度(4桁)     2026
17-18  2       年度（繰り返し）  26
19-20  2       学科（参照先）    03      (通常は前半と同じ)
21-22  2       区分（参照先）    01
23-26  4       科目（参照先）    2001
27-28  2       年度（繰り返し）  26
```

#### 学科コード（基幹理工学部）

| コード | 学科 |
|--------|------|
| `00` | 基幹共通科目 |
| `01` | 数学科 |
| `02` | 応用数理学科 |
| `03` | 情報理工学科 |
| `05` | 未確認（物理系の可能性） |
| `07` | 情報通信学科 |

#### 科目区分コード

| コード | 区分 |
|--------|------|
| `01` | 専門必修 |
| `02` | 選択必修 |
| `03` | 専門選択 |
| `04` | その他 |

#### 科目コードの読み方

```
7-10の4文字: 先頭1桁が学年、残り3桁が連番
  2xxx = 2年次科目
  3xxx = 3年次科目
  4xxx = 4年次科目
```

#### 後半部分（参照先）の扱い

複数学科で同一内容を開講する場合、後半が前半と異なる値になる：

```
例：情報数学A（情報通信学科 dept=07）
pKey前半: 26 07 02 2007 01 2026
pKey後半: 26 03 03 2002 26
          ↑ 情報理工学科(03)の科目2002を参照
```

この場合、後半はコンテンツの正規実体（マスター科目）を示す。
pKey生成時は後半も前半と同じ値で試み、存在しない場合はスキップする。

### pKey生成戦略（基幹理工学部）

```python
def generate_pkeys(year: int, dept_code: str) -> list[str]:
    """基幹理工学部のpKey候補を総当たりで生成する"""
    year_s = str(year)[-2:]  # 下2桁
    year_full = str(year)

    pkeys = []
    for cat in ["01", "02", "03", "04"]:
        for grade in [2, 3, 4]:
            for num in range(1, 100):  # 連番の上限は余裕を持たせる
                code = f"{grade}{num:03d}"
                for cls in ["01", "02", "03"]:  # クラスコード
                    pkey = (
                        f"{year_s}{dept_code}{cat}{code}{cls}{year_full}"
                        f"{year_s}{dept_code}{cat}{code}{year_s}"
                    )
                    pkeys.append(pkey)
    return pkeys
```

存在しないpKeyへのアクセスはエラーページが返るため、レスポンスの内容で判定してスキップする。

### 検索API戦略（他学部）

他学部はpKey構造が学部固有のため総当たりが困難。JAA103.phpのGETパラメータで絞り込み後、
PlaywrightでDOM上のリンクからpKeyを抽出する。

#### 動作確認済みパラメータ

| パラメータ | 効果 | 例 |
|-----------|------|----|
| `pLng` | 言語切替 | `jp` |
| `p_gakubu` | 学部で絞り込み | `51`（基幹理工） |
| `nendo` | 年度で絞り込み | `2026` |
| `p_nendo` | 効かない | - |
| `p_keyw` | 効かない（POSTのみ） | - |

#### Playwright操作フロー

```python
async def fetch_pkeys_via_search(
    page: Page, gakubu: str, nendo: str
) -> list[str]:
    url = (
        "https://www.wsl.waseda.jp/syllabus/JAA103.php"
        f"?pLng=jp&p_gakubu={gakubu}&nendo={nendo}"
    )
    await page.goto(url)
    await page.wait_for_load_state("networkidle")

    # リンクのhref属性からpKeyを抽出
    links = await page.query_selector_all("a[href*='JAA104.php']")
    pkeys = []
    for link in links:
        href = await link.get_attribute("href")
        # href例: "javascript:showSyllabus('XXXX')" or "JAA104.php?pKey=XXXX"
        pkey = extract_pkey_from_href(href)
        if pkey:
            pkeys.append(pkey)

    # ページネーションがある場合は次ページへ
    return pkeys
```

### Playwright / httpx の使い分け

| 用途 | ツール | 理由 |
|------|--------|------|
| シラバス詳細取得（JAA104.php） | `httpx` | JavaScript不要、静的HTML |
| pKey既知のバッチ取得 | `httpx` | 高速・並列処理が容易 |
| 検索結果ページのpKey収集 | `Playwright` | JavaScriptでリンク動的生成 |
| ページネーション操作 | `Playwright` | DOM操作が必要 |

### HTMLパース戦略

シラバス詳細ページ（JAA104.php）の構造：

```python
from bs4 import BeautifulSoup

def parse_syllabus(html: str, pkey: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # エラーページの判定（シラバスが存在しない場合）
    if is_error_page(soup):
        return None

    return {
        "pkey": pkey,
        "title": extract_title(soup),
        "instructor": extract_instructor(soup),
        "semester": extract_semester(soup),   # Spring/Fall/Full-year
        "credits": extract_credits(soup),
        "department": extract_department(soup),
        "year": extract_year(soup),
        "description": extract_description(soup),
        "objectives": extract_objectives(soup),
        "schedule": extract_schedule(soup),   # 週ごとの授業内容
        "evaluation": extract_evaluation(soup),
        "textbooks": extract_textbooks(soup),
        "raw_html": html,                     # 生HTMLも保存（再パース用）
    }

def is_error_page(soup: BeautifulSoup) -> bool:
    """存在しないpKeyへのアクセスを判定"""
    # サイト固有のエラー文言で判定
    error_markers = ["該当するシラバスはありません", "No syllabus found"]
    text = soup.get_text()
    return any(marker in text for marker in error_markers)
```

#### 学期情報の抽出

pKeyに学期情報は含まれないため、シラバス本文から判定する：

```python
SEMESTER_KEYWORDS = {
    "spring": ["春学期", "Spring", "前期"],
    "fall":   ["秋学期", "Fall", "後期"],
    "full":   ["通年", "Full Year", "春学期・秋学期"],
}
```

### エラーハンドリングとリトライロジック

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def fetch_syllabus(client: httpx.AsyncClient, pkey: str) -> str | None:
    url = f"https://www.wsl.waseda.jp/syllabus/JAA104.php?pKey={pkey}&pLng=jp"
    try:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.TimeoutException:
        raise  # tenacityがリトライ
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None  # pKeyが存在しない → スキップ
        raise
```

エラー種別と対処方針：

| エラー | 対処 |
|--------|------|
| 404 / エラーページ | スキップ（存在しないpKey） |
| タイムアウト | 最大3回リトライ（指数バックオフ） |
| 5xx | 最大3回リトライ後、警告ログ出力してスキップ |
| パースエラー | raw_htmlを保存してスキップ、後続処理は継続 |
| ネットワーク断 | リトライ後も失敗したら全体停止してチェックポイントを保存 |

### レート制限対策

```python
import asyncio

class RateLimitedCrawler:
    def __init__(self, requests_per_second: float = 1.0):
        self.interval = 1.0 / requests_per_second
        self._last_request_time = 0.0

    async def wait(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
```

設定値：

| 項目 | 値 |
|------|-----|
| リクエスト間隔 | 1秒以上 |
| 並列リクエスト数 | 1（逐次処理） |
| User-Agent | `WasedaSyllabusMCP/1.0 (research purpose)` |
| タイムアウト | 30秒 |

### チェックポイントと再開

大量のpKeyを処理する際、中断時に再開できるようチェックポイントを保存する：

```python
class CrawlState:
    """クロール進捗の管理"""
    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self.completed: set[str] = self._load()

    def mark_done(self, pkey: str):
        self.completed.add(pkey)
        if len(self.completed) % 100 == 0:
            self._save()

    def is_done(self, pkey: str) -> bool:
        return pkey in self.completed
```

### データ検証とクリーニング

```python
from pydantic import BaseModel, validator

class SyllabusRecord(BaseModel):
    pkey: str
    title: str
    instructor: str | None
    semester: Literal["spring", "fall", "full", "unknown"]
    credits: int | None
    year: int
    department: str

    @validator("pkey")
    def validate_pkey(cls, v):
        if len(v) != 28:
            raise ValueError(f"pKeyは28文字必須: {v!r}")
        return v

    @validator("year")
    def validate_year(cls, v):
        if not (2000 <= v <= 2100):
            raise ValueError(f"年度が範囲外: {v}")
        return v
```

クリーニング処理：

- 全角スペース・改行の正規化
- タイトル前後の空白除去
- 教員名の重複除去（複数担当の場合）
- HTMLエンティティのデコード（`&amp;` → `&` 等）

### データモデル

```python
# DB スキーマ（SQLAlchemy）
class Syllabus(Base):
    __tablename__ = "syllabuses"

    pkey = Column(String(28), primary_key=True)
    title = Column(String, nullable=False)
    instructor = Column(String)
    semester = Column(String(10))
    credits = Column(Integer)
    year = Column(Integer, nullable=False)
    department = Column(String)
    description = Column(Text)
    objectives = Column(Text)
    evaluation = Column(Text)
    raw_html = Column(Text)           # 生HTML（再パース用）
    crawled_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### 依存関係

- **httpx** - 非同期HTTPクライアント（シラバス詳細取得）
- **playwright** - ブラウザ自動化（検索結果ページのpKey収集）
- **beautifulsoup4** + **lxml** - HTMLパース
- **tenacity** - リトライロジック
- **pydantic** - データバリデーション
- **sqlalchemy[asyncio]** + **asyncpg** - DB保存

## 検討した代替案

| 案 | 採用しなかった理由 |
|---|---|
| Scrapy | asyncio との統合が複雑、Playwright との連携が難しい |
| Playwright のみで全取得 | httpxより低速・高コスト、詳細ページは静的HTMLで十分 |
| requests（同期） | 並列処理が困難、asyncioとの統合不可 |
| Selenium | Playwrightより低速・設定が煩雑 |

## 未解決の質問

- [ ] 他学部の学部コード一覧（`p_gakubu` の全パラメータ値）
- [ ] JAA103.php のページネーション構造（ページ送りのDOM操作方法）
- [ ] JAA103.php の検索POSTパラメータ（キーワード検索を有効化できるか）
- [ ] pKey後半部分（位置19-26）の参照ルールの完全な仕様
- [ ] 学科コード `05` の意味（物理系？）
- [ ] robots.txt の内容・スクレイピング可否（要確認）
- [ ] クローラー実行スケジューリング方式（cron vs GitHub Actions）

## セキュリティ/プライバシーの考慮事項

- シラバス情報は大学公式サイトの公開情報であり、個人情報は含まない
- robots.txt を必ず確認し、Disallow 指定がある場合は従う
- 適切な User-Agent を設定してボットであることを明示する
- 1リクエスト/秒のレート制限でサーバー負荷を最小化する
- クローリング目的・連絡先を User-Agent または別途告知する

## テスト戦略

- **Unit テスト**: pKey生成関数、HTMLパーサー（モックHTMLを使用）
- **Integration テスト**: httpxのモックサーバーを立ててクローラー全体をテスト
- **Playwright テスト**: テスト用の静的HTMLファイルをローカルサーバーで配信してテスト
- **バリデーションテスト**: 不正なpKey・欠損フィールドに対するPydanticモデルの動作確認

## 参考資料

- [早稲田大学シラバス検索](https://www.wsl.waseda.jp/syllabus/JAA101.php)
- [Playwright Python ドキュメント](https://playwright.dev/python/)
- [httpx ドキュメント](https://www.python-httpx.org/)
- [tenacity ドキュメント](https://tenacity.readthedocs.io/)
- [BeautifulSoup4 ドキュメント](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

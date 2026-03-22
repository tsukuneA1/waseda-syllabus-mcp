# 設計ドキュメント: Database Schema (PostgreSQL)

## 概要

早稲田大学シラバス MCP サーバーが使用する PostgreSQL データベースのスキーマ設計。
シラバスデータの格納・検索・更新を効率的に行うためのテーブル構成、インデックス戦略、マイグレーション方針を定める。

## 目標

- **主要な目標**
  - クローラーが収集した約 35,000 件のシラバスデータを格納する
  - LLM からの自然言語検索に対応できる全文検索インデックスを提供する
  - 年次更新を安全に行えるマイグレーション戦略を確立する

- **非目標**
  - ユーザー認証・セッション管理（シラバス情報は公開データのみ）
  - リアルタイムデータ更新（年1回のバッチ更新を想定）

## 背景

クローラー設計ドキュメントで定義された `SyllabusRecord` モデルをベースに、
PostgreSQL の機能（全文検索、JSONB、配列型）を活用して適切なスキーマを設計する。

pKey は 28 文字固定の識別子であり、これを主キーとして使用する。
約 35,000 件のデータを対象に、タイトル・担当教員・授業内容での検索要件がある。

## 設計

### テーブル一覧

```
syllabuses   シラバス本体
reviews      シラバスに対するユーザーレビュー（将来拡張）
```

### syllabuses テーブル

シラバスの全フィールドを格納するメインテーブル。

```sql
CREATE TABLE syllabuses (
    -- 識別子
    pkey            CHAR(28)        PRIMARY KEY,

    -- 基本情報
    title           TEXT            NOT NULL,
    title_en        TEXT,
    year            SMALLINT        NOT NULL,  -- 開講年度 (例: 2026)
    semester        VARCHAR(10)     NOT NULL,  -- 'spring' | 'fall' | 'full' | 'unknown'
    credits         SMALLINT,                  -- 単位数
    department      TEXT,                      -- 学部・研究科名

    -- 担当教員（複数担当があるため配列）
    instructors     TEXT[]          NOT NULL DEFAULT '{}',

    -- 授業内容
    description     TEXT,                      -- 授業概要
    objectives      TEXT,                      -- 学習目標
    schedule        JSONB,                     -- 授業計画（週ごとの内容）
    evaluation      TEXT,                      -- 成績評価方法
    textbooks       TEXT,                      -- 教科書・参考書

    -- 全文検索用
    search_vector   TSVECTOR,                  -- 自動更新トリガーで管理

    -- メタデータ
    raw_html        TEXT,                      -- クローリング元のHTML（デバッグ用）
    crawled_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);
```

#### カラム設計の理由

| カラム | 型 | 理由 |
|--------|-----|------|
| `pkey` | `CHAR(28)` | 固定長28文字のため `CHAR` が適切。UUIDより意味のある識別子 |
| `year` | `SMALLINT` | 年度は4桁整数。`INTEGER` より小さい `SMALLINT` で十分 |
| `semester` | `VARCHAR(10)` | ENUMの代わりに VARCHAR を使用。値は `'spring'`, `'fall'`, `'full'`, `'unknown'` の4種類 |
| `instructors` | `TEXT[]` | 複数担当教員を正規化せず配列で管理。検索・更新の単純さを優先 |
| `schedule` | `JSONB` | 週ごとの授業計画は構造が可変。JSONB でそのまま格納して柔軟性を確保 |
| `search_vector` | `TSVECTOR` | 全文検索用の前処理済みベクター。トリガーで自動更新 |
| `raw_html` | `TEXT` | パースエラー時の再処理に使用。本番ではパーティションや別テーブルへの移動を検討 |

### reviews テーブル

シラバスに対するユーザーレビュー・評価を格納するテーブル（将来拡張用）。

```sql
CREATE TABLE reviews (
    id              BIGSERIAL       PRIMARY KEY,
    pkey            CHAR(28)        NOT NULL REFERENCES syllabuses(pkey) ON DELETE CASCADE,

    -- レビュー内容
    rating          SMALLINT        NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,

    -- メタデータ（ユーザー識別子は匿名ハッシュ）
    user_hash       TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

### 正規化レベルの決定

**第3正規形を基本とし、検索パフォーマンスのため一部の非正規化を許容する。**

具体的な判断：

| 項目 | 判断 | 理由 |
|------|------|------|
| `instructors` | 非正規化（配列型） | 教員マスターテーブルを別途持つほどの要件なし。シラバス更新時の結合コストを避ける |
| `department` | 非正規化（文字列） | 学部名は変更頻度が低く、参照整合性より取得の単純さを優先 |
| `schedule` | 非正規化（JSONB） | 週ごとのデータ構造が可変。別テーブル化するとJOINコストが増加する |

### インデックス戦略

```sql
-- 全文検索インデックス（GIN: Generalized Inverted Index）
CREATE INDEX idx_syllabuses_search_vector
    ON syllabuses USING GIN (search_vector);

-- 年度・学期での絞り込み
CREATE INDEX idx_syllabuses_year_semester
    ON syllabuses (year, semester);

-- 学部での絞り込み
CREATE INDEX idx_syllabuses_department
    ON syllabuses (department);

-- 教員名での検索（配列のGINインデックス）
CREATE INDEX idx_syllabuses_instructors
    ON syllabuses USING GIN (instructors);

-- reviews: pKeyでの検索
CREATE INDEX idx_reviews_pkey
    ON reviews (pkey);
```

### 全文検索の実装

#### pg_trgm vs to_tsvector の選択

| 方式 | メリット | デメリット | 採用判断 |
|------|----------|-----------|----------|
| `to_tsvector` | 高速、形態素解析対応 | 日本語には別途設定が必要 | **採用（英語フィールド）** |
| `pg_trgm` | 日本語を含む任意の文字列に有効 | インデックスサイズが大きい | **採用（日本語フィールド）** |

両方を組み合わせて使用する。

```sql
-- pg_trgmエクステンションを有効化
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 日本語タイトルの部分一致検索用トライグラムインデックス
CREATE INDEX idx_syllabuses_title_trgm
    ON syllabuses USING GIN (title gin_trgm_ops);

CREATE INDEX idx_syllabuses_description_trgm
    ON syllabuses USING GIN (description gin_trgm_ops);
```

#### search_vector の自動更新

```sql
-- search_vectorを自動更新するトリガー関数
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title_en, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.department, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER syllabuses_search_vector_update
    BEFORE INSERT OR UPDATE ON syllabuses
    FOR EACH ROW
    EXECUTE FUNCTION update_search_vector();
```

**検索クエリ例：**

```sql
-- キーワード検索（英語タイトル対象）
SELECT pkey, title, instructors, semester, credits
FROM syllabuses
WHERE search_vector @@ plainto_tsquery('english', 'machine learning')
ORDER BY ts_rank(search_vector, plainto_tsquery('english', 'machine learning')) DESC
LIMIT 20;

-- 日本語タイトルの部分一致
SELECT pkey, title, department
FROM syllabuses
WHERE title ILIKE '%機械学習%'
LIMIT 20;

-- 複合フィルタ
SELECT pkey, title, instructors, credits
FROM syllabuses
WHERE year = 2026
  AND semester = 'spring'
  AND '田中' = ANY(instructors);
```

### JSONB スキーマ（schedule カラム）

`schedule` カラムには週ごとの授業計画を格納する。

```json
[
  {
    "week": 1,
    "title": "ガイダンス・イントロダクション",
    "content": "授業の概要と進め方について説明する。"
  },
  {
    "week": 2,
    "title": "機械学習の基礎",
    "content": "教師あり学習・教師なし学習の概念を解説する。"
  }
]
```

NULL の場合はクローリング時に授業計画が取得できなかったことを示す。

## マイグレーション戦略（Alembic）

### ディレクトリ構造

```
apps/backend/
├── alembic.ini
└── migrations/
    ├── env.py
    ├── script.py.mako
    └── versions/
        ├── 0001_create_syllabuses.py
        ├── 0002_create_reviews.py
        └── 0003_add_search_indexes.py
```

### 初期マイグレーション

```python
# migrations/versions/0001_create_syllabuses.py

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "syllabuses",
        sa.Column("pkey", sa.CHAR(28), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("title_en", sa.Text),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("semester", sa.String(10), nullable=False),
        sa.Column("credits", sa.SmallInteger),
        sa.Column("department", sa.Text),
        sa.Column("instructors", postgresql.ARRAY(sa.Text), nullable=False,
                  server_default="{}"),
        sa.Column("description", sa.Text),
        sa.Column("objectives", sa.Text),
        sa.Column("schedule", postgresql.JSONB),
        sa.Column("evaluation", sa.Text),
        sa.Column("textbooks", sa.Text),
        sa.Column("search_vector", postgresql.TSVECTOR),
        sa.Column("raw_html", sa.Text),
        sa.Column("crawled_at", sa.TIMESTAMPTZ, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMPTZ),
    )


def downgrade() -> None:
    op.drop_table("syllabuses")
```

### 年次データ更新の流れ

```
1. 新年度クローリング実行（年1回）
2. syllabuses テーブルに UPSERT（pkey が同じなら updated_at を更新）
3. 前年度データはそのまま保持（year カラムで区別）
```

```sql
-- クローラーによる UPSERT
INSERT INTO syllabuses (pkey, title, year, semester, credits, department,
                        instructors, description, objectives, schedule,
                        evaluation, textbooks, raw_html, crawled_at)
VALUES (:pkey, :title, :year, :semester, :credits, :department,
        :instructors, :description, :objectives, :schedule,
        :evaluation, :textbooks, :raw_html, NOW())
ON CONFLICT (pkey) DO UPDATE SET
    title        = EXCLUDED.title,
    instructors  = EXCLUDED.instructors,
    description  = EXCLUDED.description,
    objectives   = EXCLUDED.objectives,
    schedule     = EXCLUDED.schedule,
    evaluation   = EXCLUDED.evaluation,
    textbooks    = EXCLUDED.textbooks,
    raw_html     = EXCLUDED.raw_html,
    updated_at   = NOW();
```

## 検討した代替案

| 案 | 採用しなかった理由 |
|---|---|
| Elasticsearch | 全文検索専用エンジンは over-engineering。PostgreSQL の `pg_trgm` + `tsvector` で要件を満たせる |
| 教員を別テーブルに正規化 | 教員情報はシラバスと一体で更新されるため、正規化のメリットが小さい |
| `semester` を ENUM 型 | Alembic でのマイグレーションが複雑になる。VARCHAR + CHECK 制約で代替 |
| `schedule` を別テーブルに正規化 | 週ごとデータはシラバスと一体で読み書きされる。JOIN コストを避け JSONB を選択 |
| partitioning（year ごと） | 35,000 件はパーティショニングが必要な規模ではない。年度インデックスで十分 |

## 未解決の質問

- [ ] `raw_html` の長期保存方針（DBサイズが増大する可能性）
  - 選択肢: 一定期間後に NULL クリア / S3 等の外部ストレージに移動
- [ ] 日本語全文検索の精度向上（`pgroonga` 拡張の検討）
  - `pg_trgm` で不十分なら `PGroonga` の導入を検討
- [ ] `reviews` テーブルのユーザー識別方式
  - 匿名ハッシュで十分か、認証基盤が必要か

## セキュリティ/プライバシーの考慮事項

- シラバス情報は公開データであり、個人情報は含まない
- `reviews` テーブルのユーザー識別子は匿名ハッシュで管理し、個人が特定できないようにする
- DB 接続情報は環境変数で管理し、ソースコードにハードコードしない

## テスト戦略

- **Unit テスト**: Pydantic モデルのバリデーション（`SyllabusRecord`）
- **Integration テスト**: テスト用 PostgreSQL コンテナを起動し、実際の UPSERT・検索クエリをテスト
- **マイグレーションテスト**: `alembic upgrade head` → `alembic downgrade base` が正常に動作することを CI で確認

## ロールアウト/移行計画

1. `alembic upgrade head` で初回テーブル作成
2. クローラーを実行してシラバスデータを投入（初回約10時間）
3. インデックス作成（データ投入後に `CONCURRENTLY` オプションで作成）

```sql
-- 本番データ投入後にインデックスをノンブロッキングで作成
CREATE INDEX CONCURRENTLY idx_syllabuses_search_vector
    ON syllabuses USING GIN (search_vector);
```

## メトリクス/モニタリング

- テーブルサイズ（`pg_relation_size`）の定期確認
- 全文検索クエリの実行時間（スロークエリログ）
- クローリング後の件数確認（年度ごとの `COUNT(*)`）

## 参考資料

- [PostgreSQL 全文検索ドキュメント](https://www.postgresql.org/docs/current/textsearch.html)
- [pg_trgm ドキュメント](https://www.postgresql.org/docs/current/pgtrgm.html)
- [Alembic ドキュメント](https://alembic.sqlalchemy.org/)
- [SQLAlchemy PostgreSQL 方言](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [crawler-design.md](./crawler-design.md) — クローラー側のデータモデル定義
- [backend-architecture.md](./backend-architecture.md) — バックエンド全体構成

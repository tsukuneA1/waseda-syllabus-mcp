-- 早稲田大学シラバス MCP サーバー DB 初期化スクリプト
-- このスクリプトはコンテナ初回起動時に自動実行される

-- エクステンション
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- syllabuses テーブル
CREATE TABLE IF NOT EXISTS syllabuses (
    -- 識別子
    pkey            CHAR(28)        PRIMARY KEY,

    -- 基本情報
    title           TEXT            NOT NULL,
    title_en        TEXT,
    year            SMALLINT        NOT NULL,
    semester        VARCHAR(10)     NOT NULL,
    credits         SMALLINT,
    department      TEXT,

    -- 担当教員（複数担当があるため配列）
    instructors     TEXT[]          NOT NULL DEFAULT '{}',

    -- 授業内容
    description     TEXT,
    objectives      TEXT,
    schedule        JSONB,
    evaluation      TEXT,
    textbooks       TEXT,

    -- 全文検索用
    search_vector   TSVECTOR,

    -- メタデータ
    raw_html        TEXT,
    crawled_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

-- reviews テーブル（将来拡張用）
CREATE TABLE IF NOT EXISTS reviews (
    id              BIGSERIAL       PRIMARY KEY,
    pkey            CHAR(28)        NOT NULL REFERENCES syllabuses(pkey) ON DELETE CASCADE,
    rating          SMALLINT        NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    user_hash       TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_syllabuses_search_vector
    ON syllabuses USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_syllabuses_year_semester
    ON syllabuses (year, semester);

CREATE INDEX IF NOT EXISTS idx_syllabuses_department
    ON syllabuses (department);

CREATE INDEX IF NOT EXISTS idx_syllabuses_instructors
    ON syllabuses USING GIN (instructors);

CREATE INDEX IF NOT EXISTS idx_syllabuses_title_trgm
    ON syllabuses USING GIN (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_syllabuses_description_trgm
    ON syllabuses USING GIN (description gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_reviews_pkey
    ON reviews (pkey);

-- search_vector 自動更新トリガー
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title_en, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.department, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS syllabuses_search_vector_update ON syllabuses;
CREATE TRIGGER syllabuses_search_vector_update
    BEFORE INSERT OR UPDATE ON syllabuses
    FOR EACH ROW
    EXECUTE FUNCTION update_search_vector();

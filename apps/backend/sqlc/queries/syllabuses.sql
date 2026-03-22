-- name: GetSyllabus :one
SELECT *
FROM syllabuses
WHERE pkey = $1;

-- name: ListSyllabuses :many
SELECT pkey, title, title_en, year, semester, credits, department, instructors
FROM syllabuses
WHERE
    ($1::SMALLINT IS NULL OR year = $1)
    AND ($2::VARCHAR IS NULL OR semester = $2)
    AND ($3::TEXT IS NULL OR department = $3)
ORDER BY year DESC, title
LIMIT $4 OFFSET $5;

-- name: SearchSyllabusesByKeyword :many
SELECT pkey, title, title_en, year, semester, credits, department, instructors
FROM syllabuses
WHERE
    title ILIKE '%' || $1 || '%'
    OR description ILIKE '%' || $1 || '%'
    OR $1 = ANY(instructors)
ORDER BY year DESC
LIMIT $2 OFFSET $3;

-- name: SearchSyllabusesByVector :many
SELECT pkey, title, title_en, year, semester, credits, department, instructors,
       ts_rank(search_vector, plainto_tsquery('english', $1)) AS rank
FROM syllabuses
WHERE search_vector @@ plainto_tsquery('english', $1)
ORDER BY rank DESC
LIMIT $2 OFFSET $3;

-- name: UpsertSyllabus :one
INSERT INTO syllabuses (
    pkey, title, title_en, year, semester, credits, department,
    instructors, description, objectives, schedule, evaluation,
    textbooks, raw_html, crawled_at, updated_at
) VALUES (
    $1, $2, $3, $4, $5, $6, $7,
    $8, $9, $10, $11, $12,
    $13, $14, $15, $16
)
ON CONFLICT (pkey) DO UPDATE SET
    title        = EXCLUDED.title,
    title_en     = EXCLUDED.title_en,
    year         = EXCLUDED.year,
    semester     = EXCLUDED.semester,
    credits      = EXCLUDED.credits,
    department   = EXCLUDED.department,
    instructors  = EXCLUDED.instructors,
    description  = EXCLUDED.description,
    objectives   = EXCLUDED.objectives,
    schedule     = EXCLUDED.schedule,
    evaluation   = EXCLUDED.evaluation,
    textbooks    = EXCLUDED.textbooks,
    raw_html     = EXCLUDED.raw_html,
    crawled_at   = EXCLUDED.crawled_at,
    updated_at   = NOW()
RETURNING *;

-- name: CountSyllabuses :one
SELECT COUNT(*) FROM syllabuses;

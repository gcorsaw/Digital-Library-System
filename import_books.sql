-- ============================================================
-- STEP 1: Run this once to create the landing table for the CSV.
-- ============================================================
DROP TABLE IF EXISTS staging_books;
CREATE TABLE staging_books (
    isbn VARCHAR(20),
    internal_code VARCHAR(50),
    title VARCHAR(255),
    publish_date DATE,
    publisher VARCHAR(255),
    language VARCHAR(10),
    authors TEXT,
    genres TEXT,
    media_types TEXT
);

-- ============================================================
-- STEP 2: In DBeaver, right-click staging_books in the Database
-- Navigator -> Import Data -> CSV -> select your CSV file ->
-- map each CSV column to the matching staging_books column ->
-- Finish. This works regardless of whether the CSV lives on
-- your machine or the DB server, since DBeaver streams it over
-- the JDBC connection rather than needing a server-side file path.
-- ============================================================

-- ============================================================
-- STEP 3: Run this once to create the reusable import function.
-- Call it again any time after loading a fresh batch into
-- staging_books -- it only inserts rows that don't already exist
-- (matched on isbn/internal_code + title), so re-running is safe.
-- ============================================================
CREATE OR REPLACE FUNCTION import_staging_books()
RETURNS TABLE(book_id INT, book_title VARCHAR) AS $function$
BEGIN
    DROP TABLE IF EXISTS _staged;
    DROP TABLE IF EXISTS _new_books;
    DROP TABLE IF EXISTS _authors_exploded;

    -- Normalize blank values and keep a stable row order so the
    -- author/genre/media links line up with the correct imported book.
    CREATE TEMP TABLE _staged AS
    SELECT
        row_number() OVER () AS ord,
        NULLIF(trim(sb.isbn), '') AS isbn,
        NULLIF(trim(sb.internal_code), '') AS internal_code,
        trim(sb.title) AS title,
        sb.publish_date,
        sb.publisher,
        sb.language,
        sb.authors,
        sb.genres,
        sb.media_types
    FROM staging_books sb
    WHERE NULLIF(trim(sb.title), '') IS NOT NULL;

    CREATE TEMP TABLE _new_books ON COMMIT DROP AS
    WITH inserted AS (
        INSERT INTO book_info (book_isbn, internal_code, book_title, publish_date, publisher, language)
        SELECT DISTINCT NULLIF(trim(s.isbn), ''), NULLIF(trim(s.internal_code), ''), trim(s.title), s.publish_date, s.publisher, s.language
        FROM _staged s
        WHERE NULLIF(trim(s.title), '') IS NOT NULL
        ON CONFLICT DO NOTHING
        RETURNING book_info.book_id, book_info.book_title, book_info.book_isbn, book_info.internal_code
    )
    SELECT s.ord, ins.book_id, ins.book_title
    FROM inserted ins
    JOIN _staged s
      ON trim(s.title) = ins.book_title
     AND (NULLIF(trim(s.isbn), '') IS NOT DISTINCT FROM ins.book_isbn)
     AND (NULLIF(trim(s.internal_code), '') IS NOT DISTINCT FROM ins.internal_code);

    CREATE TEMP TABLE _authors_exploded ON COMMIT DROP AS
    SELECT
        s.ord,
        NULLIF(trim(split_part(a, ';', 1)), '') AS first_name,
        NULLIF(trim(split_part(a, ';', 2)), '') AS last_name,
        NULLIF(trim(split_part(a, ';', 3)), '') AS role
    FROM _staged s
    CROSS JOIN LATERAL unnest(string_to_array(s.authors, '|')) AS a
    WHERE s.authors IS NOT NULL AND trim(s.authors) <> '';

    INSERT INTO author_info (first_name, last_name)
    SELECT DISTINCT first_name, last_name
    FROM _authors_exploded
    WHERE first_name IS NOT NULL AND last_name IS NOT NULL
    ON CONFLICT (first_name, last_name) DO NOTHING;

    INSERT INTO creator_role_type (creator_role_name)
    SELECT DISTINCT COALESCE(role, 'Author')::citext
    FROM _authors_exploded
    WHERE first_name IS NOT NULL AND last_name IS NOT NULL
    ON CONFLICT (creator_role_name) DO NOTHING;

    INSERT INTO book_author (book_id, author_id, creator_role_id)
    SELECT DISTINCT nb.book_id, au.author_id, crt.creator_role_id
    FROM _authors_exploded ae
    JOIN _new_books nb ON nb.ord = ae.ord
    JOIN author_info au
      ON au.first_name = ae.first_name
     AND au.last_name = ae.last_name
    JOIN creator_role_type crt
      ON crt.creator_role_name = COALESCE(ae.role, 'Author')::citext
    WHERE ae.first_name IS NOT NULL AND ae.last_name IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO genre (genre_name)
    SELECT DISTINCT g
    FROM _staged s
    CROSS JOIN LATERAL unnest(string_to_array(s.genres, '|')) AS g
    WHERE s.genres IS NOT NULL AND trim(s.genres) <> ''
    ON CONFLICT (genre_name) DO NOTHING;

    INSERT INTO book_genre (book_id, genre_id)
    SELECT DISTINCT nb.book_id, gen.genre_id
    FROM _staged s
    JOIN _new_books nb ON nb.ord = s.ord
    CROSS JOIN LATERAL unnest(string_to_array(s.genres, '|')) AS g
    JOIN genre gen ON gen.genre_name = trim(g)
    WHERE s.genres IS NOT NULL AND trim(s.genres) <> ''
    ON CONFLICT DO NOTHING;

    INSERT INTO media_type (media_type_name)
    SELECT DISTINCT m
    FROM _staged s
    CROSS JOIN LATERAL unnest(string_to_array(s.media_types, '|')) AS m
    WHERE s.media_types IS NOT NULL AND trim(s.media_types) <> ''
    ON CONFLICT (media_type_name) DO NOTHING;

    INSERT INTO book_media_type (book_id, media_type_id)
    SELECT DISTINCT nb.book_id, mt.media_type_id
    FROM _staged s
    JOIN _new_books nb ON nb.ord = s.ord
    CROSS JOIN LATERAL unnest(string_to_array(s.media_types, '|')) AS m
    JOIN media_type mt ON mt.media_type_name = trim(m)
    WHERE s.media_types IS NOT NULL AND trim(s.media_types) <> ''
    ON CONFLICT DO NOTHING;

    DROP TABLE IF EXISTS _staged;
    RETURN QUERY SELECT nb.book_id, nb.book_title FROM _new_books nb ORDER BY nb.ord;
END;
$function$ LANGUAGE plpgsql;

SELECT
    s.title,
    s.isbn,
    s.internal_code,
    b.book_id,
    b.book_title,
    CASE
        WHEN b.book_id IS NULL THEN 'MISSING'
        ELSE 'OK'
    END AS import_status
FROM staging_books s
LEFT JOIN book_info b
  ON trim(s.title) = b.book_title
 AND (NULLIF(trim(s.isbn), '') IS NOT DISTINCT FROM b.book_isbn)
 AND (NULLIF(trim(s.internal_code), '') IS NOT DISTINCT FROM b.internal_code)
ORDER BY s.title;

SELECT
    (SELECT COUNT(*) FROM staging_books) AS staging_rows,
    (SELECT COUNT(*) FROM book_info) AS total_books,
    (SELECT COUNT(*) FROM author_info) AS total_authors,
    (SELECT COUNT(*) FROM book_author) AS total_book_authors,
    (SELECT COUNT(*) FROM book_genre) AS total_genres,
    (SELECT COUNT(*) FROM book_media_type) AS total_media_links;

-- ============================================================
-- STEP 4: Run this each time you've loaded a new batch of rows
-- into staging_books and want them applied to the real tables.
-- ============================================================
SELECT * FROM import_staging_books();
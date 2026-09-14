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
-- Navigator -> Import Data -> CSV -> select books_import.csv ->
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

    -- Give this batch stable row numbers so authors/genres/media
    -- types can be matched back to the right book after insert.
    CREATE TEMP TABLE _staged AS
    SELECT row_number() OVER () AS ord, sb.*
    FROM staging_books sb;

    -- Insert the books
    CREATE TEMP TABLE _new_books ON COMMIT DROP AS
    WITH inserted AS (
        INSERT INTO book_info (book_isbn, internal_code, book_title, publish_date, publisher, language)
        SELECT NULLIF(isbn, ''), NULLIF(internal_code, ''), title, publish_date, publisher, language
        FROM _staged
        ON CONFLICT DO NOTHING
        RETURNING book_info.book_id, book_info.book_title, book_info.book_isbn, book_info.internal_code
    )
    SELECT s.ord, ins.book_id, ins.book_title
    FROM inserted ins
    JOIN _staged s
      ON s.title = ins.book_title
     AND (NULLIF(s.isbn, '') IS NOT DISTINCT FROM ins.book_isbn)
     AND (NULLIF(s.internal_code, '') IS NOT DISTINCT FROM ins.internal_code);

    -- Explode the pipe/semicolon-delimited authors column
    CREATE TEMP TABLE _authors_exploded ON COMMIT DROP AS
    SELECT
        s.ord,
        split_part(a, ';', 1) AS first_name,
        split_part(a, ';', 2) AS last_name,
        NULLIF(split_part(a, ';', 3), '') AS role
    FROM _staged s, unnest(string_to_array(s.authors, '|')) AS a
    WHERE s.authors IS NOT NULL AND s.authors <> '';

    INSERT INTO author_info (first_name, last_name)
    SELECT DISTINCT first_name, last_name FROM _authors_exploded
    ON CONFLICT (first_name, last_name) DO NOTHING;

    INSERT INTO creator_role_type (creator_role_name)
    SELECT DISTINCT COALESCE(role, 'Author')::citext FROM _authors_exploded
    ON CONFLICT (creator_role_name) DO NOTHING;

    INSERT INTO book_author (book_id, author_id, creator_role_id)
    SELECT DISTINCT nb.book_id, au.author_id, crt.creator_role_id
    FROM _authors_exploded ae
    JOIN _new_books nb ON nb.ord = ae.ord
    JOIN author_info au ON au.first_name = ae.first_name AND au.last_name = ae.last_name
    JOIN creator_role_type crt ON crt.creator_role_name = COALESCE(ae.role, 'Author')
    ON CONFLICT DO NOTHING;

    -- Genres
    INSERT INTO genre (genre_name)
    SELECT DISTINCT g FROM _staged s, unnest(string_to_array(s.genres, '|')) AS g
    WHERE s.genres IS NOT NULL AND s.genres <> ''
    ON CONFLICT (genre_name) DO NOTHING;

    INSERT INTO book_genre (book_id, genre_id)
    SELECT DISTINCT nb.book_id, gen.genre_id
    FROM _staged s
    JOIN _new_books nb ON nb.ord = s.ord
    JOIN LATERAL unnest(string_to_array(s.genres, '|')) AS g ON true
    JOIN genre gen ON gen.genre_name = g
    WHERE s.genres IS NOT NULL AND s.genres <> ''
    ON CONFLICT DO NOTHING;

    -- Media types
    INSERT INTO media_type (media_type_name)
    SELECT DISTINCT m FROM _staged s, unnest(string_to_array(s.media_types, '|')) AS m
    WHERE s.media_types IS NOT NULL AND s.media_types <> ''
    ON CONFLICT (media_type_name) DO NOTHING;

    INSERT INTO book_media_type (book_id, media_type_id)
    SELECT DISTINCT nb.book_id, mt.media_type_id
    FROM _staged s
    JOIN _new_books nb ON nb.ord = s.ord
    JOIN LATERAL unnest(string_to_array(s.media_types, '|')) AS m ON true
    JOIN media_type mt ON mt.media_type_name = m
    WHERE s.media_types IS NOT NULL AND s.media_types <> ''
    ON CONFLICT DO NOTHING;

    DROP TABLE IF EXISTS _staged;
    RETURN QUERY SELECT nb.book_id, nb.book_title FROM _new_books nb ORDER BY nb.ord;
END;
$function$ LANGUAGE plpgsql;

-- ============================================================
-- STEP 4: Run this each time you've loaded a new batch of rows
-- into staging_books and want them applied to the real tables.
-- ============================================================
SELECT * FROM import_staging_books();
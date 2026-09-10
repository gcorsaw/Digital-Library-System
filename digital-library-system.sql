CREATE EXTENSION IF NOT EXISTS citext;

-- 1. CLEAN RESET: Drop existing schemas in reverse relational dependency order
DROP TABLE IF EXISTS reading_progress CASCADE;
DROP TABLE IF EXISTS book_adaptation CASCADE;
DROP TABLE IF EXISTS book_tracking CASCADE;
DROP TABLE IF EXISTS book_genre CASCADE;
DROP TABLE IF EXISTS book_media_type CASCADE;
DROP TABLE IF EXISTS book_author CASCADE;
DROP TABLE IF EXISTS author_info CASCADE;

-- Board game tables must be dropped before shared genre and user tables.
DROP TABLE IF EXISTS game_tracking CASCADE;
DROP TABLE IF EXISTS game_genre CASCADE;
DROP TABLE IF EXISTS game_designer CASCADE;
DROP TABLE IF EXISTS designer_info CASCADE;
DROP TABLE IF EXISTS game_info CASCADE;
DROP TABLE IF EXISTS reader_info CASCADE;

DROP TABLE IF EXISTS creator_role_type CASCADE;
DROP TABLE IF EXISTS genre CASCADE;
DROP TABLE IF EXISTS media_type CASCADE;
DROP TABLE IF EXISTS book_info CASCADE;

-- Automated timestamp tracking function
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$ LANGUAGE plpgsql;
 
-- 2. CORE BOOK SCHEMAS
CREATE TABLE IF NOT EXISTS author_info (
    author_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_author_name UNIQUE (first_name, last_name)
);
 
CREATE TRIGGER trigger_author_info_updated
BEFORE UPDATE ON author_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
 
CREATE TABLE IF NOT EXISTS book_info (
    book_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_isbn VARCHAR(20) UNIQUE,
    internal_code VARCHAR(50) UNIQUE,
    book_title VARCHAR(255) NOT NULL,
    publish_date DATE,
    publisher VARCHAR(255),
    edition VARCHAR(50),
    issue_number VARCHAR(50) DEFAULT NULL,
    volume_number INT DEFAULT NULL,
    page_amount INT DEFAULT NULL,
    book_description TEXT,
    language VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(book_title, '') || ' ' || COALESCE(book_description, ''))
    ) STORED,
    CONSTRAINT chk_has_identifier CHECK (book_isbn IS NOT NULL OR internal_code IS NOT NULL)
);
 
CREATE INDEX idx_book_info_search ON book_info USING GIN (search_vector);
 
CREATE TRIGGER trigger_book_info_updated
BEFORE UPDATE ON book_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
 
CREATE TABLE IF NOT EXISTS creator_role_type (
    creator_role_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creator_role_name CITEXT UNIQUE NOT NULL
);
 
CREATE TABLE IF NOT EXISTS book_author (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    author_id INT REFERENCES author_info(author_id) ON DELETE CASCADE,
    creator_role_id INT NOT NULL REFERENCES creator_role_type(creator_role_id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, author_id, creator_role_id)
);
 
CREATE TABLE IF NOT EXISTS genre (
    genre_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    genre_name CITEXT UNIQUE NOT NULL
);
 
CREATE TABLE IF NOT EXISTS book_genre (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, genre_id)
);
 
CREATE TABLE IF NOT EXISTS media_type (
    media_type_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_type_name CITEXT UNIQUE NOT NULL
);
 
CREATE TABLE IF NOT EXISTS book_media_type (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    media_type_id INT REFERENCES media_type(media_type_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, media_type_id)
);
 
CREATE TABLE IF NOT EXISTS book_adaptation (
    adaptation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id INT NOT NULL REFERENCES book_info(book_id) ON DELETE CASCADE,
    adaptation_type VARCHAR(50) NOT NULL CHECK (adaptation_type IN ('Feature Film', 'Television Series', 'Stage Play', 'Radio Drama', 'Video Game')),
    title VARCHAR(255) NOT NULL,
    release_date DATE
);

-- 3. CORE BOARD GAME SCHEMAS
CREATE TABLE IF NOT EXISTS game_info (
    game_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_title VARCHAR(255) UNIQUE NOT NULL,
    publisher VARCHAR(255),
    release_date DATE,
    min_players INT CHECK (min_players > 0),
    max_players INT CHECK (max_players >= min_players),
    play_time_minutes INT,
    min_age INT,
    game_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trigger_game_info_updated
BEFORE UPDATE ON game_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS designer_info (
    designer_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_designer_name UNIQUE (first_name, last_name)
);

CREATE TRIGGER trigger_designer_info_updated
BEFORE UPDATE ON designer_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS game_designer (
    game_id INT REFERENCES game_info(game_id) ON DELETE CASCADE,
    designer_id INT REFERENCES designer_info(designer_id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, designer_id)
);

CREATE TABLE IF NOT EXISTS game_genre (
    game_id INT REFERENCES game_info(game_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, genre_id)
);
 
-- 4. SHARED USER ACCOUNT AND TRACKING SCHEMAS
CREATE TABLE IF NOT EXISTS reader_info (
    user_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username CITEXT UNIQUE NOT NULL,
    email CITEXT UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    external_auth_id VARCHAR(255) UNIQUE,
    offline_sync_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_auth_method CHECK (password_hash IS NOT NULL OR external_auth_id IS NOT NULL)
);
 
CREATE TABLE IF NOT EXISTS book_tracking (
    user_id INT REFERENCES reader_info(user_id) ON DELETE CASCADE,
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    book_summary VARCHAR(300),
    book_ratings INT CHECK (book_ratings BETWEEN 1 AND 5),
    read_status VARCHAR(10) NOT NULL DEFAULT 'want' CHECK (read_status IN ('want', 'reading', 'finished')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, book_id)
);
 
CREATE TRIGGER trigger_book_tracking_updated
BEFORE UPDATE ON book_tracking
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
 
CREATE TABLE IF NOT EXISTS reading_progress (
    progress_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    book_id INT NOT NULL,
    progress_percent NUMERIC(5,2) CHECK (progress_percent BETWEEN 0 AND 100),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id, book_id) REFERENCES book_tracking(user_id, book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS game_tracking (
    user_id INT REFERENCES reader_info(user_id) ON DELETE CASCADE,
    game_id INT REFERENCES game_info(game_id) ON DELETE CASCADE,
    game_notes TEXT,
    game_ratings INT CHECK (game_ratings BETWEEN 1 AND 5),
    play_status VARCHAR(10) NOT NULL DEFAULT 'want' CHECK (play_status IN ('want', 'owned', 'played')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

CREATE TRIGGER trigger_game_tracking_updated
BEFORE UPDATE ON game_tracking
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
 
-- 5. PERFORMANCE INDEXES
CREATE INDEX IF NOT EXISTS index_reading_progress_user_book ON reading_progress(user_id, book_id);
CREATE INDEX IF NOT EXISTS index_book_adaptation_book_id ON book_adaptation(book_id);
CREATE INDEX IF NOT EXISTS index_book_author_author_id ON book_author(author_id);
CREATE INDEX IF NOT EXISTS index_book_genre_genre_id ON book_genre(genre_id);
CREATE INDEX IF NOT EXISTS index_book_media_type_media_type_id ON book_media_type(media_type_id);
CREATE INDEX IF NOT EXISTS index_book_tracking_book_id ON book_tracking(book_id);
 
-- 6. STABILIZED JSON BULK INGESTION FUNCTION
CREATE OR REPLACE FUNCTION bulk_insert_books(payload jsonb)
RETURNS TABLE(book_id INT, book_title VARCHAR) AS $function$
BEGIN
    -- Unnest the input array retaining ordinal indices
    DROP TABLE IF EXISTS _input_books;
    DROP TABLE IF EXISTS _new_books;

    CREATE TEMP TABLE _input_books ON COMMIT DROP AS
    SELECT
        t.ord,
        (t.elem->>'isbn')::VARCHAR AS book_isbn,
        (t.elem->>'internal_code')::VARCHAR AS internal_code,
        (t.elem->>'title')::VARCHAR AS book_title,
        (t.elem->>'publish_date')::DATE AS publish_date,
        (t.elem->>'publisher')::VARCHAR AS publisher,
        (t.elem->>'language')::VARCHAR AS language,
        t.elem->'authors' AS authors,
        t.elem->'genres' AS genres,
        t.elem->'media_types' AS media_types
    FROM jsonb_array_elements(payload) WITH ORDINALITY AS t(elem, ord);
 
    -- Resolved cross-join identification defect by tracking matching input rows linearly
    CREATE TEMP TABLE _new_books ON COMMIT DROP AS
    WITH inserted AS (
        INSERT INTO book_info (book_isbn, internal_code, book_title, publish_date, publisher, language)
        SELECT ib.book_isbn, ib.internal_code, ib.book_title, ib.publish_date, ib.publisher, ib.language
        FROM _input_books AS ib
        ON CONFLICT DO NOTHING
        RETURNING book_info.book_id, book_info.book_title, book_info.book_isbn, book_info.internal_code
    )
    SELECT i.ord, ins.book_id, ins.book_title
    FROM inserted ins
    JOIN _input_books i 
      ON i.book_title = ins.book_title
     AND (i.book_isbn IS NOT DISTINCT FROM ins.book_isbn)
     AND (i.internal_code IS NOT DISTINCT FROM ins.internal_code);
 
    -- Normalize and safe-upsert metadata collections
    INSERT INTO author_info (first_name, last_name)
    SELECT DISTINCT a->>'first_name', a->>'last_name'
    FROM _input_books, jsonb_array_elements(COALESCE(authors, '[]'::jsonb)) AS a
    ON CONFLICT (first_name, last_name) DO NOTHING;
 
    INSERT INTO genre (genre_name)
    SELECT DISTINCT g
    FROM _input_books, jsonb_array_elements_text(COALESCE(genres, '[]'::jsonb)) AS g
    ON CONFLICT (genre_name) DO NOTHING;
 
    INSERT INTO media_type (media_type_name)
    SELECT DISTINCT m
    FROM _input_books, jsonb_array_elements_text(COALESCE(media_types, '[]'::jsonb)) AS m
    ON CONFLICT (media_type_name) DO NOTHING;

    -- Prevent dynamic crash exceptions by auto-registering unseen roles
    INSERT INTO creator_role_type (creator_role_name)
    SELECT DISTINCT COALESCE(a->>'role', 'Author')::citext
    FROM _input_books, jsonb_array_elements(COALESCE(authors, '[]'::jsonb)) AS a
    ON CONFLICT (creator_role_name) DO NOTHING;
 
    -- Generate relational intersection linkages
    INSERT INTO book_author (book_id, author_id, creator_role_id)
    SELECT DISTINCT nb.book_id, au.author_id, crt.creator_role_id
    FROM _input_books ib
    JOIN _new_books nb ON nb.ord = ib.ord
    JOIN jsonb_array_elements(COALESCE(ib.authors, '[]'::jsonb)) AS a ON true
    JOIN author_info au ON au.first_name = a->>'first_name' AND au.last_name  = a->>'last_name'
    JOIN creator_role_type crt ON crt.creator_role_name = COALESCE(a->>'role', 'Author')
    ON CONFLICT DO NOTHING;
 
    INSERT INTO book_genre (book_id, genre_id)
    SELECT DISTINCT nb.book_id, g.genre_id
    FROM _input_books ib
    JOIN _new_books nb ON nb.ord = ib.ord
    JOIN jsonb_array_elements_text(COALESCE(ib.genres, '[]'::jsonb)) AS gname ON true
    JOIN genre g ON g.genre_name = gname
    ON CONFLICT DO NOTHING;
 
    INSERT INTO book_media_type (book_id, media_type_id)
    SELECT DISTINCT nb.book_id, mt.media_type_id
    FROM _input_books ib
    JOIN _new_books nb ON nb.ord = ib.ord
    JOIN jsonb_array_elements_text(COALESCE(ib.media_types, '[]'::jsonb)) AS mname ON true
    JOIN media_type mt ON mt.media_type_name = mname
    ON CONFLICT DO NOTHING;
 
    RETURN QUERY SELECT nb.book_id, nb.book_title FROM _new_books nb ORDER BY nb.ord;
END;
$function$ LANGUAGE plpgsql;
 
-- 7. DATA SEEDING SETUP
INSERT INTO book_info (book_isbn, internal_code, book_title, publish_date, publisher, edition, issue_number, volume_number, page_amount, language) VALUES 
('9780451524935', NULL, '1984', '1949-06-08', 'Signet Classic', 'Centennial Edition', NULL, NULL, 328, 'en'),
('9780141439518', NULL, 'Pride and Prejudice', '1813-01-28', 'Penguin Classics', 'Deluxe Edition', NULL, NULL, 480, 'en'),
('9780060853983', NULL, 'Good Omens', '1990-05-01', 'William Morrow', 'International Edition', NULL, NULL, 412, 'en'),
(NULL, 'COMIC-BATMAN-V2-01', 'Batman: The Court of Owls', '2011-09-21', 'DC Comics', 'First Printing', '1', 2, 32, 'en'),
('9780000000099', NULL, 'Some Untitled Work', '2020-01-01', 'Unknown Press', NULL, NULL, NULL, NULL, NULL),
(NULL, 'COMIC-WATCHMEN-01', 'Watchmen', '1986-09-01', 'DC Comics', 'First Printing', '1', 1, 32, 'en');
 
INSERT INTO author_info (first_name, last_name) VALUES 
('George', 'Orwell'), ('Jane', 'Austen'), ('Terry', 'Pratchett'), ('Neil', 'Gaiman'),
('Scott', 'Snyder'), ('Greg', 'Capullo'), ('Alan', 'Moore'), ('Dave', 'Gibbons');
 
INSERT INTO creator_role_type (creator_role_name) VALUES
('Writer'), ('Penciler'), ('Inker'), ('Colorist'), ('Letterer'), ('Cover Artist'), ('Author');
 
INSERT INTO book_author (book_id, author_id, creator_role_id)
SELECT b.book_id, a.author_id, r.creator_role_id
FROM book_info b
JOIN author_info a ON
    (b.book_isbn = '9780451524935' AND a.first_name='George' AND a.last_name='Orwell') OR
    (b.book_isbn = '9780141439518' AND a.first_name='Jane' AND a.last_name='Austen') OR
    (b.book_isbn = '9780060853983' AND a.first_name IN ('Terry','Neil'))
JOIN creator_role_type r ON r.creator_role_name = 'Author';
 
INSERT INTO book_author (book_id, author_id, creator_role_id)
SELECT b.book_id, a.author_id, r.creator_role_id
FROM book_info b
JOIN author_info a ON
    (b.internal_code = 'COMIC-BATMAN-V2-01' AND a.first_name='Scott' AND a.last_name='Snyder') OR
    (b.internal_code = 'COMIC-WATCHMEN-01' AND a.first_name='Alan' AND a.last_name='Moore')
JOIN creator_role_type r ON r.creator_role_name = 'Writer';
 
INSERT INTO book_author (book_id, author_id, creator_role_id)
SELECT b.book_id, a.author_id, r.creator_role_id
FROM book_info b
JOIN author_info a ON
    (b.internal_code = 'COMIC-BATMAN-V2-01' AND a.first_name='Greg' AND a.last_name='Capullo') OR
    (b.internal_code = 'COMIC-WATCHMEN-01' AND a.first_name='Dave' AND a.last_name='Gibbons')
JOIN creator_role_type r ON r.creator_role_name = 'Penciler';
 
INSERT INTO genre (genre_name) VALUES 
('Dystopian Fiction'), ('Political Fiction'), ('Social Science Fiction'), 
('Fiction'), ('Satire'), ('Romance'), ('Novel of Manners'), ('Fantasy Comedy'),
('Superhero'), ('Mystery');
 
INSERT INTO book_genre (book_id, genre_id)
SELECT b.book_id, g.genre_id FROM book_info b 
JOIN genre g ON 
    (b.book_isbn = '9780451524935' AND g.genre_name IN ('Dystopian Fiction', 'Political Fiction', 'Social Science Fiction')) OR 
    (b.book_isbn = '9780141439518' AND g.genre_name IN ('Fiction', 'Satire', 'Romance', 'Novel of Manners')) OR 
    (b.book_isbn = '9780060853983' AND g.genre_name IN ('Fiction', 'Satire', 'Fantasy Comedy')) OR
    (b.internal_code = 'COMIC-BATMAN-V2-01' AND g.genre_name IN ('Superhero', 'Mystery')) OR
    (b.internal_code = 'COMIC-WATCHMEN-01' AND g.genre_name IN ('Superhero', 'Mystery', 'Dystopian Fiction'));
 
INSERT INTO media_type (media_type_name) VALUES 
('Book/Novel'), ('E-book'), ('Audiobook'), ('Online Text'), ('Print Novel'),
('Comic Book (Single Issue)'), ('Graphic Novel / Trade Paperback');
 
INSERT INTO book_media_type (book_id, media_type_id)
SELECT b.book_id, m.media_type_id FROM book_info b 
JOIN media_type m ON 
    (b.book_isbn = '9780451524935' AND m.media_type_name IN ('Print Novel', 'E-book')) OR 
    (b.book_isbn = '9780141439518' AND m.media_type_name IN ('Print Novel', 'Audiobook')) OR 
    (b.book_isbn = '9780060853983' AND m.media_type_name IN ('Print Novel')) OR
    (b.internal_code = 'COMIC-BATMAN-V2-01' AND m.media_type_name IN ('Comic Book (Single Issue)')) OR
    (b.internal_code = 'COMIC-WATCHMEN-01' AND m.media_type_name IN ('Graphic Novel / Trade Paperback'));
 
INSERT INTO book_adaptation (book_id, adaptation_type, title, release_date)
SELECT b.book_id, 'Television Series', 'Good Omens', '2019-05-31'
FROM book_info b WHERE b.book_isbn = '9780060853983';

-- Board Game Seed Executions
INSERT INTO game_info (game_title, publisher, release_date, min_players, max_players, play_time_minutes, min_age, game_description) VALUES
('Catan', 'Kosmos', '1995-01-01', 3, 4, 90, 10, 'Trade, build, and settle the island of Catan.'),
('Codenames', 'Czech Games Edition', '2015-03-14', 2, 8, 15, 14, 'Two rival spymasters give one-word clues to lead their teammates to the right agents.'),
('Pandemic', 'Z-Man Games', '2008-08-01', 2, 4, 45, 8, 'Work together as a team of specialists to stop four diseases from spreading across the globe.'),
('Ticket to Ride', 'Days of Wonder', '2004-01-01', 2, 5, 60, 8, 'Collect train cards to claim railway routes connecting cities across the map.'),
('Wingspan', 'Stonemaier Games', '2019-03-01', 1, 5, 70, 10, 'Attract a beautiful and diverse collection of birds to your wildlife preserve.');

INSERT INTO designer_info (first_name, last_name) VALUES
('Klaus', 'Teuber'), ('Vlaada', 'Chvatil'), ('Matt', 'Leacock'), ('Alan', 'Moon'), ('Elizabeth', 'Hargrave');

INSERT INTO game_designer (game_id, designer_id)
SELECT g.game_id, d.designer_id
FROM game_info g
JOIN designer_info d ON
    (g.game_title = 'Catan' AND d.first_name = 'Klaus' AND d.last_name = 'Teuber') OR
    (g.game_title = 'Codenames' AND d.first_name = 'Vlaada' AND d.last_name = 'Chvatil') OR
    (g.game_title = 'Pandemic' AND d.first_name = 'Matt' AND d.last_name = 'Leacock') OR
    (g.game_title = 'Ticket to Ride' AND d.first_name = 'Alan' AND d.last_name = 'Moon') OR
    (g.game_title = 'Wingspan' AND d.first_name = 'Elizabeth' AND d.last_name = 'Hargrave');

INSERT INTO genre (genre_name) VALUES
('Strategy'), ('Party'), ('Cooperative'), ('Family'), ('Engine Building')
ON CONFLICT DO NOTHING;

INSERT INTO game_genre (game_id, genre_id)
SELECT g.game_id, gn.genre_id FROM game_info g
JOIN genre gn ON
    (g.game_title = 'Catan' AND gn.genre_name IN ('Strategy', 'Family')) OR
    (g.game_title = 'Codenames' AND gn.genre_name IN ('Party')) OR
    (g.game_title = 'Pandemic' AND gn.genre_name IN ('Strategy', 'Cooperative')) OR
    (g.game_title = 'Ticket to Ride' AND gn.genre_name IN ('Strategy', 'Family')) OR
    (g.game_title = 'Wingspan' AND gn.genre_name IN ('Strategy', 'Engine Building', 'Family'));

-- Execute Function Verification Payload
SELECT * FROM bulk_insert_books('[
  {
    "isbn": "9780000000101",
    "title": "Animal Farm",
    "publish_date": "1945-08-17",
    "publisher": "Secker & Warburg",
    "language": "en",
    "authors": [{"first_name": "George", "last_name": "Orwell", "role": "Author"}],
    "genres": ["Political Fiction", "Satire"],
    "media_types": ["Print Novel", "E-book"]
  },
  {
    "internal_code": "COMIC-NEWSERIES-01",
    "title": "Some New Series #1",
    "publish_date": "2024-02-01",
    "publisher": "Indie Press",
    "language": "en",
    "authors": [{"first_name": "Robin", "last_name": "Newauthor", "role": "Dynamic Testing Role"}],
    "genres": ["Superhero", "New Speculative Genre"],
    "media_types": ["Comic Book (Single Issue)"]
  }
]'::jsonb);
 
INSERT INTO reader_info (username, email, password_hash, offline_sync_enabled) VALUES 
('grace_reads', 'grace@example.com', '$2b$12$V7b...', false), 
('booklover42', 'lover42@example.com', '$2b$12$X9z...', true);
 
INSERT INTO book_tracking(user_id, book_id, book_summary, book_ratings, read_status) VALUES 
(
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT book_id FROM book_info WHERE book_isbn = '9780451524935'),
    'A chilling look at totalitarian surveillance.', 5, 'finished'
),
(
    (SELECT user_id FROM reader_info WHERE username = 'booklover42'),
    (SELECT book_id FROM book_info WHERE book_isbn = '9780141439518'),
    'Wit, romance, and social commentary done right.', 5, 'finished'
),
(
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT book_id FROM book_info WHERE internal_code = 'COMIC-BATMAN-V2-01'),
    'The introduction of the Court of Owls storyline!', 5, 'reading'
);
 
-- User Tracking Activity
INSERT INTO game_tracking (user_id, game_id, game_notes, game_ratings, play_status) VALUES
(
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT game_id FROM game_info WHERE game_title = 'Wingspan'),
    'Gorgeous artwork, great solo mode.', 5, 'played'
),
(
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT game_id FROM game_info WHERE game_title = 'Pandemic'),
    'Tense co-op, want to try the expansions.', 4, 'owned'
),
(
    (SELECT user_id FROM reader_info WHERE username = 'booklover42'),
    (SELECT game_id FROM game_info WHERE game_title = 'Codenames'),
    'Perfect for game night with a big group.', 5, 'played'
),
(
    (SELECT user_id FROM reader_info WHERE username = 'booklover42'),
    (SELECT game_id FROM game_info WHERE game_title = 'Catan'),
    NULL, NULL, 'want'
);

INSERT INTO reading_progress (user_id, book_id, progress_percent) VALUES
((SELECT user_id FROM reader_info WHERE username = 'grace_reads'), (SELECT book_id FROM book_info WHERE internal_code = 'COMIC-BATMAN-V2-01'), 45.00),
((SELECT user_id FROM reader_info WHERE username = 'grace_reads'), (SELECT book_id FROM book_info WHERE book_isbn = '9780451524935'), 100.00);
 
UPDATE book_tracking
SET book_ratings = 5
WHERE user_id = (SELECT user_id FROM reader_info WHERE username = 'grace_reads')
  AND book_id = (SELECT book_id FROM book_info WHERE internal_code = 'COMIC-BATMAN-V2-01');

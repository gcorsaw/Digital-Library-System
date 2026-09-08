CREATE EXTENSION IF NOT EXISTS citext;
-- CHANGE: citext used for username/email and all lookup-table names so
-- 'Fiction' and 'fiction' (or 'Grace'/'grace') can't both get inserted
-- as distinct rows.

DROP TABLE IF EXISTS reading_progress CASCADE;
DROP TABLE IF EXISTS book_adaptation CASCADE;
DROP TABLE IF EXISTS book_tracking CASCADE;
DROP TABLE IF EXISTS book_genre CASCADE;
DROP TABLE IF EXISTS book_media_type CASCADE;
DROP TABLE IF EXISTS book_author CASCADE;
DROP TABLE IF EXISTS creator_role_type CASCADE;
DROP TABLE IF EXISTS genre CASCADE;
DROP TABLE IF EXISTS media_type CASCADE;
DROP TABLE IF EXISTS book_info CASCADE;
DROP TABLE IF EXISTS reader_info CASCADE;
DROP TABLE IF EXISTS author_info CASCADE;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE if not exists author_info (
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

CREATE TABLE if not exists book_info (
    book_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_isbn VARCHAR(20) UNIQUE,
    internal_code VARCHAR(50) UNIQUE,
    book_title VARCHAR(255) NOT NULL,
    publish_date DATE,
    publisher VARCHAR(255),
    edition VARCHAR(50),
    issue_number VARCHAR(50) default null,
    volume_number INT default null,
    page_amount INT default null,
    book_description TEXT,
    language VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(book_title, '') || ' ' || coalesce(book_description, ''))
    ) STORED,
    CONSTRAINT chk_has_identifier CHECK (book_isbn IS NOT NULL OR internal_code IS NOT NULL)
);

CREATE INDEX idx_book_info_search ON book_info USING GIN (search_vector);

CREATE TRIGGER trigger_book_info_updated
BEFORE UPDATE ON book_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE if not exists creator_role_type (
    creator_role_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creator_role_name CITEXT UNIQUE NOT NULL
);

-- CHANGE: explicit ON DELETE RESTRICT on creator_role_id — documenting
-- the (already-implicit) decision that a role can't be deleted while any
-- book_author row still references it. Switch to ON DELETE SET NULL with
-- a nullable column if you'd rather allow role deletion and lose the
-- association instead.
CREATE TABLE if not exists book_author (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    author_id INT REFERENCES author_info(author_id) ON DELETE CASCADE,
    creator_role_id INT NOT NULL REFERENCES creator_role_type(creator_role_id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, author_id, creator_role_id)  -- This is going to allow for multi-author configurations for books
);

/*
 The timestampz command is used to store the time stamp with the timezone information.
 This is important for tracking when the user was created and when they last updated their information,
 this will also provide the time and date of when the user was created their information in the system.
 then the default value is set to the current time and date when the user is created in the system.
*/
CREATE TABLE if not exists reader_info (
    user_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username CITEXT UNIQUE NOT NULL,
    email CITEXT UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    external_auth_id VARCHAR(255) UNIQUE,
    offline_sync_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_auth_method CHECK (password_hash IS NOT NULL OR external_auth_id IS NOT NULL)
);

/*
 Similar to the reader_info table, the book_tracking table utilizes the timestampz
 command to store the date and the time of when the book was added to the user's list.
 A trigger (trigger_book_tracking_updated) refreshes the updated_at timestamp automatically
 whenever the user updates their book information, whether that's the book summary, the
 book ratings, or the read status of the book.
 Together, added_at and updated_at allow the system to track when the user last updated
 their book information, and when they added the book to their list.
 The system also allows the user to track their reading progress, and to provide the user
 with a history of their reading progress; this is handled by the separate reading_progress
 table below rather than by this table, since progress changes far more often than the
 rest of a tracking entry and deserves its own history rather than overwriting a single value.
 The primary key for this table contains both a user_id and a book_id, this is to ensure
 that the user can only have one entry for each book in their list.
*/
CREATE TABLE if not exists book_tracking (
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

CREATE TABLE if not exists reading_progress (
    progress_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    book_id INT NOT NULL,
    progress_percent NUMERIC(5,2) CHECK (progress_percent BETWEEN 0 AND 100),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id, book_id) REFERENCES book_tracking(user_id, book_id) ON DELETE CASCADE
);

CREATE INDEX index_reading_progress_user_book ON reading_progress(user_id, book_id);

CREATE TABLE if not exists genre (
    genre_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    genre_name CITEXT UNIQUE NOT NULL
);

CREATE TABLE if not exists book_genre (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, genre_id)
);

CREATE TABLE if not exists media_type (
    media_type_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_type_name CITEXT UNIQUE NOT NULL
);

CREATE TABLE if not exists  book_media_type (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    media_type_id INT REFERENCES media_type(media_type_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, media_type_id)
);


CREATE TABLE if not exists book_adaptation (
    adaptation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id INT NOT NULL REFERENCES book_info(book_id) ON DELETE CASCADE,
    adaptation_type VARCHAR(50) NOT NULL CHECK (adaptation_type IN ('Feature Film', 'Television Series', 'Stage Play', 'Radio Drama', 'Video Game')),
    title VARCHAR(255) NOT NULL,
    release_date DATE
);

CREATE INDEX index_book_adaptation_book_id ON book_adaptation(book_id);
CREATE INDEX IF NOT EXISTS index_book_author_author_id ON book_author(author_id);

CREATE INDEX IF NOT EXISTS index_book_genre_genre_id
    ON book_genre(genre_id);

CREATE INDEX IF NOT EXISTS index_book_media_type_media_type_id
    ON book_media_type(media_type_id);

CREATE INDEX IF NOT EXISTS index_book_tracking_book_id
    ON book_tracking(book_id);

INSERT INTO book_info (book_isbn, internal_code, book_title, publish_date, publisher, edition, issue_number, volume_number, page_amount, language) VALUES 
('9780451524935', NULL, '1984', '1949-06-08', 'Signet Classic', 'Centennial Edition', NULL, NULL, 328, 'en'),
('9780141439518', NULL, 'Pride and Prejudice', '1813-01-28', 'Penguin Classics', 'Deluxe Edition', NULL, NULL, 480, 'en'),
('9780060853983', NULL, 'Good Omens', '1990-05-01', 'William Morrow', 'International Edition', NULL, NULL, 412, 'en'),
(NULL, 'COMIC-BATMAN-V2-01', 'Batman: The Court of Owls', '2011-09-21', 'DC Comics', 'First Printing', '1', 2, 32, 'en'),
('9780000000099', NULL, 'Some Untitled Work', '2020-01-01', 'Unknown Press', NULL, NULL, NULL, NULL, NULL),
(NULL, 'COMIC-WATCHMEN-01', 'Watchmen', '1986-09-01', 'DC Comics', 'First Printing', '1', 1, 32, 'en');

INSERT INTO author_info (first_name, last_name) VALUES 
('George', 'Orwell'),
('Jane', 'Austen'),
('Terry', 'Pratchett'),
('Neil', 'Gaiman'),
('Scott', 'Snyder'),
('Greg', 'Capullo'),
('Alan', 'Moore'),
('Dave', 'Gibbons');

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

INSERT INTO reading_progress (user_id, book_id, progress_percent)
VALUES
(
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT book_id FROM book_info WHERE internal_code = 'COMIC-BATMAN-V2-01'),
    45.00
),
(
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT book_id FROM book_info WHERE book_isbn = '9780451524935'),
    100.00
);

UPDATE book_tracking
SET book_ratings = 5
WHERE user_id = (SELECT user_id FROM reader_info WHERE username = 'grace_reads')
  AND book_id = (SELECT book_id FROM book_info WHERE internal_code = 'COMIC-BATMAN-V2-01');

UPDATE book_info 
SET publisher = 'Signet Classic', edition = 'Centennial Edition' 
WHERE book_isbn = '9780451524935';

UPDATE book_info 
SET publisher = 'Penguin Classics', edition = 'Deluxe Edition' 
WHERE book_isbn = '9780141439518';

UPDATE book_info 
SET publisher = 'William Morrow', edition = 'International Edition' 
WHERE book_isbn = '9780060853983';

SELECT * FROM author_info;
SELECT * FROM book_info;
SELECT * FROM reader_info;
SELECT * FROM book_tracking;
SELECT * FROM reading_progress;
SELECT * FROM genre;
SELECT * FROM book_genre;
SELECT * FROM media_type;
SELECT * FROM book_author;
SELECT * FROM book_media_type;
SELECT * FROM book_adaptation;
SELECT * FROM creator_role_type;
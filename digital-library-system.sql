DROP TABLE IF EXISTS book_tracking CASCADE;
DROP TABLE IF EXISTS book_genre CASCADE;
DROP TABLE IF EXISTS book_media_type CASCADE;
DROP TABLE IF EXISTS book_author CASCADE;
DROP TABLE IF EXISTS genre CASCADE;
DROP TABLE IF EXISTS media_type CASCADE;
DROP TABLE IF EXISTS book_info CASCADE;
DROP TABLE IF EXISTS reader_info CASCADE;
DROP TABLE IF EXISTS author_info CASCADE;

CREATE TABLE author_info (
    author_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    CONSTRAINT uq_author_name UNIQUE (first_name, last_name)
);

CREATE TABLE book_info (
    book_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_isbn VARCHAR(20) UNIQUE,
    book_title VARCHAR(255) NOT NULL,
    publish_date DATE
);

CREATE TABLE book_author (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    author_id INT REFERENCES author_info(author_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)  -- This is going to allow for multi-author configurations for books
);

CREATE TABLE reader_info (
    user_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    external_auth_id VARCHAR(255) UNIQUE,
    offline_sync_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE book_tracking (
    user_id INT REFERENCES reader_info(user_id) ON DELETE CASCADE,
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    book_summary VARCHAR(300),
    book_ratings INT CHECK (book_ratings BETWEEN 1 AND 5),
    read_status VARCHAR(10) NOT NULL DEFAULT 'want' CHECK (read_status IN ('want', 'reading', 'finished')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, book_id)
);

CREATE TABLE genre (
    genre_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    genre_name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE book_genre (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, genre_id)
);

CREATE TABLE media_type (
    media_type_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_type_name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE book_media_type (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    media_type_id INT REFERENCES media_type(media_type_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, media_type_id)
);


CREATE INDEX index_book_author_author_id ON book_author(author_id);
CREATE INDEX index_book_genre_genre_id ON book_genre(genre_id);
CREATE INDEX index_book_media_type_media_type_id ON book_media_type(media_type_id);
CREATE INDEX index_book_tracking_book_id ON book_tracking(book_id);

INSERT INTO book_info(book_isbn, book_title, publish_date) VALUES 
('9780451524935', '1984', '1949-06-08'),
('9780141439518', 'Pride and Prejudice', '1813-01-28'),
('9780060853983', 'Good Omens', '1990-05-01');

INSERT INTO author_info (first_name, last_name) VALUES 
('George', 'Orwell'),
('Jane', 'Austen'),
('Terry', 'Pratchett'),
('Neil', 'Gaiman');

INSERT INTO book_author (book_id, author_id)
SELECT b.book_id, a.author_id FROM book_info b 
JOIN author_info a ON 
    (b.book_isbn = '9780451524935' AND a.first_name='George' AND a.last_name='Orwell') OR 
    (b.book_isbn = '9780141439518' AND a.first_name='Jane' AND a.last_name='Austen') OR 
    (b.book_isbn = '9780060853983' AND a.first_name IN ('Terry','Neil'));

INSERT INTO genre (genre_name) VALUES 
('Dystopian Fiction'), ('Political Fiction'), ('Social Science Fiction'), 
('Fiction'), ('Satire'), ('Romance'), ('Novel of Manners'), ('Fantasy Comedy');

INSERT INTO book_genre (book_id, genre_id)
SELECT b.book_id, g.genre_id FROM book_info b 
JOIN genre g ON 
    (b.book_isbn = '9780451524935' AND g.genre_name IN ('Dystopian Fiction', 'Political Fiction', 'Social Science Fiction')) OR 
    (b.book_isbn = '9780141439518' AND g.genre_name IN ('Fiction', 'Satire', 'Romance', 'Novel of Manners')) OR 
    (b.book_isbn = '9780060853983' AND g.genre_name IN ('Fiction', 'Satire', 'Fantasy Comedy'));

INSERT INTO media_type (media_type_name) VALUES 
('Book/Novel'), ('Feature Film'), ('Television Series'), 
('E-book'), ('Audiobook'), ('Online Text'), ('Print Novel');

INSERT INTO book_media_type (book_id, media_type_id)
SELECT b.book_id, m.media_type_id FROM book_info b 
JOIN media_type m ON 
    (b.book_isbn = '9780451524935' AND m.media_type_name IN ('Print Novel', 'E-book')) OR 
    (b.book_isbn = '9780141439518' AND m.media_type_name IN ('Print Novel', 'Audiobook')) OR 
    (b.book_isbn = '9780060853983' AND m.media_type_name IN ('Print Novel', 'Television Series'));

INSERT INTO reader_info (username, email, password_hash, offline_sync_enabled) VALUES 
('grace_reads', 'grace@example.com', '$2b$12$V7b...', false), 
('booklover42', 'lover42@example.com', '$2b$12$X9z...', true);

INSERT INTO book_tracking(user_id, book_id, book_summary, book_ratings, read_status) VALUES (
    (SELECT user_id FROM reader_info WHERE username = 'grace_reads'),
    (SELECT book_id FROM book_info WHERE book_isbn = '9780451524935'),
    'A chilling look at totalitarian surveillance.', 5, 'finished'
),
(
    (SELECT user_id FROM reader_info WHERE username = 'booklover42'),
    (SELECT book_id FROM book_info WHERE book_isbn = '9780141439518'),
    'Wit, romance, and social commentary done right.', 5, 'finished'
);

SELECT * FROM author_info;
SELECT * FROM book_info;
SELECT * FROM reader_info;
SELECT * FROM book_tracking;
SELECT * FROM genre;
SELECT * FROM book_genre;
SELECT * FROM media_type;
SELECT * FROM book_author;
SELECT * FROM book_media_type;
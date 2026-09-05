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
    publish_date DATE,
    publisher VARCHAR(255),
    edition VARCHAR(50),
    issue_number VARCHAR(50) default null,
    volume_number INT default null
);

CREATE TABLE book_author (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    author_id INT REFERENCES author_info(author_id) ON DELETE CASCADE,
    creator_role VARCHAR(50) not null check (creator_role in ('Writer', 'Penciler', 'Inker', 'Colorist', 'Letterer', 'Cover Artist', 'Author')),
    PRIMARY KEY (book_id, author_id, creator_role)  -- This is going to allow for multi-author configurations for books
);

CREATE TABLE reader_info (
    user_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    external_auth_id VARCHAR(255) UNIQUE,
    offline_sync_enabled BOOLEAN DEFAULT TRUE,
    /*
     The timestampz command is used to store the time stamp with the timezone information.
     This is important for tracking when the user was created and when they last updated their information,
     this will also provide the time and date of when the user was created their information in the system.
     then the default value is set to the current time and date when the user is created in the system.
    */
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
/*
Similar to the reader_info table, the book_tracking table utilizes the timestampz
command to store the date and the time of when the book was added to the user's list.
This table will also update the timestampz when the user updates their book information,
this would include whether they're updating the book summary, the book ratings, or the read status of the book.
Both of these two new parts of the table will allow for the system to track when the user last updated their book 
information, and when they added the book to their list.
The system will also allow for the user to track their reading progress, and the system will be able to provide
the user with a history of their reading progress. The primary key for this table contains
both a user_id and a book_id, this is to ensure that the user can only have one
entry for each book in their list. 
*/
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
    media_type_name VARCHAR(50) UNIQUE NOT null
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

INSERT INTO book_info (book_isbn, book_title, publish_date, publisher, edition, issue_number, volume_number) VALUES 
('9780451524935', '1984', '1949-06-08', 'Signet Classic', 'Centennial Edition', NULL, NULL),
('9780141439518', 'Pride and Prejudice', '1813-01-28', 'Penguin Classics', 'Deluxe Edition', NULL, NULL),
('9780060853983', 'Good Omens', '1990-05-01', 'William Morrow', 'International Edition', NULL, NULL),
('COMIC-BATMAN-V2-01', 'Batman: The Court of Owls', '2011-09-21', 'DC Comics', 'First Printing', '1', 2),
('COMIC-WATCHMEN-01', 'Watchmen', '1986-09-01', 'DC Comics', 'First Printing', '1', 1);

INSERT INTO author_info (first_name, last_name) VALUES 
('George', 'Orwell'),
('Jane', 'Austen'),
('Terry', 'Pratchett'),
('Neil', 'Gaiman'),
('Scott', 'Snyder'),
('Greg', 'Capullo'),
('Alan', 'Moore'),
('Dave', 'Gibbons');

-- Map creators explicitly to roles
INSERT INTO book_author (book_id, author_id, creator_role)
SELECT b.book_id, a.author_id, 'Author' FROM book_info b JOIN author_info a ON 
    (b.book_isbn = '9780451524935' AND a.first_name='George' AND a.last_name='Orwell') OR 
    (b.book_isbn = '9780141439518' AND a.first_name='Jane' AND a.last_name='Austen') OR 
    (b.book_isbn = '9780060853983' AND a.first_name IN ('Terry','Neil'));

INSERT into book_author (book_id, author_id, creator_role)
SELECT b.book_id, a.author_id, 'Writer' FROM book_info b JOIN author_info a ON 
    (b.book_isbn = 'COMIC-BATMAN-V2-01' AND a.first_name='Scott' AND a.last_name='Snyder') OR
    (b.book_isbn = 'COMIC-WATCHMEN-01' AND a.first_name='Alan' AND a.last_name='Moore');

INSERT INTO book_author (book_id, author_id, creator_role)
SELECT b.book_id, a.author_id, 'Penciler' FROM book_info b JOIN author_info a ON 
    (b.book_isbn = 'COMIC-BATMAN-V2-01' AND a.first_name='Greg' AND a.last_name='Capullo') OR
    (b.book_isbn = 'COMIC-WATCHMEN-01' AND a.first_name='Dave' AND a.last_name='Gibbons');

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
    (b.book_isbn = 'COMIC-BATMAN-V2-01' AND g.genre_name IN ('Superhero', 'Mystery')) OR
    (b.book_isbn = 'COMIC-WATCHMEN-01' AND g.genre_name IN ('Superhero', 'Mystery', 'Dystopian Fiction'));

INSERT INTO media_type (media_type_name) VALUES 
('Book/Novel'), ('Feature Film'), ('Television Series'), 
('E-book'), ('Audiobook'), ('Online Text'), ('Print Novel'),
('Comic Book (Single Issue)'), ('Graphic Novel / Trade Paperback');

INSERT INTO book_media_type (book_id, media_type_id)
SELECT b.book_id, m.media_type_id FROM book_info b 
JOIN media_type m ON 
    (b.book_isbn = '9780451524935' AND m.media_type_name IN ('Print Novel', 'E-book')) OR 
    (b.book_isbn = '9780141439518' AND m.media_type_name IN ('Print Novel', 'Audiobook')) OR 
    (b.book_isbn = '9780060853983' AND m.media_type_name IN ('Print Novel', 'Television Series')) OR
    (b.book_isbn = 'COMIC-BATMAN-V2-01' AND m.media_type_name IN ('Comic Book (Single Issue)')) OR
    (b.book_isbn = 'COMIC-WATCHMEN-01' AND m.media_type_name IN ('Graphic Novel / Trade Paperback'));

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
    (SELECT book_id FROM book_info WHERE book_isbn = 'COMIC-BATMAN-V2-01'),
    'The introduction of the Court of Owls storyline!', 5, 'reading'
);
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
SELECT * FROM genre;
SELECT * FROM book_genre;
SELECT * FROM media_type;
SELECT * FROM book_author;
SELECT * FROM book_media_type;
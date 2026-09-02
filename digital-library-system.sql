-- this table is going to generate a unique author ID for each author that the 
-- user adds to the database, as well as store the author's first and last name.
create table author_info(
	author_id INT generated always as identity primary key,
	first_name VARCHAR(50),
	last_name VARCHAR(50)
);

-- this table is going to generate a unique book ID for each book, as well as 
-- store the book's ISBN, title, author ID (which references the author_info table), 
-- and publish date.
create table book_info(
	book_id INT generated always as identity primary key,
	book_isbn VARCHAR(20) unique,
	book_title VARCHAR(255) not null,
	publish_date date
);

create table book_author(
	book_id INT references book_info(book_id) on delete cascade,
	author_id INT references author_info(author_id) on delete cascade,
	primary key (book_id, author_id)
);
-- this table is going to allow for users to generate a unique user ID and username, 
-- as well as a boolean value to indicate whether or not the user has enabled 
-- offline synchronization for their reading progress.
create table reader_info(
	user_id INT generated always as identity primary key,
	username VARCHAR(50) unique not null,
	offline_sync_enabled boolean default true
);

-- this table is going to allow for users to track their reading progress, including 
-- the books they have read, their ratings, and their current reading status.
create table book_tracking(
	user_id INT references reader_info(user_id) on delete cascade,
	book_id INT references book_info(book_id) on delete cascade,
	book_summary VARCHAR(300),
	book_ratings INT check (book_ratings between 1 and 5),
	read_status VARCHAR(10) not null default 'want'
		check (read_status in ('want', 'reading', 'finished')),
	primary key (user_id, book_id)
);

-- this table is going to establish a way for books to be categorized into genres, 
-- allowing for multiple genres to be associated with a single book and vice versa.
create table genre(
	genre_id INT generated always as identity primary key,
	genre_name VARCHAR(50) unique not null
);

-- This table is going to allow for users to add genres to books, establishing a 
-- many-to-many relationship between books and genres.
create table book_genre(
	book_id INT references book_info(book_id) on delete cascade,
	genre_id INT references genre(genre_id) on delete cascade,
	primary key (book_id, genre_id)
);
-- This table is going to allow for the categorization of books into different media types, 
--such as print, digital, or audio formats.
create table media_type(
	media_type_id INT generated always as identity primary key,
	media_type_name VARCHAR(50) unique not null
);

-- This table establishes a many-to-many relationship between books and media types, 
-- allowing for multiple media types to be associated with a single book and vice versa.
create table book_media_type(
	book_id INT references book_info(book_id) on delete cascade,
	media_type_id INT references media_type(media_type_id) on delete cascade,
	primary key (book_id, media_type_id)
);
insert into book_info(book_isbn, book_title, publish_date) values
('9780451524935', '1984', '1949-06-08'),
('9780141439518', 'Pride and Prejudice', '1813-01-28'),
('9780060853983', 'Good Omens', '1990-05-01');

insert into author_info (first_name, last_name) values
('George', 'Orwell'),
('Jane', 'Austen'),
('Terry', 'Pratchett'),
('Neil', 'Gaiman');

insert into book_author (book_id, author_id)
select b.book_id, a.author_id
from book_info b
join author_info a on
	(b.book_isbn = '9780451524935' and a.first_name='George' and a.last_name='Orwell')
	or (b.book_isbn = '9780141439518' and a.first_name='Jane' and a.last_name='Austen')
	or (b.book_isbn = '9780060853983' and a.first_name in ('Terry','Neil'));

insert into genre (genre_name) values
('Dystopian Fiction'), ('Political Fiction'), ('Social Science Fiction'),
('Fiction'), ('Satire'), ('Romance'), ('Novel of Manners');

insert into book_genre (book_id, genre_id)
select b.book_id, g.genre_id
from book_info b
join genre g on
	(b.book_isbn = '9780451524935' and g.genre_name in ('Dystopian Fiction', 'Political Fiction', 'Social Science Fiction'))
	or (b.book_isbn = '9780141439518' and g.genre_name in ('Fiction', 'Satire', 'Romance', 'Novel of Manners'));

insert into media_type (media_type_name) values
('Book/Novel'), ('Feature Film'),
('Television Series'), ('E-book'), ('Audiobook'), ('Online Text'), ('Print Novel');

insert into reader_info (username, offline_sync_enabled) values
('grace_reads', false),
('booklover42', true);

insert into book_tracking(user_id, book_id, book_summary, book_ratings, read_status) values
(
	(select user_id from reader_info where username = 'grace_reads'),
	(select book_id from book_info where book_isbn = '9780451524935'),
	'A chilling look at totalitarian surveillance.', 5, 'finished'
),
(
	(select user_id from reader_info where username = 'booklover42'),
	(select book_id from book_info where book_isbn = '9780141439518'),
	'Wit, romance, and social commentary done right.', 5, 'finished'
);

select * from author_info;
select * from book_info;
select * from reader_info;
select * from book_tracking;
select * from genre;
select * from book_genre;
select * from media_type;
select * from book_author;

drop table if exists book_tracking;
drop table if exists book_genre;
drop table if exists book_media_type;
drop table if exists genre;
drop table if exists media_type;
drop table if exists book_info;
drop table if exists reader_info;
drop table if exists author_info;
drop table if exists book_author;

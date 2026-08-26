create table author_info(
	author_id INT generated always as identity primary key,
	first_name VARCHAR(50),
	last_name VARCHAR(50)
);

create table book_info(
	book_id INT generated always as identity primary key,	
	book_isbn VARCHAR(20) unique,
	book_title VARCHAR(255) not null,
	author_id INT references author_info(author_id),
	publish_date date
);

create table reader_info(
	user_id INT generated always as identity primary key,
	username varchar(50) unique not null,
	is_offline boolean default true
);

create table book_tracking(
	user_id INT references reader_info(user_id) on delete cascade,
	book_id INT references book_info(book_id) on delete cascade,
	book_summary varchar(300),
	book_ratings INT not null check (book_ratings between 1 and 5),
	read_status boolean default false not null,
	primary key (user_id, book_id)
);

insert into author_info (first_name, last_name) values
('George', 'Orwell'),
('Jane', 'Austen');

insert into book_info(book_isbn, book_title, author_id, publish_date) values
('9780451524935', '1984', (select author_id from author_info where first_name='George' and last_name='Orwell'), '1949-06-08'),
('9780141439518', 'Pride and Prejudice', (select author_id from author_info where first_name='Jane' and last_name='Austen'), '1813-01-28');

insert into reader_info (username, is_offline) values
('grace_reads', false),
('booklover42', true);

insert into book_tracking(user_id, book_id, book_summary, book_ratings, read_status) values
(
	(select user_id from reader_info where username = 'grace_reads'),
	(select book_id from book_info where book_isbn = '9780451524935'),
	'A chilling look at totalitarian surveillance.', 5, true
),
(
	(select user_id from reader_info where username = 'booklover42'),
	(select book_id from book_info where book_isbn = '9780141439518'),
	'Wit, romance, and social commentary done right.', 5, true
);

select * from author_info;
select * from book_info;
select * from reader_info;
select * from book_tracking;

drop table if exists book_tracking;
drop table if exists book_info;
drop table if exists reader_info;
drop table if exists author_info;
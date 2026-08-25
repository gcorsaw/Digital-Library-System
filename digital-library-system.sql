create table author_info(
	author_id serial primary key,
	first_name VARCHAR(50),
	last_name VARCHAR(50)
);

create table book_info(
	book_id INT generated always as identity primary key,	
	book_isbn VARCHAR(20) unique,
	book_title VARCHAR(255) not null,
	author VARCHAR(50) not null,
	publish_date date
);

create table reader_info(
	user_id int generated always as identity primary key,
	username varchar(50) unique not null,
	is_offline boolean default true
);

create table book_tracking(
	user_id int references reader_info(user_id) on delete cascade,
	book_id int references book_info(book_id) on delete cascade,
	book_summary varchar(300),
	book_ratings int not null check (book_ratings between 1 and 5),
	read_status boolean default false not null,
	primary key (user_id, book_id)
);

insert into author_info (first_name, last_name) values
('George', 'Orwell'),
('Jane', 'Austen');

insert into book_info(book_isbn, book_title, author, publish_date) values
('9780451524935', '1984', 'George Orwell', '1949-06-08'),
('9780141439518', 'Pride and Prejudice', 'Jane Austen', '1813-01-28');

insert into reader_info (username, is_offline) values
('grace_reads', false),
('booklover42', true);

insert into book_tracking(user_id, book_id, book_summary, book_ratings, read_status) values
(1, 1, 'A chilling look at totalitarian surveillance.', 5, true),
(2, 2, 'Wit, romance, and social commentary done right.', 5, true);

select * from author_info;
select * from book_info;
select * from reader_info;
select * from book_tracking;

drop table if exists book_tracking;
drop table if exists book_info;
drop table if exists reader_info;
drop table if exists author_info;
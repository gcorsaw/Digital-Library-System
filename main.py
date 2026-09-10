import os
import logging
from datetime import date
from contextlib import asynccontextmanager
from typing import Generator
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends, status
from pydantic import BaseModel, model_validator
import uvicorn

# Be sure to export environment variables before connecting
# export DB_NAME=mydatabase
# export DB_USER=gcorsaw
# export DB_PASSWORD=DadR0cks
# export DB_HOST=localhost
# export DB_PORT=5440
#
# You can also setup a .env file for your project and put in the variables
# needed to run the program. If you set environment variables and have a .env
# file the environment variable value will take priority over the .env value.
# Basically it does this:
# 1. Set the value by getting the value from .env
# 2. Set the value by getting the value from the shell environment values. This will
# overwrite any value that you got from the .env file.

load_dotenv()

"""The get_env function is going to be used to get the environment variables
that are needed to connect to the database. This function is also going to be used 
to get the environemnet variables thta are needed to connnect to the database.
The function is going to check if the environment variable is set, if it's not set,
then it's going to raise a RunTimeError. If the environment variable is set, 
then it's going to return the value of the environment variable."""
def get_env(env_name):
    env_value = os.environ.get(env_name)
    if env_value is not None:
        env_value = env_value.strip()

    if env_value is None and env_name == "DB_PORT":
        return "5440"

    if env_value in (None, ""):
        raise RuntimeError(f"Missing required environment variable: {env_name}")

    return env_value

"""
The DatabaseManager class is going to manage the connection pool to the already existing database.
The initialzie pool function is going create a pool of database connections. This function is giong to return
if there is no pool availabe and if there is a pool, it's going to try and make a simple connection with a minimum
connection fo 1 and a maximum connection of 20. The dbname and the variables that are following the maxconn follow
the same concept as the other functions. In the exception block, it's going to have an exception as an error,
this is then going to print the error and raise the error. The get_conn function is going to retrieve an available connection
from the pool. If there is no pool, then it's going to perform the initialize_pool funtion. If there is a connection, then it
will return the connection. As an additional note, the self._pool is going to be used as an internal use. The self means current
DatabaseManager instance and the _pool is going to be the attribute
that is holding the pool. The None in the first __init__ function is indicating 
that there is no pool that has been created yet. The release_conn is going to 
return the connection to the pool for reuse. The close_pool() function

"""
class DatabaseManager:
    def __init__(self):
        self._pool = None

    def initialize_pool(self) -> None:
        if self._pool is not None:
            return
        try:
            self._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=20,
                dbname=get_env("DB_NAME"),
                user=get_env("DB_USER"),
                password=get_env("DB_PASSWORD"),
                host=get_env("DB_HOST"),
                port=int(get_env("DB_PORT"))
            )
        except Exception as error:
            print(error)
            raise error

    def get_conn(self):
        if not self._pool:
            self.initialize_pool()
        return self._pool.getconn()

    def release_conn(self, conn):
        if self._pool and conn:
            self._pool.putconn(conn)

    def close_pool(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

db_manager = DatabaseManager()

"""
This function is going to be in charge of the FastAPI application
startup and shutdown lifecycle. The async def isi going to allows FastAPI
to manage the lifecycle asynchronously. The yield is going to keep the application
running and the code after the yield is going to run when the app shuts down.
The @asynccontextmanager is going to tell the FastAPI that this function has
setup and cleanup sections.
"""
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown seamlessly.
    This eradicates the 4 structural Pytest deprecation and resource wanings!
    """
    db_manager.initialize_pool()
    yield
    db_manager.close_pool()


# Define the app instance with the proper context lifespan attached
library_app = FastAPI(lifespan=lifespan)

"""
This function is giong to get the database cursor and it's paramters contain a yielded value (RealDictCurosr), a
value sent into the generator and a return value (both the return and the value sent into the generator are null).
Once the parameters are initialized, the connection is going to be instantiated to the db_manager and getting the
the connection and storing that into our connection variable. The cursor is going to store the connection.cursor
is going to ask PostgreSQL for a curosr and it's going to tell psycopg2 to return each database row as
a dictionary-like object. The try bok is going to yeild the curosr to the FastAPI endpoint through the 
Depends(get_db_cursor). It will commit if the connection succeeds, in the except block, the cursor is going 
to roll back if the exception occurs. In the finally block, it's going to close the cursor and
it's going to release the connection to the pool.
"""
def get_db_cursor() -> Generator[RealDictCursor, None, None]:
    connection = db_manager.get_conn()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        db_manager.release_conn(connection)

"""
The connect() function is going to create a connection to the database. The try block is going to create the connection to the database and the cursor is going to also make a connection.
The try block is also going to print the PostgreSQL database version and cursor is going to execute a select version of the database as well. THe value is then going to be stored in the version
varaible. It will then print the version. To end the try block, the cursor is going to close. In the except block, we're going to have 2 parameters and the first one is going to be an Exception and
the second paramter is going to be a psycopg2.DatabaseError, both of these parameters are going to be known as an error, if an error were to occur, we're going to print the error and raise it as well.
In the finally block, we're going to check to see if our connection is not null, if the condition is null, then we won't be entering the if block. However, if the conection is not null, then we're 
going to close the connection and print out the statement of `Database connection closed.`.
"""
def connect():
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor()
        print("PostgreSQL database version:")
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(version)

        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        raise(error)
    finally:
        if connection is not None:
            connection.close()
            print('Database connection closed.')

class Book(BaseModel):
    book_isbn: str | None = None
    internal_code: str | None = None
    book_title: str
    author_id: int | None = None
    creator_role_id: int | str | None = None
    publish_date: date | None = None

    @model_validator(mode="after")
    def validate_book_data(self):
        if not self.book_isbn and not self.internal_code:
            raise ValueError(
                "Either book_isbn or internal_code is required"
            )

        if (self.author_id is None) != (self.creator_role_id is None):
            raise ValueError(
                "author_id and creator_role_id must be provided together"
            )

        return self

class Book_Description(BaseModel):
    book_id: int
    book_title: str
    book_description: str | None = None

class Book_Description_Update(BaseModel):
    book_description: str

@library_app.get("/")
def read_root():
    return {"message": "Hello World"}


@library_app.get("/books")
def get_book_endpoint(cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        books = get_book_database()
        return {"books" : books}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@library_app.get("/books/summaries")
def get_book_summaries_from_database(cursor: RealDictCursor = Depends(get_db_cursor)):
    """In the try block, the connection to the database is going to be established. 
    The cursor is going to be initialized and the SELECT book_id, book_title FROM 
    book_info; command is going to be executed. the details_query variable is 
    going to be initialized and the cursor.fetchall() command is going to be executed.
    The fetchall() command is going to return all of the rows from the SELECT command.
    The cursor is going to be closed and the details_query variable is going to be returned
    as a dictionary with the "books" as the key. In the except block, if there's 
    an error, then the HTTPException is going to be raised with a status code of 500
    and the detail message is going to be "Could not find book details". 
    In the finally block, if the connection is not None, then the connection is
    going to be closed."""
    try:
        cursor.execute("SELECT book_id, book_title FROM book_info;")
        details_query = cursor.fetchall()
        return {"books": details_query}
    except Exception as e:
        raise HTTPException(status_code = 500, detail= "Could not find book details")

"""
This particular function (get_details_from_database) is defining a FastAPI dependency injection parameter. 
It's typically used in a route function to automatically provide an active database cursor for executing SQL   
queries. This is useful because it's going to allow us to search down the url with the cursor and have the dependecy
parameter. The : RealDictCusor is used because it would have the cursor return the query results as dictionaries where the
column names are keys instead of standard tuples and this is specific to psycopg2 (PostgreSQL). The = Depends(get_db_cursor) is
the FastAPI dependency injection symbol (Depends). This tells FastAPI to execute the get_db_cursor helper function before
running the route, and pass its return value into the cursor variable.
"""
@library_app.get("/books/info")
def get_details_from_database(cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute("SELECT * FROM book_info;")
        info_query = cursor.fetchall()
        return {"books":info_query}
    except Exception as e:
        raise HTTPException(status_code = 500, detail = "Could not find info")


@library_app.post("/books", status_code=status.HTTP_201_CREATED)
def user_add_book(book: Book, cursor: RealDictCursor = Depends(get_db_cursor)):
    """The first except block is going to be used to catch the psycopg2.errors.UniqueViolation error.
    This error is going to be raised if the user tries to add a book with an ISBN that already exists in the database. 
    The second except block is going to be used to catch the psy. The third 
    except block is going to be used to catch any other exceptions that may occur.
    The finally block is going to be used to close the connection to the database if it is not None. 
    This is going to ensure that the connection to the database is closed even if an error occurs.
    This is going to prevent any potential memory leaks or other issues that may arise from leaving the connection open."""
    try:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'book_info'
              AND column_name = 'internal_code';
            """
        )
        has_internal_code = cursor.fetchone() is not None
        insert_columns = ["book_isbn", "book_title", "publish_date"]
        insert_values = [book.book_isbn, book.book_title, book.publish_date]
        if has_internal_code:
            insert_columns.insert(1, "internal_code")
            insert_values.insert(1, book.internal_code)
        query = f"""
            INSERT INTO book_info ({', '.join(insert_columns)})
            VALUES ({', '.join(['%s'] * len(insert_columns))})
            RETURNING *;
        """
        cursor.execute(
            query,
            insert_values,
        )
        new_book = cursor.fetchone()

        if book.author_id is not None and book.creator_role_id is not None:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'book_author'
                  AND column_name = 'creator_role_id';
                """
            )
            has_role_id = cursor.fetchone() is not None
            role_column = "creator_role_id" if has_role_id else "creator_role"
            cursor.execute(
                f"INSERT INTO book_author (book_id, author_id, {role_column}) VALUES (%s, %s, %s);",
                (new_book["book_id"], book.author_id, book.creator_role_id),
            )

        return {"message": "Book added successfully", "book": new_book}
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="A book with this ISBN already exists.")
    except psycopg2.errors.ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="Invalid author_id. The author does not exist.")
    except psycopg2.errors.CheckViolation:
        raise HTTPException(status_code=400, detail="Book must have either an ISBN or an internal_code.")
    except psycopg2.Error as e:
        logging.exception("Database error in user_add_book")
        raise HTTPException(status_code=500, detail="A database error occurred while adding the book.")


"""The intention behind the search_title_by_word function is to allow for the user to search for a book by a specific word in the title. 
The function is going to check if the title parameter is empty or not. If the title parameter is empty, there is going to be an HTTPException
raised with a status code of 400 with the message of 'Title is required'. If the title paramter is not empty, then the function is going to check if there is a space in the title parameter. 
If there is a space in the title parameter, then there is going to be an HTTPException raised with a status code of 400 with the message of 'Please provide only one word to search'.
The function is going to make a connection to the database and initialize the cursor. 
The cursor is going to execute the SELECT * FROM book_info WHERE book_title ILIKE %s ORDER BY book_title; command. 
The % symbols are going to be used to indicate that the search patten can be 
anywhere in the book_title string. The cursor is going to fetch all of the results and return them as a dictionary with the query and books as the keys.
"""
@library_app.get("/books/search")
def search_title_by_word(title: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    title = title.strip()
    if " " in title:
        raise HTTPException(status_code=400, detail="Please provide only one word to search")

    try:
        query = """ 
                SELECT * 
                FROM book_info 
                WHERE book_title ILIKE %s 
                ORDER BY book_title;
        """
        search_patten = f"%{title}%"
        cursor.execute(query, (search_patten,))
        results = cursor.fetchall()
        return {"query": title, "books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@library_app.delete("/books/{book_id}")
def delete_book_endpoint(book_id: int, cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute(
            "DELETE FROM book_info WHERE book_id = %s RETURNING *;",
            (book_id,),
        )
        deleted_book = cursor.fetchone()

        if deleted_book is None:
            raise HTTPException(status_code=404, detail="Book not found")

        return {"message": "Book deleted successfully", "book": deleted_book}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete book: {str(e)}")


@library_app.put("/books/{book_id}/description", response_model=Book_Description)
def description_change(book_id: int, summary: Book_Description_Update, cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute(
            "UPDATE book_info SET book_description = %s WHERE book_id = %s RETURNING book_id, book_title, book_description;",
            (summary.book_description, book_id),
        )
        updated_book = cursor.fetchone()
        if updated_book is None:
            raise HTTPException(status_code = 404, detail= "Book not found")
        return Book_Description(**updated_book)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException (status_code=500, detail=f"Could not update description: {str(e)}")


"""
The seach_book_media_type function is going to be used to search for the books by their media type. 
The function is going to check to see if the media_type parameter is empty or not. If the media_type
parameter is empty, then there is going to be an HTTPException raised with a status code of 400
with the message of 'Media type is required'. If the media_type parameter is not empty, then the
function is going to check to see if there's a space in the media_type parameter. 
If there is a space in the media_type parameter, then there's going to be an HTTPException
raised with a status code of 400 and the message of 'Please provide only one word to seach by media type'.
The function is going to make a connection tp the database and initializes the cursor. 
The query is going to be initialized with the value of the select command that is going to be used to search for the books by their media type.
The search patten is going to be a string that is going to be used to search for the media type in the database. The % symbols
are going t obe used to indicate that the search patten can be anywhere in the media type string. The cursor is going to execute the 
query with the search patten as the parameter. The results are going to be fetched and returned as a dictionary with the query and books as the keys.
In the except block, if there's an error, then it's going to raise an HTTPException with a status code of 500 and the message of 'Search by media type failed: {str(e)}'.
In the finally block, if the connection is not None, then the connection is going to be closed. 
"""
@library_app.get("/books/search/media_type")
def search_books_by_media_type(media_type: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not media_type or not media_type.strip():
        raise HTTPException(status_code=400, detail="Media type is required")
    media_type = media_type.strip()
    if " " in media_type:
        raise HTTPException(status_code=400, detail="Please provide only one word to search by media type")

    try:
        query = """
            SELECT DISTINCT b.*, mt.media_type_name AS media_type
            FROM book_info AS b
            JOIN book_media_type AS bmt ON bmt.book_id = b.book_id
            JOIN media_type AS mt ON mt.media_type_id = bmt.media_type_id
            WHERE mt.media_type_name ILIKE %s
            ORDER BY b.book_title;
        """
        # the search patten is going to be a string that is going to be 
        # used to serach for the media type in the database. The % symbols 
        # are going to be used to indicate that the search patten can be anywwhere
        # in the media type string. The % symbols are going to be used to indicate 
        # that the search patten can be anywhere in the media type string.
        search_patten = f"%{media_type}%"
        cursor.execute(query, (search_patten,))
        results = cursor.fetchall()

        return {"query": media_type, "books": results}
    except Exception as e:
        # This except block is going to be similar to the other search functions, 
        # but the difference is that this one is going to be searching by media type. 
        # The exception is going to be raised if there is an error with the search by media type.
        raise HTTPException(status_code=500, detail=f"Search by media type failed: {str(e)}")


"""
This function is going to search in the book database and it'll specifically search for books by their genre. 
The function is going to check to see if the genre parameter is empty or not. If the genre parameter is empty, then
it'll return a HTTPException with a status code of 400 and the message of 'Book genre is required'. 
If the genre parameter is not empty, then the function is going to check to see if there's a space in the genre parameter.
The next portion of the function is going to behave similarly to the other search functions. The try block is going to 
attempt to make a connection to the database and initialize the cursor using the RealDictCursor.
The query is then going to be store the responses of the 
SELECT DISTINCT b.*, g.genre_name AS genre FROM book_info AS b JOIN book_genre AS bg ON bg.book_id = b.book_id JOIN genre AS g ON 
g.genre_id = bg.genre_id WHERE g.genre_name ILIKE %s ORDER BY b.book_title; command.
The search patten then is going to be initialized with the value of f"%{book_genre}%" 
and the cursor is going to execute the query with the search patten as a parameter.
The results are then going to be fetched and returned as a dictionary with the query and books as
the keys. In the except block, if there's an error, it's going to then raise an HTTPException with 
a status code of 500 and the message of 'Search by book genre failed: {str(e)}'. 
In the finally block, if the connection is not None, then the connection is going to be closed.
"""
@library_app.get("/books/search/book_genre")
def search_books_by_book_genre(genre: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not genre or not genre.strip():
        raise HTTPException(status_code=400, detail="Book genre is required")
    book_genre = genre.strip()
    if " " in book_genre:
        raise HTTPException(status_code=400, detail="Please provide only one word to search by book genre")
    try:
        query = """
            SELECT DISTINCT b.*, g.genre_name AS genre
            FROM book_info AS b
            JOIN book_genre AS bg ON bg.book_id = b.book_id
            JOIN genre AS g ON g.genre_id = bg.genre_id
            WHERE g.genre_name ILIKE %s
            ORDER BY b.book_title;
        """
        search_patten = f"%{book_genre}%"
        cursor.execute(query, (search_patten,))
        results = cursor.fetchall()

        return {"query": book_genre, "books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by book genre failed: {str(e)}")


"""
This function is going to be used to search for books by author.
The function is going to check to see if the author parameter is empty or not. If
the author parameter is empty, then there is going to be an HTTPException raised 
with a status code of 400 with the message of 'Author name is required'.
If the other paramter is satisfied, then the function is going to check to see if
there's a space in the author parameter. If there is a space in the author parameter, 
then there is going to be an HTTPException raised with a 
status code of 400 with the message of 'Please provide only one word to search 
by author name'. 
"""
@library_app.get("/books/search/author")
def search_books_by_author(author: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not author or not author.strip():
        raise HTTPException(status_code=400, detail="Author name is required")
    author_name = author.strip()
    if " " in author_name:
        raise HTTPException(status_code=400, detail="Please provide only one word to search by author name")
    try:
        query = """
            SELECT DISTINCT
                b.*,
                CONCAT_WS(' ', a.first_name, a.last_name) AS author
            FROM book_info AS b
            JOIN book_author AS ba ON ba.book_id = b.book_id
            JOIN author_info AS a ON a.author_id = ba.author_id
            WHERE CONCAT_WS(' ', a.first_name, a.last_name) ILIKE %s
            ORDER BY b.book_title;
        """
        search_patten = f"%{author_name}%"
        cursor.execute(query, (search_patten,))
        results = cursor.fetchall()

        return {"query": author_name, "books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by author failed: {str(e)}")

"""
This function is going to retrieve a commic book from the database. The
parameter is going to declare a required string query paramter defined as 
comic that the client must pass in the URL The ... (ellipsis) specifies that 
the paramter is mandatory. The second cursor where cursor: RealDictCusor = Depends(get_db_cursor)
is going to use the FastAPI's Depends to inject a database cursor. The RealDictCursor
is going to ensure that the database rwos are returned as Python dictionaries where
columns map to keys, rather than tuples.
"""
@library_app.get("/comics/search")
def get_comic_book_from_database(comic: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not comic or not comic.strip():
        raise HTTPException(status_code=400, detail="Comic book title is required")
    comic_book = comic.strip()
    if " " in comic_book:
        raise HTTPException(status_code=400, detail="Please provide only one word to search by comic book title")
    try:
        query = """
            SELECT DISTINCT b.*, g.genre_name AS genre, mt.media_type_name AS media_type
            FROM book_info AS b
            LEFT JOIN book_genre AS bg ON bg.book_id = b.book_id
            LEFT JOIN genre AS g ON g.genre_id = bg.genre_id
            LEFT JOIN book_media_type AS bmt ON bmt.book_id = b.book_id
            LEFT JOIN media_type AS mt ON mt.media_type_id = bmt.media_type_id
            WHERE b.book_title ILIKE %s
            ORDER BY b.book_title;
        """
        search_patten = f"%{comic_book}%"
        cursor.execute(query, (search_patten,))
        comic_book_results = cursor.fetchall()
        return {"comic_books": comic_book_results}
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        raise HTTPException(status_code=500, detail=str(error))


"""What this function does is that it's going to search for the minimum and the
max number of pages that the user is looking for. The Query parameter is used as a
FastAPI helper that is going to define and validate the query-string parameter in the URL.
The first if-statement in the function is going to check to see if the minimum
pages are null and it will also check to see if the maximum number of pages 
are also null. If that is the case, then it's going to raise an HTTPException
and it the status code is going to be a 400 error code with the message indicating 
to the user that they will have to provide a minimum or a maximum number of pages, or 
both a min and a max number of pages. The second if statment is going to be using 
similar checking process to that of the prior conditional statement, however, it's 
going to be also checking to see if the minimum number of pages is greater than the 
maximum number of pages. If that is the case, then it's going to raise an HTTPException
error with the status code of 400 and the detail message behind the code indicating
'min_pages cannot be greater than max_pages'. After the conditions were checked and satisfied,
we are going to intialize our connection and attempt to make a connection to the 
dataabase. Within our try block, after the connection was formed, the cursor
is going to make a connnection using our connection. We're also going to be performing 
a query where it's going to be selecting information from our book_info table where
the page amount is not null and it's also going to be finding the page amount where
the page amount is going to be null or greater than or less than the value. Then it's 
going to be order the resutls by the page amount and book_title."""
@library_app.get("/books/search/pages")
def search_books_by_pages(
    min_pages: int | None = Query(default=None, ge=0),
    max_pages: int | None = Query(default=None, ge=0),
    cursor: RealDictCursor = Depends(get_db_cursor)
):
    if min_pages is None and max_pages is None:
        raise HTTPException(
            status_code=400,
            detail="Provide min_pages, max_pages, or both"
        )

    if min_pages is not None and max_pages is not None and min_pages > max_pages:
        raise HTTPException(
            status_code=400,
            detail="min_pages cannot be greater than max_pages"
        )

    try:
        query = """
            SELECT *
            FROM book_info
            WHERE page_amount IS NOT NULL
              AND (%s IS NULL OR page_amount >= %s)
              AND (%s IS NULL OR page_amount <= %s)
            ORDER BY page_amount, book_title;
        """

        cursor.execute(
            query,
            (min_pages, min_pages, max_pages, max_pages)
        )

        books = cursor.fetchall()

        return {
            "query": {
                "min_pages": min_pages,
                "max_pages": max_pages
            },
            "books": books
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search by page count failed: {str(e)}"
        )


"""The following function will get a single book from the database. What's unique
about the parameter for this function is that the book_id is recognized as an integer.
The function fetches a single book by ID and validates that the record exists."""
@library_app.get("/books/{book_id}")
def get_book_details(book_id: int, cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute(
            """
            SELECT b.*, ba.author_id
            FROM book_info AS b
            LEFT JOIN LATERAL (
                SELECT author_id
                FROM book_author
                WHERE book_id = b.book_id
                ORDER BY author_id
                LIMIT 1
            ) AS ba ON TRUE
            WHERE b.book_id = %s;
            """,
            (book_id,),
        )
        book = cursor.fetchone()

        if book is None:
            raise HTTPException(status_code=404, detail="Book not found")
        return book
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""This function (get_book_database) will make a connection to the database and have an array for the book records be initialized.
This array is going to allow for the book data to be return safely. The try block is going to be similar to that of the other functions
in this file, but the difference is that after the declaration/initialization of the cursor, the cursor is going to execute the 
SELECT * FROM book_info PostgreSQL command. This is going to retrieve all of the information that we currently of the books in our database"""
def get_book_database():
    """Fetch and print all the rows from the book information as a record set (list 
    of dictionaries)"""
    connection = db_manager.get_conn()
    book_records = [] #this will allow for the book data to be returned safely
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM book_info;")
        book_records = cursor.fetchall()

        print(f"Found {len(book_records)} books: \n")
        # Get book titles
        for row in book_records:
            print(row["book_title"])

        cursor.close()
        return book_records #this return statement will allow for the FastAPI to access the data
    
    except(Exception, psycopg2.DatabaseError) as error:
        """This except block is has a different error than what we may typically use.
        However, with this function retrieving all of the information from one specific table.
        This error exception is raise for errors that are related to the database speicifically
        """
        print(error)
        raise error
    finally:
        db_manager.release_conn(connection)

"""
This function is going to allow the users to add multiple authors to the database. The db_manager is going to get the 
connection and it's going to be stored in the connnection variable. The the connection.cursor is going to then be 
used to create a PostgreSQL cursor whose query is going to behave like a dictionary. The RealDictCursor comes from psycopg2.extras
and it's useful for returning database rows through the FastAPI.
"""
def add_multiple_authors():
    connection = db_manager.get_conn()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    """The try block is going to have the cursor execute the select command where
    it's going to select the author_id, first_name and last_name from the author info
    table in the database. It's also going to order the results of the database by the last
    name, first name, and the authors id values. The cursor.fetchall() is going retrieve the remaining rows 
    returned by the cursor.execute command, the information is then going to be stored into the authors 
    variable. In the for-in block, we're going to be performing the command because we are wanting to
    print out the dictionary 'author' values that are authors dictionary. Outside of the 
    for-in loop, we're going to return the authors. In the finally block, we're going
    close the cursor and we're going to also release the connection to the database
    as well."""
    try:
        cursor.execute(
            """
            SELECT author_id, first_name, last_name
            FROM author_info
            ORDER BY last_name, first_name, author_id;
            """
        )
        authors = cursor.fetchall()
        for author in authors:
            print(f"{author['first_name']} {author['last_name']}")
        return authors
    finally:
        cursor.close()
        db_manager.release_conn(connection)

def search_all_games():
    connection = db_manager.get_conn()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT *
            FROM game_info
            ORDER BY game_title;
            """
        )
        games = cursor.fetchall()
        for game in games:
            print(f"{game['game_title']}")
        return games
    finally:
        cursor.close()
        db_manager.release_conn(connection)


@library_app.get("/games")
def get_all_games():
    try:
        return {"games": search_all_games()}
    except Exception as error:
        logging.exception("Database error in get_all_games")
        raise HTTPException(status_code=500, detail="Could not retrieve games") from error
        
"""In the main() function, we're going to print out a test to ensure that the file
is working as it should be, after the print statement, we're going to try 
and get the book database. In the exception block, if we aren't able to get 
our database, then the file is going to print out a message consisting of 
'Main execution waning: local databaase check failed'. After the except block, 
the database manager is going to be set up a database connection pool to manage
multiple database connections efficiently. The uvicorn.run is going to be used 
as a way to initialize the app with a host, port, and a reload be initialized."""
def main():
    print("Hello from digital-library-system!")
    try:
        get_book_database()
    except Exception as e:
        print(f"Main execution waning: Local database check failed ({e})")
    db_manager.initialize_pool()
    uvicorn.run("main:library_app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()

"""
@pytest.fixture(autouse=True)
def setup_test_env():
    #This will tell the app to use the test paramters rather than production paramters
    os.environ["TESTING"] = "True"
    os.environ.setdefault("DB_USER", "postgres")
    os.environ.setdefault("DB_PASSWORD", "password")
    os.environ.setdefault("DB_HOST", "localhost")
    yield
    os.environ["TESTING"] = "False"
"""

import os
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from datetime import date
from fastapi.encoders import jsonable_encoder
import uvicorn

# def config(filename='database.ini', section='postgresql'):
#     parser = ConfigParser()
#     parser.read(filename)

#     database = {}
#     if parser.has_section(section):
#         params = parser.items(section)
#         for param in params:
#             database[param[0]] = param[1]
#     else:
#         raise Exception(f'Section {section} not found in the {filename} file')
#     return database

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

library_app = FastAPI()

load_dotenv()
"""The get_env function is going to be used to get the environment variables
that are needed to connect to the database. This function is also going to be used 
to get the environemnet variables thta are needed to connnect to the database.
The function is going to check if the environment variable is set, if it's not set,
then it's going to raise a RunTimeError. If the environment variable is set, 
then it's going to return the value of the environment variable."""
def get_env(env_name):
    if os.environ.get("TESTING") == "True" and env_name == "DB_NAME":
        return "digital-library-system"

    env_value = os.environ.get(env_name)
    if env_value is not None:
        env_value = env_value.strip()

    if env_value is None and env_name == "DB_PORT":
        return "5440"

    if env_value in (None, ""):
        raise RuntimeError(f"Missing required environment variable: {env_name}")

    return env_value

def connect():
    """Connect to the PostgreSQL database server"""
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
    # if the connection is not None, then close the connection to the database
    finally:
        if connection is not None:
            connection.close()
            print('Database connection closed.')

@library_app.get("/books")
def get_book_endpoint():
    try:
        books = get_book_database()
        return {"books" : books}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@library_app.get("/books/summaries")
def get_book_summaries_from_database():
    connection = None
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
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT book_id, book_title FROM book_info;")
        details_query = cursor.fetchall()
        cursor.close()
        return {"books": details_query}
    except Exception as e:
        raise HTTPException(status_code = 500, detail= "Could not find book details")
    finally:
        if connection is not None:
            connection.close()

@library_app.get("/books/info")
def get_details_from_database():
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM book_info;")
        info_query = cursor.fetchall()
        cursor.close()
        return {"books":info_query}
    except Exception as e:
        raise HTTPException(status_code = 500, detail = "Could not find info")
    finally:
        if connection is not None:
            connection.close()

class Book(BaseModel):
    book_isbn: str
    book_title: str
    author_id: int | None = None
    publish_date: date | None = None 

@library_app.post("/books", status_code=status.HTTP_201_CREATED)
def user_add_book(book: Book):
    connection = None
    """The first except block is going to be used to catch the psycopg2.errors.UniqueViolation error.
    This error is going to be raised if the user tries to add a book with an ISBN that already exists in the database. 
    The second except block is going to be used to catch the psy. The third 
    except block is going to be used to catch any other exceptions that may occur.
    The finally block is going to be used to close the connection to the database if it is not None. 
    This is going to ensure that the connection to the database is closed even if an error occurs.
    This is going to prevent any potential memory leaks or other issues that may arise from leaving the connection open."""
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user = get_env("DB_USER"),
            password = get_env("DB_PASSWORD"),
            host = get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        query = """
        insert into book_info(book_isbn, book_title, author_id, publish_date)
        values (%s, %s, %s, %s) 
        RETURNING *
        """
        cursor.execute(
            query, (book.book_isbn, book.book_title, book.author_id, book.publish_date)
        )
        new_book = cursor.fetchone()
        connection.commit()

        return {"message": "Book added successfully", "book": new_book}
    except psycopg2.errors.UniqueViolation:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code = 409,
            detail="A book with this ISBN already exists."
        )
    except psycopg2.errors.ForeignKeyViolation:
        if connection is not None:
            connection.rollback()
        raise HTTPException(
            status_code = 400,
            detail = "Invalid author_id. The author does not exist."
        )
    except Exception as e:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=500, detail=f"Could not add book: {str(e)}")

    finally:
        if connection is not None:
            connection.close()

@library_app.get("/")
def read_root():
    return {"message": "Hello World"}

"""This function (get_book_database) will make a connection to the database and have an array for the book records be initialized.
This array is going to allow for the book data to be return safely. The try block is going to be similar to that of the other functions
in this file, but the difference is that after the declaration/initialization of the cursor, the cursor is going to execute the 
SELECT * FROM book_info PostgreSQL command. This is going to retrieve all of the information that we currently of the books in our database"""
def get_book_database():
    """Fetch and print all the rows from the book infor as a record set (list 
    of dictionaries)"""
    connection = None
    book_records = [] #this will allow for the book data to be returned safely
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
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
        if connection is not None:
            connection.close()
"""The intention behind the search_title_by_word function is to allow for the user to search for a book by a specific word in the title. 
The function is going to check if the title parameter is empty or not. If the title parameter is empty, there is going to be an HTTPException
raised with a status code of 400 with the message of 'Title is required'. If the title paramter is not empty, then the function is going to check if there is a space in the title parameter. 
If there is a space in the title parameter, then there is going to be an HTTPException raised with a status code of 400 with the message of 'Please provide only one word to search'.
The function is going to make a connection to the database and initialize the cursor. 
The cursor is going to execute the SELECT * FROM book_info WHERE book_title ILIKE %s ORDER BY book_title; command. 
The % symbols are going to be used to indicate that the search pattern can be 
anywhere in the book_title string. The cursor is going to fetch all of the results and return them as a dictionary with the query and books as the keys.
"""
@library_app.get("/books/search")
def search_title_by_word(title: str):
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    title = title.strip()
    if " " in title:
        raise HTTPException(status_code=400, detail="Please provide only one word to search")

    connection = None
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        query = """ 
                SELECT * 
                FROM book_info 
                WHERE book_title ILIKE %s 
                ORDER BY book_title;
        """
        search_pattern = f"%{title}%"
        cursor.execute(query, (search_pattern,))
        results = cursor.fetchall()
        return {"query": title, "books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    finally:
        if connection is not None:
            connection.close()

"""The following function will get a single book from the database. What's unique
about the paramter for this function is that the book_id is going to be recognized
as an integer. This function will fetch a single book by ID, validate
that a specific record with the ID exists. It will also support 
updating and deleting a specific book. It'll also return a detailed record data."""
@library_app.get("/books/{book_id}")           
def get_single_book_endpoint(book_id: int):
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM book_info WHERE book_id = %s;", (book_id,))
        book = cursor.fetchone()
        cursor.close()

        if book is None:
            raise HTTPException(status_code=404, detail="Book not found")
        return book
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))
    finally:
        if connection is not None:
            connection.close()

@library_app.delete("/books/{book_id}")
def delete_book_endpoint(book_id: int):
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "DELETE FROM book_info WHERE book_id = %s RETURNING *;",
            (book_id,),
        )
        deleted_book = cursor.fetchone()

        if deleted_book is None:
            raise HTTPException(status_code=404, detail="Book not found")

        connection.commit()
        return {"message": "Book deleted successfully", "book": deleted_book}

    except HTTPException:
        raise
    except Exception as e:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete book: {str(e)}")
    finally:
        if connection is not None:
            connection.close()

class Book_Description(BaseModel):
    book_id: int
    book_title: str
    book_description: str | None = None

def create_dummy_book_table():
        return{
            1: {
                "book_id": 1,
                "book_title": "Hollow",
                "book_description": "A book about survival in a dangerous forest determined to survive.",
            },
            2: {
                "book_id": 2,
                "book_title": "Never Keep",
                "book_description": "A book involving magic, friendship, and enemies to lovers",
            },
        }

dummy_books = create_dummy_book_table()

class Book_Description_Update(BaseModel):
    book_description: str

@library_app.put("/books/{book_id}/description", response_model=Book_Description)
def description_change(book_id: int, summary: Book_Description_Update):
    book = dummy_books.get(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    book["book_description"] = summary.book_description
    return Book_Description(**book)

@library_app.get("/books/search/genre")
def search_books_by_genre(genre: str):
    if not genre or not genre.strip():
        raise HTTPException(status_code=400, detail="Genre is required")
    genre = genre.strip()
    if " " in genre:
        raise HTTPException(status_code=400, detail="Please provide only one word to search by genre")

    connection = None

    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        query = """ 
                SELECT * 
                FROM book_info 
                WHERE genre ILIKE %s 
                ORDER BY book_title;
        """
        search_pattern = f"%{genre}%"
        cursor.execute(query, (search_pattern,))
        results = cursor.fetchall()

        return {"query": genre, "books": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by genre failed: {str(e)}")
    finally:
        if connection is not None:
            connection.close()

@library_app.get("/books/search/media_type")
def search_books_by_media_type(media_type: str):
    if not media_type or not media_type.strip():
        raise HTTPException(status_code=400, detail="Media type is required")
    media_type = media_type.strip()
    if " " in media_type:
        raise HTTPException(status_code=400, detail="Please provide only one word to search by media type")

    connection = None

    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT"))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        query = """ 
                SELECT * 
                FROM book_info 
                WHERE media_type ILIKE %s 
                ORDER BY book_title;
        """
        # the search pattern is going to be a string that is going to be 
        # used to serach for the media type in the database. The % symbols 
        # are going to be used to indicate that the search pattern can be anywwhere
        # in the media type string. The % symbols are going to be used to indicate 
        # that the search pattern can be anywhere in the media type string.
        search_pattern = f"%{media_type}%"
        cursor.execute(query, (search_pattern,))
        results = cursor.fetchall()

        return {"query": media_type, "books": results}
    except Exception as e:
        # This except block is going to be similar to the other search functions, 
        # but the difference is that this one is going to be searching by media type. 
        # The exception is going to be raised if there is an error with the search by media type.
        raise HTTPException(status_code=500, detail=f"Search by media type failed: {str(e)}")
    finally:
        if connection is not None:
            connection.close()

def main():
    print("Hello from digital-library-system!")
    # connect()
    try:
        get_book_database()
    except Exception as e:
        print(f"Main execution warning: Local database check failed ({e})")
    read_root()

if __name__ == "__main__":
    uvicorn.run(library_app, host="0.0.0.0", port=8000)
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
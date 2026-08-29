import psycopg2, os 
#import pytest #adds pytest, os, and psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends #adds depends
from fastapi.responses import JSONResponse



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

def get_env(env_name):
    if os.environ.get("TESTING") == "True" and env_name == "DB_NAME":
        return "digital-library-system"
        
    env_value = os.environ.get(env_name)

    if env_value is not None:
        env_value = env_value.strip()

    print(f"env_value is {env_value}")

    if env_value is None and env_name == "DB_PORT":
        return "5440"
    
    if env_value is None:
        print(f"You must set environment variable ${env_name} to run the program")

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
def get_books_summaries_from_database():
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
        cursor.execute("SELECT book_id, book_title FROM book_info;")
        details_query = cursor.fetchall()
        cursor.close()
        return {"books": details_query}
    except Exception as e:
        raise HTTPException(status_code = 500, detail= "Could not find book details")
    finally:
        if connection is not None:
            connection.close()

@library_app.get("/book/info")
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

@library_app.get("/")
def read_root():
    return {"message": "Hello World"}

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
        print(error)
        raise error
    finally:
        if connection is not None:
            connection.close()

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

def main():
    print("Hello from digital-library-system!")
    # connect()
    try:
        get_book_database()
    except Exception as e:
        print(f"Main execution warning: Local database check failed ({e})")
    read_root()

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



# def test_get_books():
#     #Tests the database integration endpoint
#     client = TestClient(library_app)
#     response = client.get("/books")

#     #Assertions depend on test DB state, if the DB table exists, it will return 200
#     assert response.status_code in [200, 500]
#     if response.status_code == 200:
#         assert "books" in response.json()
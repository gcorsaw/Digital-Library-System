import psycopg2
import os
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()


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

def connect():
    """Connect to the PostgreSQL database server"""
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=os.environ.get("DB_NAME", "mydatabase"),
            user=os.environ.get("DB_USER", "gcorsaw"),
            password=os.environ.get("DB_PASSWORD", "DadR0cks"),
            host=os.environ.get("DB_HOST", "localhost"),
            port= int(os.environ.get("DB_PORT", 5440))
        )
        cursor = connection.cursor()
        print("PostgreSQL database version:")
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(version)

        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()
            print('Database connection closed.')

def get_book_database():
    """Fetch and print all the rows from the book infor as a record set (list 
    of dictionarys)"""
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=os.environ.get("DB_NAME", "mydatabase"),
            user=os.environ.get("DB_USER", "gcorsaw"),
            password=os.environ.get("DB_PASSWORD", "DadR0cks"),
            host=os.environ.get("DB_HOST", "localhost"),
            port= int(os.environ.get("DB_PORT", 5440))
        )
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM book_info;")
        records = cursor.fetchall()

        print(f"Found {len(records)} books: \n")
        for row in records:
            print(row)

        cursor.close()
    except(Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()

def main():
    print("Hello from digital-library-system!")
    connect()
    get_book_database()

if __name__ == "__main__":
    main()

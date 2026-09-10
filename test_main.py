import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "True"

from main import (
    add_multiple_authors,
    get_book_database,
    get_env,
    library_app,
    search_all_games,
)


@pytest.fixture
def client():
    with TestClient(library_app) as test_client:
        yield test_client


@pytest.fixture
def orwell_with_multiple_books():
    connection = psycopg2.connect(
        dbname=get_env("DB_NAME"),
        user=get_env("DB_USER"),
        password=get_env("DB_PASSWORD"),
        host=get_env("DB_HOST"),
        port=int(get_env("DB_PORT")),
    )
    cursor = connection.cursor()
    book_id = None

    try:
        cursor.execute(
            """
            SELECT author_id
            FROM author_info
            WHERE first_name = 'George' AND last_name = 'Orwell';
            """
        )
        author_row = cursor.fetchone()
        if author_row is None:
            pytest.skip("Test database does not contain George Orwell.")

        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'book_author'
              AND column_name = 'creator_role';
            """
        )
        legacy_role_schema = cursor.fetchone() is not None
        role_column = "creator_role" if legacy_role_schema else "creator_role_id"
        if legacy_role_schema:
            cursor.execute(f"SELECT {role_column} FROM book_author LIMIT 1;")
        else:
            cursor.execute(
                """
                SELECT creator_role_id
                FROM creator_role_type
                WHERE creator_role_name = 'Author';
                """
            )
        role_row = cursor.fetchone()
        if role_row is None:
            pytest.skip("Test database does not contain the Author role.")

        cursor.execute(
            """
            INSERT INTO book_info (book_isbn, book_title, publish_date)
            VALUES ('9780000000998', 'Test Orwell Book', '2026-01-01')
            RETURNING book_id;
            """
        )
        book_id = cursor.fetchone()[0]
        cursor.execute(
            f"""
            INSERT INTO book_author (book_id, author_id, {role_column})
            VALUES (%s, %s, %s);
            """,
            (book_id, author_row[0], role_row[0]),
        )
        connection.commit()
        yield
    finally:
        if book_id is not None:
            cursor.execute("DELETE FROM book_info WHERE book_id = %s;", (book_id,))
            connection.commit()
        cursor.close()
        connection.close()

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

# Tests to see if the root is found, if not then it'll return a 404 error.
def test_not_found(client):
    response = client.get("/not-found")
    assert response.status_code == 404

#Tests get the books from the database 
def test_get_books(client):
    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert "books" in data
    assert isinstance(data["books"], list)

#Tests to see if adding a book to the database is successful
def test_book_add_success(client):    
    # Pre-seed background relational tables to prevent foreign key errors
    connection = psycopg2.connect(
        dbname=get_env("DB_NAME"), user=get_env("DB_USER"),
        password=get_env("DB_PASSWORD"), host=get_env("DB_HOST"),
        port=int(get_env("DB_PORT"))
    )
    cursor = connection.cursor()
    cursor.execute("SELECT author_id FROM author_info WHERE first_name = 'Test' AND last_name = 'Author' LIMIT 1;")
    author_row = cursor.fetchone()
    added_id = None
    if author_row is None:
        cursor.execute(
            "INSERT INTO author_info (first_name, last_name) VALUES ('Test', 'Author') RETURNING author_id;"
        )
        author_row = cursor.fetchone()

    cursor.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'book_author' AND column_name = 'creator_role';"
    )
    legacy_role_schema = cursor.fetchone() is not None
    role_column = "creator_role" if legacy_role_schema else "creator_role_id"
    cursor.execute(f"SELECT {role_column} FROM book_author LIMIT 1;")
    role_row = cursor.fetchone()
    assert role_row is not None, "Test database needs an existing book_author role"
    connection.commit()

    payload = {
        "book_isbn": "9780000000001",
        "book_title": "New Test Book",
        "author_id": author_row[0],
        "creator_role_id": role_row[0],
        "publish_date": "2026-01-01",
    }

    try:
        response = client.post("/books", json=payload)

        assert response.status_code == 201
        add_info = response.json()
        assert add_info["message"] == "Book added successfully"
        assert add_info["book"]["book_title"] == "New Test Book"

        added_id = add_info["book"]["book_id"]
    finally:
        if added_id is not None:
            cursor.execute(
                "DELETE FROM book_info WHERE book_id = %s;",
                (added_id,),
            )
            connection.commit()

        cursor.close()
        connection.close()

#Tests to see if removing a book from the database is successful
def test_book_remove_success(client):   
    # Pre-seed background tables for this removal scenario as well
    connection = psycopg2.connect(
        dbname=get_env("DB_NAME"), user=get_env("DB_USER"),
        password=get_env("DB_PASSWORD"), host=get_env("DB_HOST"),
        port=int(get_env("DB_PORT"))
    )
    cursor = connection.cursor()
    cursor.execute("SELECT author_id FROM author_info WHERE first_name = 'Test' AND last_name = 'Author' LIMIT 1;")
    author_row = cursor.fetchone()
    if author_row is None:
        cursor.execute(
            "INSERT INTO author_info (first_name, last_name) VALUES ('Test', 'Author') RETURNING author_id;"
        )
        author_row = cursor.fetchone()

    cursor.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'book_author' AND column_name = 'creator_role';"
    )
    legacy_role_schema = cursor.fetchone() is not None
    role_column = "creator_role" if legacy_role_schema else "creator_role_id"
    cursor.execute(f"SELECT {role_column} FROM book_author LIMIT 1;")
    role_row = cursor.fetchone()
    assert role_row is not None, "Test database needs an existing book_author role"
    connection.commit()
    cursor.close()
    connection.close()

    payload = {
        "book_isbn": "9780000000002",
        "book_title": "New Test Book",
        "author_id": author_row[0],
        "creator_role_id": role_row[0],
        "publish_date": "2026-01-01",
    }
    create_response = client.post("/books", json=payload)
    assert create_response.status_code == 201
    created_book = create_response.json()["book"]
    book_id = created_book["book_id"]

    response = client.delete(f"/books/{book_id}")
    assert response.status_code == 200

    delete_info = response.json()
    assert delete_info["message"] == "Book deleted successfully"
    assert delete_info["book"]["book_id"] == book_id
    assert delete_info["book"]["book_title"] == "New Test Book"

def test_book_details_success(client):    
    # Query database records dynamically instead of guessing index /1
    books = get_book_database()
    if not books:
        pytest.skip("Test database contains zero populated rows.")
        
    target_id = books[0]["book_id"] if isinstance(books, list) else books["book_id"]
    response = client.get(f"/books/{target_id}")
    assert response.status_code == 200

    data = response.json()
    assert "book_title" in data
    assert data["book_id"] == target_id

def test_book_details_retuns_expected_fields(client):    
    # Fetch a true, live primary key directly from database pool results
    books = get_book_database()
    if not books:
        pytest.skip("Test database contains zero populated rows.")
        
    target_id = books[0]["book_id"] if isinstance(books, list) else books["book_id"]
    response = client.get(f"/books/{target_id}")
    assert response.status_code == 200

    book_data = response.json()
    assert "book_title" in book_data
    assert book_data["book_id"] == target_id


def test_search_details_invalid_id_type(client):
    response = client.get("/books/abc")
    assert response.status_code == 422
    assert "detail" in response.json()

def test_search_info_success(client):
    response = client.get("/books")
    assert response.status_code == 200
    search_info = response.json()
    assert "books" in search_info
    assert isinstance(search_info["books"], list)

def test_description_change_updates_book(client):  
    # Ensure a target row exists to safely test updating values
    books = get_book_database()
    if not books:
        pytest.skip("Test database contains zero populated rows.")
        
    first_book = books[0] if isinstance(books, list) else books
    target_id = first_book["book_id"]
    target_title = first_book["book_title"]
    
    response = client.put(
        f"/books/{target_id}/description",
        json={"book_description": "Updated test narrative description structure."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["book_id"] == target_id
    assert data["book_title"] == target_title
    assert data["book_description"] == "Updated test narrative description structure."

def test_description_change_retuns_404_for_missing_books(client):
    response = client.put(
        "/books/999999/description",
        json={"book_description": "Nope"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found"

def test_title_search(client):    
    # Find a valid name phrase from the test pool to guarantee search matches
    books = get_book_database()
    if not books:
        pytest.skip("Test database contains zero populated rows.")
        
    first_book = books[0] if isinstance(books, list) else books
    search_term = first_book["book_title"].split()[0]
    
    response = client.get(f"/books/search?title={search_term}")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == search_term

def test_title_search_no_results(client):
    response = client.get("/books/search?title=zzzznotrealword")
    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "zzzznotrealword"
    assert data["books"] == []

def test_title_search_missing_query(client):
    response = client.get("/books/search")

    #This assert will retun a 422 error if the title is missing as the query parameters require title
    assert response.status_code == 422

def test_media_type_search(client):
    response = client.get("/books/search/media_type?media_type=ebook")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "ebook"

def test_media_type_search_no_results(client):
    response = client.get("/books/search/media_type?media_type=notarealmediatype")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "notarealmediatype"

def test_book_genre_search(client):
    response = client.get("/books/search/book_genre?genre=fiction")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "fiction"

def test_book_genre_search_no_results(client):
    response = client.get("/books/search/book_genre?genre=notarealgenre")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "notarealgenre"

def test_author_search(client):
    response = client.get("/books/search/author?author=orwell")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)

def test_author_search_no_results(client):
    response = client.get("/books/search/author?author=notarealauthor")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "notarealauthor"

def test_get_book_summaries(client):
    response = client.get("/books/summaries")
    assert response.status_code == 200
    data = response.json()
    assert "books" in data
    assert isinstance(data["books"], list)

    if data["books"]:
        assert isinstance(data["books"][0], dict)

def test_get_authors(client, orwell_with_multiple_books):
    response = client.get("/books/search/author?author=orwell")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "orwell"
    assert isinstance(data["books"], list)
    assert len(data["books"]) >= 2

def test_author_can_have_multiple_books(orwell_with_multiple_books):
    connection = psycopg2.connect(
        dbname=get_env("DB_NAME"),
        user=get_env("DB_USER"),
        password=get_env("DB_PASSWORD"),
        host=get_env("DB_HOST"),
        port=int(get_env("DB_PORT")),
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT a.author_id, COUNT(DISTINCT ba.book_id)
                FROM author_info AS a
                JOIN book_author AS ba ON ba.author_id = a.author_id
                WHERE a.first_name = 'George'
                  AND a.last_name = 'Orwell'
                GROUP BY a.author_id;
            """)

            result = cursor.fetchone()

        assert result is not None
        author_id, book_count = result
        assert author_id is not None
        assert book_count >= 2
    finally:
        connection.close()

def test_add_multiple_authors_returns_expected_fields():
    authors = add_multiple_authors()

    assert isinstance(authors, list)
    assert authors

    for author in authors:
        assert "author_id" in author
        assert "first_name" in author
        assert "last_name" in author

def test_search_all_games():
    games = search_all_games()
    assert isinstance(games, list)
    assert games

    for game in games:
        assert "game_title" in game
        assert "min_players" in game
        assert "max_players" in game

def test_get_games(client):
    response = client.get("/games")

    assert response.status_code == 200
    data = response.json()
    
    assert "games" in data
    assert isinstance(data["games"], list)

def test_add_game(client):
    game_title = f"Test Game {uuid4()}"
    payload = {
        "game_title": game_title,
        "publisher": "Test Publisher",
        "release_date": "2026-01-01",
        "min_players": 2,
        "max_players": 4,
        "play_time_minutes": 45,
        "min_age": 8,
        "game_description": "A test game.",
    }

    try:
        response = client.post("/games", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Game added successfully"
        assert data["game"]["game_title"] == game_title
    finally:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT")),
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM game_info WHERE game_title = %s;",
                    (game_title,),
                )
            connection.commit()
        finally:
            connection.close()
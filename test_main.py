from fastapi.testclient import TestClient #adds TestClient for testing
from main import library_app, get_book_database

def test_read_root():
    #Tests the root node without needing connection to the database
    client = TestClient(library_app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

def test_not_found():
    client = TestClient(library_app)
    response = client.get("/not-found")
    assert response.status_code == 404

def test_get_books():
    client = TestClient(library_app)
    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert "books" in data
    assert isinstance(data["books"], list)

def test_book_add_success():
    client = TestClient(library_app)
    payload = {
        "book_isbn": "9780000000001",
        "book_title": "New Test Book",
        "author_id": 1,
        "publish_date": "2026-01-01"
    }

    response = client.post("/books", json=payload)
    assert response.status_code == 201
    add_info = response.json()
    assert add_info["message"] == "Book added successfully"
    assert add_info["book"]["book_title"] == "New Test Book"

    added_id = add_info["book"]["book_id"]
    import psycopg2
    import main
    connection = psycopg2.connect(
        dbname=main.get_env("DB_NAME"), user=main.get_env("DB_USER"),
        password=main.get_env("DB_PASSWORD"), host=main.get_env("DB_HOST"),
        port=int(main.get_env("DB_PORT"))
    )
    connection.cursor().execute("DELETE FROM book_info WHERE book_id = %s;", (added_id,))
    connection.commit()
    connection.close()
def test_book_remove_success():
    client = TestClient(library_app)
    payload = {
        "book_isbn": "9780000000001",
        "book_title": "New Test Book",
        "author_id": 1,
        "publish_date": "2026-01-01"
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

def test_book_details_success():
    client = TestClient(library_app)
    response = client.get("/books/1")
    assert response.status_code == 200

    data = response.json()
    assert "book_title" in data
    assert "author_id" in data
    assert data["book_id"] == 1

def test_book_details_returns_expected_fields():
    client = TestClient(library_app)
    response = client.get("/books/2")
    assert response.status_code == 200

    book_data = response.json()
    assert "book_title" in book_data
    assert "author_id" in book_data
    assert book_data["book_id"] == 2


def test_search_details_invalid_id_type():
    client = TestClient(library_app)
    response = client.get("/book/abc")
    assert response.status_code == 404
    assert "detail" in response.json()

def test_search_info_success():
    client = TestClient(library_app)
    response = client.get("/books")
    assert response.status_code == 200
    search_info = response.json()
    assert "books" in search_info
    assert isinstance(search_info["books"], list)

def test_description_change_updates_dummy_book():
    client = TestClient(library_app)

    client.post("/books/dummy")
    response = client.put(
        "/books/1/description",
        json={"book_description": "Updated description for Hollow."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["book_id"] == 1
    assert data["book_title"] == "Hollow"
    assert data["book_description"] == "Updated description for Hollow."

def test_description_change_returns_404_for_missing_books():
    client = TestClient(library_app)

    response = client.put(
        "/books/999/description",
        json={"book_description": "Nope"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found"

def test_title_search():
    client = TestClient(library_app)
    response = client.get("/books/search?title=king")

    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "king"

def test_title_search_no_results():
    client = TestClient(library_app)
    response = client.get("/books/search?title=zzzznotrealword")
    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "zzzznotrealword"
    assert data["books"] == []

def test_title_search_missing_query():
    client = TestClient(library_app)
    response = client.get("/books/search")

    #This assert will return a 422 error if the title is missing as the query parameters require title
    assert response.status_code == 422

def test_media_type_search():
    client = TestClient(library_app)
    response = client.get("/books/search/media_type?media_type=ebook")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "ebook"

def test_media_type_search_no_results():
    client = TestClient(library_app)
    response = client.get("/books/search/media_type?media_type=notarealmediatype")
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert data["query"] == "notarealmediatype"
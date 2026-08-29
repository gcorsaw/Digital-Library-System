from fastapi.testclient import TestClient #adds TestClient for testing
from main import library_app, get_book_database

def test_book_details_success():
    client = TestClient(library_app)
    response = client.get("/books/1")
    assert response.status_code == 200

    data = response.json()
    assert "book_title" in data
    assert "author_id" in data
    assert data["book_id"] == 1

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

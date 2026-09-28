"""
Tests for the Digital Library API.

These run against a SEPARATE database (default name: digital_library_test) so
they can never touch your real data. Create it once:

    createdb digital_library_test        # or: CREATE DATABASE digital_library_test;

then run:  pytest -v
(DB_USER / DB_PASSWORD / DB_HOST / DB_PORT come from your .env as usual;
set TEST_DB_NAME to use a different test database name.)

Every run rebuilds the schema from digital-library-system.sql, and every test
starts with empty user/book/game tables.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Must happen BEFORE importing main, so the app connects to the test database.
os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "digital_library_test")
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-that-is-32-chars-or-more"

from jose import jwt
import psycopg2
import pytest
from fastapi.testclient import TestClient

from main import (
    Book,
    Game,
    add_multiple_authors,
    db_manager,
    get_book_database,
    get_env,
    library_app,
    search_all_games,
)

SCHEMA_FILE = Path(__file__).with_name("digital-library-system.sql")
PASSWORD = "correct horse battery"


def db_connect():
    return psycopg2.connect(
        dbname=get_env("DB_NAME"), user=get_env("DB_USER"), password=get_env("DB_PASSWORD"),
        host=get_env("DB_HOST"), port=int(get_env("DB_PORT")),
    )


def db_run(sql, params=None, fetch=False):
    conn = db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    finally:
        conn.close()


@pytest.fixture(scope="session")
def fresh_schema():
    # The schema file DROPs tables, so refuse to run against anything that isn't a test DB.
    assert os.environ["DB_NAME"].endswith("_test"), "Test database name must end with _test"
    conn = db_connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SCHEMA_FILE.read_text())
    conn.close()


@pytest.fixture(scope="session")
def client(fresh_schema):
    with TestClient(library_app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def empty_tables(fresh_schema):
    # Keeps lookup data (author roles, media types); clears everything else. CASCADE clears tracking tables.
    db_run("TRUNCATE reader_info, book_info, game_info, author_info RESTART IDENTITY CASCADE;")


def make_user(client, name=None):
    name = name or f"user_{uuid4().hex[:8]}"
    resp = client.post(
        "/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def add_book(client, headers, title="Test Book", isbn="9780000000001"):
    resp = client.post("/books", json={"book_title": title, "book_isbn": isbn}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["book"]["book_id"]


# ---------------------------------------------------------------- accounts
def test_read_root(client):
    assert client.get("/").json() == {"message": "Hello World"}


def test_register_returns_working_token(client):
    resp = client.post("/auth/register", json={"username": "grace", "email": "g@example.com", "password": PASSWORD})
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["username"] == "grace"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "grace"


def test_password_is_hashed_not_stored(client):
    make_user(client, "hashcheck")
    stored = db_run("SELECT password_hash FROM reader_info WHERE username = 'hashcheck';", fetch=True)[0][0]
    assert stored.startswith("$argon2")
    assert PASSWORD not in stored


def test_duplicate_username_or_email_rejected_case_insensitively(client):
    make_user(client, "Grace")
    same_name = client.post("/auth/register", json={"username": "GRACE", "email": "other@example.com", "password": PASSWORD})
    same_email = client.post("/auth/register", json={"username": "someone", "email": "GRACE@example.com", "password": PASSWORD})
    assert same_name.status_code == 409
    assert same_email.status_code == 409


@pytest.mark.parametrize("payload", [
    {"username": "ab", "email": "a@example.com", "password": PASSWORD},        # username too short
    {"username": "has space", "email": "a@example.com", "password": PASSWORD},  # bad characters
    {"username": "valid_name", "email": "not-an-email", "password": PASSWORD},
    {"username": "valid_name", "email": "a@example.com", "password": "short"},
])
def test_register_validation(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 422


def test_login_by_username_or_email(client):
    make_user(client, "grace")
    for identifier in ("grace", "GRACE@example.com"):
        resp = client.post("/auth/login", json={"username": identifier, "password": PASSWORD})
        assert resp.status_code == 200, identifier
        assert resp.json()["token_type"] == "bearer"


def test_login_failures_do_not_reveal_which_part_was_wrong(client):
    make_user(client, "grace")
    wrong_pw = client.post("/auth/login", json={"username": "grace", "password": "wrong-password"})
    no_user = client.post("/auth/login", json={"username": "nobody", "password": PASSWORD})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


@pytest.mark.parametrize("method,path,body", [
    ("get", "/books", None),
    ("get", "/games", None),
    ("get", "/books/search?title=a", None),
    ("post", "/books", {"book_title": "X", "book_isbn": "1"}),
    ("post", "/games", {"game_title": "X"}),
    ("put", "/books/1/description", {"book_description": "x"}),
    ("delete", "/books/1", None),
    ("get", "/auth/me", None),
])
def test_protected_routes_require_login(client, method, path, body):
    resp = getattr(client, method)(path, **({"json": body} if body else {}))
    assert resp.status_code == 401


def test_bad_and_expired_tokens_rejected(client):
    make_user(client, "grace")
    assert client.get("/books", headers={"Authorization": "Bearer garbage"}).status_code == 401
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        os.environ["JWT_SECRET_KEY"], algorithm="HS256",
    )
    assert client.get("/books", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "a-different-secret-that-is-also-32-chars-long", algorithm="HS256",
    )
    assert client.get("/books", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# --------------------------------------------------------- personal libraries
def test_new_account_starts_empty(client):
    headers = make_user(client)
    assert client.get("/books", headers=headers).json() == {"books": []}
    assert client.get("/games", headers=headers).json() == {"games": []}


def test_add_list_and_duplicate_book(client):
    headers = make_user(client)
    add_book(client, headers, "Dune", "9780000000010")
    books = client.get("/books", headers=headers).json()["books"]
    assert [b["book_title"] for b in books] == ["Dune"]
    again = client.post("/books", json={"book_title": "Dune", "book_isbn": "9780000000010"}, headers=headers)
    assert again.status_code == 409


def test_libraries_are_private_between_users(client):
    alice, bob = make_user(client, "alice"), make_user(client, "bob")
    alice_book = add_book(client, alice, "Alice's Book", "9780000000021")
    assert client.get("/books", headers=bob).json()["books"] == []
    assert client.get("/books/search?title=Alice", headers=bob).json()["books"] == []

    # Same ISBN added by both shares one catalog row but two separate library entries.
    assert client.post("/books", json={"book_title": "Alice's Book", "book_isbn": "9780000000021"}, headers=bob).status_code == 201
    assert db_run("SELECT count(*) FROM book_info;", fetch=True)[0][0] == 1
    assert client.delete(f"/books/{alice_book}", headers=alice).status_code == 200
    assert client.get("/books", headers=alice).json()["books"] == []
    assert len(client.get("/books", headers=bob).json()["books"]) == 1


def test_cannot_touch_another_users_book(client):
    alice, bob = make_user(client, "alice"), make_user(client, "bob")
    book_id = add_book(client, alice)
    assert client.put(f"/books/{book_id}/description", json={"book_description": "hijack"}, headers=bob).status_code == 404
    assert client.delete(f"/books/{book_id}/description", headers=bob).status_code == 404
    assert client.delete(f"/books/{book_id}", headers=bob).status_code == 404
    assert len(client.get("/books", headers=alice).json()["books"]) == 1


def test_description_edit_and_clear(client):
    headers = make_user(client)
    book_id = add_book(client, headers, "Notes Book")
    put = client.put(f"/books/{book_id}/description", json={"book_description": "Loved it."}, headers=headers)
    assert put.status_code == 200 and put.json()["book_description"] == "Loved it."
    cleared = client.delete(f"/books/{book_id}/description", headers=headers)
    assert cleared.status_code == 200 and cleared.json()["book_description"] is None
    too_long = client.put(f"/books/{book_id}/description", json={"book_description": "x" * 301}, headers=headers)
    assert too_long.status_code == 422


def test_missing_book_returns_404(client):
    headers = make_user(client)
    assert client.put("/books/999999/description", json={"book_description": "Nope"}, headers=headers).status_code == 404
    assert client.delete("/books/999999", headers=headers).status_code == 404


def test_title_search_only_searches_own_library(client):
    headers = make_user(client)
    add_book(client, headers, "The Hobbit", "9780000000031")
    add_book(client, headers, "Emma", "9780000000032")
    hit = client.get("/books/search?title=hobbit", headers=headers).json()
    assert hit["query"] == "hobbit" and [b["book_title"] for b in hit["books"]] == ["The Hobbit"]
    assert client.get("/books/search?title=zzzz", headers=headers).json()["books"] == []
    assert client.get("/books/search", headers=headers).status_code == 422


def test_games_add_list_duplicate_and_privacy(client):
    alice, bob = make_user(client, "alice"), make_user(client, "bob")
    payload = {"game_title": "Catan", "min_players": 3, "max_players": 4}
    assert client.post("/games", json=payload, headers=alice).status_code == 201
    assert client.post("/games", json=payload, headers=alice).status_code == 409
    assert [g["game_title"] for g in client.get("/games", headers=alice).json()["games"]] == ["Catan"]
    assert client.get("/games", headers=bob).json()["games"] == []
    assert client.post("/games", json=payload, headers=bob).status_code == 201
    assert db_run("SELECT count(*) FROM game_info;", fetch=True)[0][0] == 1


def test_book_with_author_is_found_by_author_search(client):
    headers = make_user(client)
    author_id = db_run("INSERT INTO author_info (first_name, last_name) VALUES ('George','Orwell') RETURNING author_id;", fetch=True)[0][0]
    role_id = db_run("SELECT creator_role_id FROM creator_role_type WHERE creator_role_name = 'Author';", fetch=True)[0][0]
    resp = client.post(
        "/books",
        json={"book_title": "1984", "book_isbn": "9780451524935", "author_id": author_id, "creator_role_id": role_id},
        headers=headers,
    )
    assert resp.status_code == 201
    found = client.get("/books/search/author?author=orwell").json()["books"]
    assert [b["book_title"] for b in found] == ["1984"]


# ------------------------------------------- shared-catalog endpoints (public)
@pytest.mark.parametrize("path", [
    "/books/search/media_type?media_type=ebook",
    "/books/search/book_genre?genre=fiction",
    "/books/search/author?author=nobody",
    "/books/search/pages?min_pages=1",
    "/comics/search?comic=batman",
    "/books/summaries",
    "/books/info",
])
def test_catalog_endpoints_work_on_empty_database(client, path):
    assert client.get(path).status_code == 200


def test_book_details_and_bad_ids(client):
    headers = make_user(client)
    book_id = add_book(client, headers)
    assert client.get(f"/books/{book_id}").json()["book_id"] == book_id
    assert client.get("/books/999999").status_code == 404
    assert client.get("/books/abc").status_code == 422
    assert client.get("/not-found").status_code == 404


def test_helper_functions_on_empty_database(client):
    assert get_book_database() == []
    assert add_multiple_authors() == []
    assert search_all_games() == []


# ------------------------------------------------------------ model validation
def test_book_model_cleans_input():
    book = Book(book_isbn=" ISBN-TEST ", book_title="  Test Book  ")
    assert book.book_isbn == "ISBN-TEST" and book.book_title == "Test Book"


def test_book_requires_isbn_or_internal_code():
    with pytest.raises(ValueError, match="Either book_isbn or internal_code is required"):
        Book(book_title="Test Book")


def test_game_model_cleans_input():
    game = Game(game_title="  Test Game  ", publisher="  Pub  ", game_description="  A game.  ", min_players=2, max_players=4)
    assert (game.game_title, game.publisher, game.game_description) == ("Test Game", "Pub", "A game.")


def test_game_rejects_invalid_player_range():
    with pytest.raises(ValueError, match="max_players cannot be less than min_players"):
        Game(game_title="Test Game", min_players=5, max_players=2)
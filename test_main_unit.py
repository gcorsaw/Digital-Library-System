"""
Unit testing for the main.py FastAPI application, focusing on the database interactions,
authentication, and the business logic for the endpoints. The tests use pytest and
unittest.mock to simulate database connections, HTTP requests, and other dependencies,
ensuring that the application behaves correctly under various scenarios, including
successful operations, error handling, and edge cases. The tests cover user registration,
login, book and game management, and the validation of input data, providing a comprehensive
suite to verify the functionality and robustness of the application.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

os.environ.setdefault("DB_NAME", "digital_library_unit_test")
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-that-is-long-enough-32")

import main

USER = {"user_id": 7, "username": "reader", "email": "reader@example.com"}
TOKEN_SECRET = "unit-test-secret-that-is-long-enough-32"


def test_get_env_strips_values_and_defaults_port(monkeypatch):
    """Verify environment values are trimmed and DB_PORT defaults when unset."""
    monkeypatch.setenv("DB_HOST", "  db.example  ")
    monkeypatch.delenv("DB_PORT", raising=False)

    assert main.get_env("DB_HOST") == "db.example"
    assert main.get_env("DB_PORT") == "5440"

@pytest.mark.parametrize("value", [None, "  "])
def test_get_env_rejects_missing_required_values(monkeypatch, value):
    """Verify missing or blank required environment settings raise an error."""
    if value is None:
        monkeypatch.delenv("DB_NAME", raising=False)
    else:
        monkeypatch.setenv("DB_NAME", value)

    with pytest.raises(RuntimeError, match="DB_NAME"):
        main.get_env("DB_NAME")

def test_database_manager_initializes_pool_once(monkeypatch):
    """Verify the connection pool initializes once and closes cleanly."""
    manager = main.DatabaseManager()
    pool = MagicMock()
    pool_factory = MagicMock(return_value=pool)
    monkeypatch.setattr(main, "SimpleConnectionPool", pool_factory)
    for name, value in {
        "DB_NAME": "library_test",
        "DB_USER": "tester",
        "DB_PASSWORD": "password",
        "DB_HOST": "localhost",
        "DB_PORT": "5544",
    }.items():
        monkeypatch.setenv(name, value)

    manager.initialize_pool()
    manager.initialize_pool()

    pool_factory.assert_called_once_with(
        minconn=1,
        maxconn=20,
        dbname="library_test",
        user="tester",
        password="password",
        host="localhost",
        port=5544,
    )
    manager._pool = pool
    manager.close_pool()
    pool.closeall.assert_called_once_with()
    assert manager._pool is None

def test_get_db_cursor_commits_and_releases_connection(monkeypatch):
    """Verify successful cursor work commits and releases its connection."""
    connection = MagicMock()
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    release = MagicMock()
    monkeypatch.setattr(main.db_manager, "release_conn", release)

    generator = main.get_db_cursor()
    cursor = next(generator)
    with pytest.raises(StopIteration):
        next(generator)

    connection.commit.assert_called_once_with()
    cursor.close.assert_called_once_with()
    release.assert_called_once_with(connection)

def test_get_db_cursor_rolls_back_and_releases_connection(monkeypatch):
    """Verify failed cursor work rolls back and still releases its connection."""
    connection = MagicMock()
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    monkeypatch.setattr(main.db_manager, "release_conn", MagicMock())
    generator = main.get_db_cursor()
    next(generator)

    with pytest.raises(ValueError, match="query failed"):
        generator.throw(ValueError("query failed"))

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    connection.cursor.return_value.close.assert_called_once_with()
    main.db_manager.release_conn.assert_called_once_with(connection)

def test_get_cognito_public_keys_fetches_and_caches(monkeypatch):
    """Verify Cognito signing keys are fetched once and cached."""
    keys = [{"kid": "key-1"}]
    response = MagicMock()
    response.json.return_value = {"keys": keys}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(main.requests, "get", request)
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")

    assert main.get_cognito_public_keys() == keys
    assert main.get_cognito_public_keys() == keys
    request.assert_called_once_with(
        "https://cognito-idp.us-west-2.amazonaws.com/pool-123/.well-known/jwks.json",
        timeout=5,
    )

def test_get_cognito_public_keys_skips_request_without_pool_id(monkeypatch):
    """Verify key lookup skips the network request without a pool ID."""
    request = MagicMock()
    monkeypatch.setattr(main.requests, "get", request)
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")

    with pytest.raises(RuntimeError, match="COGNITO_USER_POOL_ID"):
        main.get_cognito_public_keys()
    request.assert_not_called()

def test_create_access_token_contains_user_and_expiration(monkeypatch):
    """Verify a signed access token contains the user claims and configured expiry."""
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "15")

    token = main.create_access_token(7, "reader")
    payload = main.jwt.decode(token, TOKEN_SECRET, algorithms=["HS256"])

    assert payload["sub"] == "7"
    assert payload["username"] == "reader"
    assert datetime.now(timezone.utc).timestamp() < payload["exp"]
    assert payload["exp"] - payload["iat"] == 15 * 60

def test_get_jwt_secret_rejects_short_secrets(monkeypatch):
    """Verify JWT signing keys shorter than the minimum are rejected."""
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        main.get_jwt_secret()

def test_verify_cognito_or_jwt_accepts_native_token(monkeypatch):
    """Verify the token verifier accepts a valid native JWT."""
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    monkeypatch.setenv("USE_COGNITO", "true")
    token = main.create_access_token(7, "reader")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    result = asyncio.run(main.verify_cognito_or_jwt(credentials))

    assert result == {
        "identity_provider": "native_jwt",
        "user_id": 7,
        "username": "reader",
    }

def test_verify_cognito_or_jwt_requires_credentials():
    """Verify the token verifier rejects requests without credentials."""
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.verify_cognito_or_jwt(None))

    assert error.value.status_code == 401

# Use a valid signed token and a matching database row to verify that the user
# lookup returns the database record. The schema activation is mocked so this
# unit test does not create or change a PostgreSQL schema.
def test_get_current_user_returns_database_user(monkeypatch):
    """Verify a valid token resolves to its database user and activates the schema."""
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    token = main.create_access_token(7, "reader")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    cursor = MagicMock()
    cursor.fetchone.return_value = USER
    monkeypatch.setattr(main, "activate_user_schema", MagicMock())

    result = main.get_current_user(credentials, cursor)

    assert result == USER
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (7,)

# An invalid bearer token cannot be decoded as a valid JWT, so the request must
# fail with HTTP 401 rather than returning an authenticated user.
def test_get_current_user_rejects_invalid_token():
    """Verify an invalid bearer token is rejected with HTTP 401."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")

    with pytest.raises(HTTPException) as error:
        main.get_current_user(credentials, MagicMock())

    assert error.value.status_code == 401

def test_get_current_user_rejects_unknown_user(monkeypatch):
    """Verify a valid token for an absent account is rejected."""
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    token = main.create_access_token(7, "reader")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    with pytest.raises(HTTPException) as error:
        main.get_current_user(credentials, cursor)

    assert error.value.status_code == 401

def test_register_hashes_password_and_returns_token(monkeypatch):
    """Verify registration hashes the password and returns an access token."""
    cursor = MagicMock()
    cursor.fetchone.return_value = USER
    hasher = MagicMock()
    hasher.hash.return_value = "hashed"
    monkeypatch.setattr(main, "password_hasher", hasher)
    monkeypatch.setattr(main, "create_access_token", MagicMock(return_value="signed-token"))
    monkeypatch.setattr(main, "activate_user_schema", MagicMock())
    body = main.RegisterRequest(username=" reader ", email=" reader@example.com ", password="password123")

    result = main.register(body, cursor)

    assert result == {
        "access_token": "signed-token",
        "token_type": "bearer",
        "user": USER,
    }
    assert cursor.execute.call_args.args[1] == ("reader", "reader@example.com", "hashed")
    main.create_access_token.assert_called_once_with(7, "reader")

def test_login_verifies_password_and_returns_token(monkeypatch):
    """Verify valid login credentials return a token and public user data."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {**USER, "password_hash": "stored-hash"}
    verify = MagicMock(return_value=True)
    hasher = MagicMock()
    hasher.verify = verify
    monkeypatch.setattr(main, "password_hasher", hasher)
    monkeypatch.setattr(main, "create_access_token", MagicMock(return_value="signed-token"))
    body = main.LoginRequest(username=" reader@example.com ", password="password123")

    result = main.login(body, cursor)

    assert result["access_token"] == "signed-token"
    assert result["user"] == USER
    assert cursor.execute.call_args.args[1] == ("reader@example.com", "reader@example.com")
    verify.assert_called_once_with("stored-hash", "password123")


def test_login_uses_same_error_for_unknown_user_and_wrong_password(monkeypatch):
    """Verify unknown users and wrong passwords receive the same response."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    verify = MagicMock(return_value=False)
    hasher = MagicMock()
    hasher.verify = verify
    monkeypatch.setattr(main, "password_hasher", hasher)

    with pytest.raises(HTTPException) as error:
        main.login(main.LoginRequest(username="missing", password="password123"), cursor)

    assert error.value.status_code == 401
    verify.assert_called_once_with(main._DUMMY_HASH, "password123")


def test_book_model_normalizes_fields_and_checks_related_author_fields():
    """Verify book fields are normalized and related author fields are paired."""
    book = main.Book(
        book_isbn=" ISBN-1 ",
        internal_code=" shelf-1 ",
        book_title="  Example  ",
        author_id=2,
        creator_role_id=3,
    )

    assert (book.book_isbn, book.internal_code, book.book_title) == (
        "ISBN-1",
        "shelf-1",
        "Example",
    )
    with pytest.raises(ValueError, match="provided together"):
        main.Book(book_isbn="ISBN-1", book_title="Example", author_id=2)


def test_game_model_normalizes_and_checks_player_range():
    """Verify game text is normalized and player limits are consistent."""
    game = main.Game(
        game_title="  Game ",
        publisher=" Pub ",
        game_description=" Description ",
        min_players=2,
        max_players=4,
    )

    assert (game.game_title, game.publisher, game.game_description) == (
        "Game",
        "Pub",
        "Description",
    )
    with pytest.raises(ValueError, match="max_players"):
        main.Game(game_title="Game", min_players=4, max_players=2)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(" READ ", "read"), ("Want to Read", "want to read")],
)
def test_book_progress_normalizes_status(status, expected):
    """Verify supported read-status values are normalized."""
    assert main.BookProgressUpdate(read_status=status, rating=5).read_status == expected


def test_book_progress_rejects_invalid_status():
    """Verify unsupported read-status values are rejected."""
    with pytest.raises(ValueError, match="read_status must be exactly"):
        main.BookProgressUpdate(read_status="reading")


def test_read_root_and_health(monkeypatch):
    """Verify the root response and health payload."""
    monkeypatch.setenv("APP_ENV", "test")

    assert main.read_root() == {"message": "Hello World"}
    assert asyncio.run(main.health_check()) == {
        "status": "healthy",
        "environment": "test",
        "database_connected": True,
    }


def test_get_books_scopes_query_to_current_user():
    """Verify book listings are restricted to the authenticated user."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_id": 3}]

    assert main.get_books(USER, cursor) == {"books": [{"book_id": 3}]}
    assert cursor.execute.call_args.args[1] == (USER["user_id"],)

def test_get_books_translates_database_errors():
    """Verify book-listing database failures become HTTP 500 responses."""
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        main.get_books(USER, cursor)

    assert error.value.status_code == 500
    assert "database unavailable" in error.value.detail

def test_user_add_book_creates_book_and_library_entry():
    """Verify adding a new book creates its catalog and user-library records."""
    cursor = MagicMock()
    book_row = {"book_id": 11, "book_title": "Example"}
    cursor.fetchone.side_effect = [None, book_row, {"book_id": 11}]
    book = main.Book(book_isbn="ISBN-11", book_title="Example")

    result = main.user_add_book(book, USER, cursor)

    assert result == {"message": "Book added successfully", "book": book_row}
    assert cursor.execute.call_count == 3
    assert cursor.execute.call_args_list[-1].args[1] == (USER["user_id"], 11)

def test_user_add_book_rejects_duplicate_library_entry():
    """Verify adding an already tracked book returns a conflict."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"book_id": 11, "book_title": "Example"}, None]

    with pytest.raises(HTTPException) as error:
        main.user_add_book(main.Book(book_isbn="ISBN-11", book_title="Example"), USER, cursor)

    assert error.value.status_code == 409

def test_search_title_trims_query_and_scopes_user():
    """Verify title search trims its term and scopes results to the user."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_title": "The Hobbit"}]

    result = main.search_title_by_word("  Hobbit ", USER, cursor)

    assert result == {"query": "Hobbit", "books": [{"book_title": "The Hobbit"}]}
    assert cursor.execute.call_args.args[1] == (USER["user_id"], "%Hobbit%")

def test_search_pages_requires_bounds_and_valid_range():
    """Verify page searches require bounds in a valid order."""
    cursor = MagicMock()
    with pytest.raises(HTTPException) as missing:
        main.search_books_by_pages(None, None, cursor)
    assert missing.value.status_code == 400

    with pytest.raises(HTTPException) as invalid:
        main.search_books_by_pages(300, 100, cursor)
    assert invalid.value.status_code == 400
    cursor.execute.assert_not_called()

def test_search_pages_executes_with_optional_bounds():
    """Verify page search works when only one bound is supplied."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_id": 1}]

    result = main.search_books_by_pages(100, None, cursor)

    assert result == {
        "query": {"min_pages": 100, "max_pages": None},
        "books": [{"book_id": 1}],
    }
    assert cursor.execute.call_args.args[1] == (100, 100, None, None)

def test_get_book_details_returns_row_or_404():
    """Verify book details are returned or a missing book yields HTTP 404."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"book_id": 9}

    assert main.get_book_details(9, cursor) == {"book_id": 9}
    assert cursor.execute.call_args.args[1] == (9,)

    cursor.fetchone.return_value = None
    with pytest.raises(HTTPException) as error:
        main.get_book_details(9, cursor)
    assert error.value.status_code == 404

def test_add_game_inserts_game_and_tracks_for_user():
    """Verify adding a game creates it and tracks it for the user."""
    cursor = MagicMock()
    game_row = {"game_id": 4, "game_title": "Catan"}
    cursor.fetchone.side_effect = [None, game_row, {"game_id": 4}]

    result = main.add_game(main.Game(game_title="Catan"), USER, cursor)

    assert result == {"message": "Game added successfully", "game": game_row}
    assert cursor.execute.call_args_list[-1].args[1] == (USER["user_id"], 4)

def test_add_game_rejects_duplicate_tracking_entry():
    """Verify duplicate game tracking returns a conflict."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"game_id": 4, "game_title": "Catan"}, None]

    with pytest.raises(HTTPException) as error:
        main.add_game(main.Game(game_title="Catan"), USER, cursor)

    assert error.value.status_code == 409

def test_database_helpers_release_connections(monkeypatch):
    """Verify database helper functions return checked-out connections."""
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_title": "Example"}]
    connection.cursor.return_value = cursor
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    release = MagicMock()
    monkeypatch.setattr(main.db_manager, "release_conn", release)

    assert main.get_book_database() == [{"book_title": "Example"}]
    release.assert_called_once_with(connection)

def test_author_and_game_helpers_use_mocked_connection(monkeypatch):
    """Verify author and game helpers use the pooled connection."""
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.side_effect = [[{"author_id": 1}], [{"game_id": 2}]]
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    release = MagicMock()
    monkeypatch.setattr(main.db_manager, "release_conn", release)

    assert main.add_multiple_authors() == [{"author_id": 1}]
    assert main.search_all_games() == [{"game_id": 2}]
    assert release.call_args_list == [call(connection), call(connection)]

def test_load_db_config_uses_defaults_and_environment(monkeypatch):
    """Verify database configuration combines defaults with environment values."""
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_PORT"):
        monkeypatch.delenv(name, raising=False)
    assert main.load_db_config() == {
        "host": "localhost",
        "database": "digital_library",
        "user": "postgres",
        "password": "secretpassword",
        "port": "5440",
    }

    monkeypatch.setenv("DB_HOST", "db.internal")
    monkeypatch.setenv("DB_PORT", "5544")
    assert main.load_db_config()["host"] == "db.internal"
    assert main.load_db_config()["port"] == "5544"

def test_database_manager_lazily_connects_and_guards_release(monkeypatch):
    """Verify connections are acquired lazily and released safely."""
    manager = main.DatabaseManager()
    pool = MagicMock()
    connection = MagicMock()
    pool.getconn.return_value = connection
    factory = MagicMock(return_value=pool)
    monkeypatch.setattr(main, "SimpleConnectionPool", factory)
    for name, value in {
        "DB_NAME": "library_test",
        "DB_USER": "tester",
        "DB_PASSWORD": "password",
        "DB_HOST": "localhost",
        "DB_PORT": "5440",
    }.items():
        monkeypatch.setenv(name, value)

    assert manager.get_conn() is connection
    assert manager.get_conn() is connection
    factory.assert_called_once()
    manager.release_conn(connection)
    manager.release_conn(None)
    pool.putconn.assert_called_once_with(connection)
    manager.close_pool()
    manager.close_pool()
    pool.closeall.assert_called_once_with()

def test_database_manager_does_not_release_without_initialized_pool():
    """Verify a missing pool does not attempt to release a connection."""
    manager = main.DatabaseManager()

    manager.release_conn(MagicMock())

    assert manager._pool is None

def test_database_manager_propagates_pool_initialization_errors(monkeypatch):
    """Verify pool initialization errors are propagated to the caller."""
    manager = main.DatabaseManager()
    factory = MagicMock(side_effect=OSError("pool unavailable"))
    monkeypatch.setattr(main, "SimpleConnectionPool", factory)
    for name in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"):
        monkeypatch.setenv(name, "configured")

    with pytest.raises(OSError, match="pool unavailable"):
        manager.initialize_pool()
    assert manager._pool is None

def test_lifespan_initializes_and_closes_database_pool(monkeypatch):
    """Verify application startup and shutdown manage the database pool."""
    initialize = MagicMock()
    close = MagicMock()
    monkeypatch.setattr(main.db_manager, "initialize_pool", initialize)
    monkeypatch.setattr(main.db_manager, "close_pool", close)

    async def run_lifespan():
        """Run the app lifespan to check startup and shutdown behavior."""
        async with main.lifespan(main.library_app):
            initialize.assert_called_once_with()
            close.assert_not_called()

    asyncio.run(run_lifespan())
    close.assert_called_once_with()

def test_activate_user_schema_skips_creation_when_schema_is_ready():
    """Verify an initialized user schema is selected without recreating tables."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"book_info": "book_info"}

    main.activate_user_schema(cursor, 7)

    assert cursor.execute.call_count == 4
    assert cursor.execute.call_args_list[0].args[1] == (7,)

def test_activate_user_schema_creates_schema_and_reports_missing_citext(monkeypatch, tmp_path):
    """Verify schema setup creates tables and reports a missing citext extension."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"book_info": None}, None]

    with pytest.raises(RuntimeError, match="citext extension must be installed"):
        main.activate_user_schema(cursor, 7)

    assert cursor.execute.call_count == 5

    schema_file = tmp_path / "user-schema.sql"
    schema_file.write_text("CREATE TABLE sample (value public.citext);")
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"book_info": None}, {"nspname": "extensions"}]
    monkeypatch.setattr(main, "USER_SCHEMA_FILE", schema_file)
    monkeypatch.setattr(main.sql.ext, "quote_ident", lambda identifier, context: f'"{identifier}"')

    main.activate_user_schema(cursor, 7)

    assert cursor.execute.call_count == 6
    assert '"extensions".citext' in cursor.execute.call_args.args[0]

def test_cognito_key_fetch_failure_is_logged_and_raised(monkeypatch, caplog):
    """Verify key-fetch failures are logged and reported instead of failing open."""
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(
        main.requests,
        "get",
        MagicMock(side_effect=main.requests.ConnectionError("network down")),
    )

    with pytest.raises(RuntimeError, match="Unable to retrieve Cognito signing keys"):
        main.get_cognito_public_keys()
    assert "Failed to pull Cognito JWKS certificates" in caplog.text

def test_verify_cognito_token_uses_matching_public_key(monkeypatch):
    """Verify Cognito token validation uses the matching key and expected claims."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="cognito-token")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setattr(main, "get_cognito_public_keys", lambda: [{"kid": "key-1"}])
    key = MagicMock()
    monkeypatch.setattr(main.jwt.PyJWK, "from_dict", lambda jwk: key)
    decode = MagicMock(
        side_effect=[
            {"iss": "https://cognito-idp.us-west-2.amazonaws.com/pool-123"},
            {
                "sub": "cognito-user",
                "username": "reader",
                "token_use": "access",
                "client_id": "client-456",
            },
        ]
    )
    monkeypatch.setattr(main.jwt, "get_unverified_header", lambda token: {"kid": "key-1"})
    monkeypatch.setattr(main.jwt, "decode", decode)

    result = asyncio.run(main.verify_cognito_or_jwt(credentials))

    assert result == {
        "identity_provider": "aws_cognito",
        "user_id": "cognito-user",
        "username": "reader",
    }
    assert decode.call_args.kwargs == {
        "algorithms": ["RS256"],
        "issuer": "https://cognito-idp.us-west-2.amazonaws.com/pool-123",
        "options": {
            "verify_aud": False,
            "require": ["exp", "iat", "sub", "token_use", "client_id"],
        },
    }


def test_decode_bearer_token_verifies_real_cognito_access_token(monkeypatch):
    """Verify a signed Cognito access token using its matching public JWK."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(main.jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "signing-key"
    monkeypatch.setattr(main, "get_cognito_public_keys", lambda: [jwk])
    now = int(datetime.now(timezone.utc).timestamp())
    token = main.jwt.encode(
        {
            "iss": "https://cognito-idp.us-west-2.amazonaws.com/pool-123",
            "sub": "cognito-subject",
            "username": "reader@example.com",
            "client_id": "client-456",
            "token_use": "access",
            "iat": now,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "signing-key"},
    )

    assert main.decode_bearer_token(token) == {
        "identity_provider": "aws_cognito",
        "user_id": "cognito-subject",
        "username": "reader@example.com",
    }


def test_verify_cognito_token_rejects_unmatched_key(monkeypatch):
    """Verify Cognito tokens with unknown key IDs are rejected."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="cognito-token")
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(
        main,
        "get_cognito_public_keys",
        lambda force_refresh=False: [{"kid": "other-key"}],
    )
    monkeypatch.setattr(main.jwt, "get_unverified_header", lambda token: {"kid": "missing-key"})
    monkeypatch.setattr(
        main.jwt,
        "decode",
        lambda *args, **kwargs: {"iss": "https://cognito-idp.us-west-2.amazonaws.com/pool-123"},
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(main.verify_cognito_or_jwt(credentials))

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid token credentials."


def test_register_cognito_requests_email_confirmation(monkeypatch):
    """Verify Cognito sign-up uses the configured public app client."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    cognito_request = MagicMock(return_value={
        "CodeDeliveryDetails": {"DeliveryMedium": "EMAIL"}
    })
    monkeypatch.setattr(main, "cognito_api", cognito_request)

    result = main.register_cognito(
        main.CognitoRegisterRequest(
            email="reader@example.com",
            password="Valid!Password1",
        )
    )

    assert result == {
        "message": "Check your email for a Cognito confirmation code.",
        "delivery_medium": "EMAIL",
    }
    cognito_request.assert_called_once_with(
        "SignUp",
        {
            "ClientId": "client-456",
            "Username": "reader@example.com",
            "Password": "Valid!Password1",
            "UserAttributes": [{"Name": "email", "Value": "reader@example.com"}],
        },
    )


def test_cognito_login_returns_access_token(monkeypatch):
    """Verify Cognito login returns its API access token without replacing native login."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    cognito_request = MagicMock(return_value={
        "AuthenticationResult": {
            "AccessToken": "access-token",
            "TokenType": "Bearer",
            "ExpiresIn": 3600,
            "RefreshToken": "refresh-token",
        }
    })
    monkeypatch.setattr(main, "cognito_api", cognito_request)

    result = main.login_cognito(
        main.CognitoLoginRequest(email="reader@example.com", password="Valid!Password1")
    )

    assert result == {
        "access_token": "access-token",
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_token": "refresh-token",
    }
    cognito_request.assert_called_once_with(
        "InitiateAuth",
        {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": "client-456",
            "AuthParameters": {
                "USERNAME": "reader@example.com",
                "PASSWORD": "Valid!Password1",
            },
        },
    )


def test_cognito_identity_links_existing_profile_only_by_verified_email(monkeypatch):
    """Verify a verified Cognito email links to the corresponding native user profile."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        None,
        {
            "user_id": 7,
            "username": "reader",
            "email": "reader@example.com",
            "external_auth_id": None,
        },
        {"user_id": 7, "username": "reader", "email": "reader@example.com"},
    ]
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(return_value={
            "UserAttributes": [
                {"Name": "email", "Value": "reader@example.com"},
                {"Name": "email_verified", "Value": "true"},
            ]
        }),
    )

    result = main.get_or_create_cognito_user(
        {"user_id": "cognito-sub", "identity_provider": "aws_cognito"},
        "cognito-access-token",
        cursor,
    )

    assert result == {"user_id": 7, "username": "reader", "email": "reader@example.com"}
    assert "UPDATE reader_info" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1] == ("cognito-sub", 7)


def test_cognito_identity_requires_verified_email(monkeypatch):
    """Verify a Cognito identity without a verified email cannot get a local profile."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(return_value={
            "UserAttributes": [
                {"Name": "email", "Value": "reader@example.com"},
                {"Name": "email_verified", "Value": "false"},
            ]
        }),
    )

    with pytest.raises(HTTPException) as error:
        main.get_or_create_cognito_user(
            {"user_id": "cognito-sub", "identity_provider": "aws_cognito"},
            "cognito-access-token",
            cursor,
        )

    assert error.value.status_code == 403
    assert "verified email" in error.value.detail


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("AWS_REGION", ""),
        ("COGNITO_USER_POOL_ID", ""),
        ("COGNITO_CLIENT_ID", ""),
    ],
)
def test_cognito_configuration_requires_each_setting(monkeypatch, setting, value):
    """Verify every required Cognito setting is checked."""
    for name in ("AWS_REGION", "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID"):
        monkeypatch.setenv(name, "configured")
    monkeypatch.setenv(setting, value)

    with pytest.raises(RuntimeError, match="AWS_REGION"):
        main.cognito_configuration()


def test_cognito_configuration_returns_trimmed_settings(monkeypatch):
    """Verify Cognito settings are stripped before use."""
    monkeypatch.setenv("AWS_REGION", " us-west-2 ")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", " pool-123 ")
    monkeypatch.setenv("COGNITO_CLIENT_ID", " client-456 ")

    assert main.cognito_configuration() == ("us-west-2", "pool-123", "client-456")


def test_cognito_api_posts_signed_public_operation(monkeypatch):
    """Verify Cognito API requests use the region endpoint and operation header."""
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    response = MagicMock(ok=True)
    response.json.return_value = {"UserSub": "cognito-sub"}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(main.requests, "post", request)

    assert main.cognito_api("SignUp", {"ClientId": "client-456"}) == {
        "UserSub": "cognito-sub"
    }
    request.assert_called_once_with(
        "https://cognito-idp.us-west-2.amazonaws.com/",
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.SignUp",
        },
        json={"ClientId": "client-456"},
        timeout=10,
    )


def test_cognito_api_reports_transport_and_invalid_json_errors(monkeypatch):
    """Verify Cognito network errors and invalid responses are surfaced."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(
        main.requests,
        "post",
        MagicMock(side_effect=main.requests.ConnectionError("offline")),
    )
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        main.cognito_api("SignUp", {})

    response = MagicMock(ok=True)
    response.json.side_effect = ValueError("not JSON")
    monkeypatch.setattr(main.requests, "post", MagicMock(return_value=response))
    with pytest.raises(RuntimeError, match="invalid response"):
        main.cognito_api("SignUp", {})

    response.json.side_effect = None
    response.json.return_value = ["not", "an", "object"]
    with pytest.raises(RuntimeError, match="invalid response"):
        main.cognito_api("SignUp", {})


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"__type": "com.example#UsernameExistsException:http"}, "UsernameExistsException"),
        ({}, "CognitoServiceError"),
    ],
)
def test_cognito_api_translates_provider_errors(monkeypatch, payload, expected_code):
    """Verify Cognito error payloads become typed provider exceptions."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    response = MagicMock(ok=False)
    response.json.return_value = payload
    monkeypatch.setattr(main.requests, "post", MagicMock(return_value=response))

    with pytest.raises(main.CognitoApiError) as error:
        main.cognito_api("SignUp", {})

    assert error.value.code == expected_code
    assert str(error.value) == expected_code


@pytest.mark.parametrize("document", [[], {"keys": "not-a-list"}])
def test_cognito_jwks_rejects_malformed_documents(monkeypatch, document):
    """Verify invalid JWKS payload and key-list shapes fail explicitly."""
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    response = MagicMock()
    response.json.return_value = document
    monkeypatch.setattr(main.requests, "get", MagicMock(return_value=response))

    with pytest.raises(RuntimeError, match="Unable to retrieve Cognito signing keys"):
        main.get_cognito_public_keys()


def test_cognito_jwks_refreshes_cached_keys(monkeypatch):
    """Verify a forced JWKS refresh replaces the cached key set."""
    old_keys = [{"kid": "old"}]
    new_keys = [{"kid": "new"}]
    monkeypatch.setattr(main, "_COGNITO_JWKS", old_keys)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    response = MagicMock()
    response.json.return_value = {"keys": new_keys}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(main.requests, "get", request)

    assert main.get_cognito_public_keys() == old_keys
    assert main.get_cognito_public_keys(force_refresh=True) == new_keys
    request.assert_called_once_with(
        "https://cognito-idp.us-east-1.amazonaws.com/pool-123/.well-known/jwks.json",
        timeout=5,
    )


def cognito_issuer_token(issuer):
    """Build a signed token with a chosen issuer for verifier rejection tests."""
    return main.jwt.encode(
        {"iss": issuer, "sub": "cognito-sub"},
        "unit-test-secret-that-is-long-enough-32",
        algorithm="HS256",
    )


def test_cognito_token_verification_rejects_disabled_and_misconfigured_tokens(monkeypatch):
    """Verify Cognito token use is disabled by default and requires complete configuration."""
    token = cognito_issuer_token("https://cognito-idp.us-west-2.amazonaws.com/pool-123")
    monkeypatch.setenv("USE_COGNITO", "false")
    with pytest.raises(HTTPException) as disabled:
        main.decode_bearer_token(token)
    assert disabled.value.status_code == 401

    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.delenv("COGNITO_CLIENT_ID", raising=False)
    with pytest.raises(HTTPException) as missing_config:
        main.decode_bearer_token(token)
    assert missing_config.value.status_code == 503


def test_cognito_token_verification_rejects_wrong_issuer(monkeypatch):
    """Verify a token from a different Cognito pool is rejected."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")

    with pytest.raises(HTTPException) as error:
        main.decode_bearer_token(
            cognito_issuer_token("https://cognito-idp.us-west-2.amazonaws.com/other-pool")
        )
    assert error.value.status_code == 401


def test_cognito_token_verification_surfaces_jwks_failure_as_service_unavailable(monkeypatch):
    """Verify JWKS network failures become a service-unavailable response."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(
        main,
        "get_cognito_public_keys",
        MagicMock(side_effect=RuntimeError("JWKS unavailable")),
    )

    with pytest.raises(HTTPException) as error:
        main.decode_bearer_token(
            cognito_issuer_token("https://cognito-idp.us-west-2.amazonaws.com/pool-123")
        )
    assert error.value.status_code == 503
    assert error.value.detail == "JWKS unavailable"


def test_cognito_token_verification_rejects_id_tokens_and_wrong_clients(monkeypatch):
    """Verify only access tokens issued for the configured app client are accepted."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(main, "get_cognito_public_keys", lambda: [{"kid": "key-1"}])
    monkeypatch.setattr(main.jwt.PyJWK, "from_dict", lambda jwk: MagicMock(key="public-key"))
    monkeypatch.setattr(main.jwt, "get_unverified_header", lambda token: {"kid": "key-1"})

    for claims in (
        {"token_use": "id", "client_id": "client-456"},
        {"token_use": "access", "client_id": "another-client"},
    ):
        decode = MagicMock(
            side_effect=[
                {"iss": "https://cognito-idp.us-west-2.amazonaws.com/pool-123"},
                {
                    **claims,
                    "sub": "cognito-sub",
                    "iat": 1,
                    "exp": 9999999999,
                },
            ]
        )
        monkeypatch.setattr(main.jwt, "decode", decode)
        with pytest.raises(HTTPException) as error:
            main.decode_bearer_token("signed-token")
        assert error.value.status_code == 401


def test_cognito_token_refreshes_jwks_for_rotated_signing_key(monkeypatch):
    """Verify an unknown cached key triggers a refresh and accepts the rotated key."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    key = MagicMock(key="public-key")
    monkeypatch.setattr(main.jwt.PyJWK, "from_dict", lambda jwk: key)
    monkeypatch.setattr(main.jwt, "get_unverified_header", lambda token: {"kid": "rotated"})
    key_lookup = MagicMock(side_effect=[[], [{"kid": "rotated"}]])
    monkeypatch.setattr(main, "get_cognito_public_keys", key_lookup)
    monkeypatch.setattr(
        main.jwt,
        "decode",
        MagicMock(
            side_effect=[
                {"iss": "https://cognito-idp.us-west-2.amazonaws.com/pool-123"},
                {
                    "sub": "cognito-sub",
                    "token_use": "access",
                    "client_id": "client-456",
                    "iat": 1,
                    "exp": 9999999999,
                },
            ]
        ),
    )

    result = main.decode_bearer_token("signed-token")

    assert result["identity_provider"] == "aws_cognito"
    assert key_lookup.call_args_list == [call(), call(force_refresh=True)]


def test_get_current_user_resolves_cognito_profile(monkeypatch):
    """Verify a valid Cognito identity resolves and activates its local profile."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="access-token")
    profile = {"user_id": 12, "username": "cognito_reader", "email": "reader@example.com"}
    monkeypatch.setattr(
        main,
        "decode_bearer_token",
        lambda token: {"identity_provider": "aws_cognito", "user_id": "subject"},
    )
    resolve = MagicMock(return_value=profile)
    activate = MagicMock()
    monkeypatch.setattr(main, "get_or_create_cognito_user", resolve)
    monkeypatch.setattr(main, "activate_user_schema", activate)

    assert main.get_current_user(credentials, MagicMock()) == profile
    resolve.assert_called_once_with(
        {"identity_provider": "aws_cognito", "user_id": "subject"},
        "access-token",
        resolve.call_args.args[2],
    )
    activate.assert_called_once_with(resolve.call_args.args[2], profile["user_id"])


def test_get_or_create_cognito_user_returns_existing_identity(monkeypatch):
    """Verify an already-linked Cognito subject avoids another provider request."""
    cursor = MagicMock()
    cursor.fetchone.return_value = USER
    provider_call = MagicMock()
    monkeypatch.setattr(main, "cognito_api", provider_call)

    assert main.get_or_create_cognito_user(
        {"user_id": "subject"}, "access-token", cursor
    ) == USER
    provider_call.assert_not_called()


@pytest.mark.parametrize(
    ("provider_error", "status_code"),
    [(main.CognitoApiError("InvalidToken"), 401), (RuntimeError("unavailable"), 503)],
)
def test_get_or_create_cognito_user_maps_provider_errors(
    monkeypatch, provider_error, status_code
):
    """Verify provider authentication and availability errors are translated."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    monkeypatch.setattr(main, "cognito_api", MagicMock(side_effect=provider_error))

    with pytest.raises(HTTPException) as error:
        main.get_or_create_cognito_user(
            {"user_id": "subject"}, "access-token", cursor
        )
    assert error.value.status_code == status_code


def test_get_or_create_cognito_user_rejects_missing_email(monkeypatch):
    """Verify a Cognito profile with no email is not linked to an app account."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(return_value={"UserAttributes": [{"Name": "email_verified", "Value": "true"}]}),
    )

    with pytest.raises(HTTPException) as error:
        main.get_or_create_cognito_user({"user_id": "subject"}, "access-token", cursor)
    assert error.value.status_code == 403


def test_get_or_create_cognito_user_rejects_email_linked_to_other_subject(monkeypatch):
    """Verify a verified email already linked to another Cognito subject conflicts."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        None,
        {**USER, "external_auth_id": "different-subject"},
    ]
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(
            return_value={
                "UserAttributes": [
                    {"Name": "email", "Value": USER["email"]},
                    {"Name": "email_verified", "Value": "true"},
                ]
            }
        ),
    )

    with pytest.raises(HTTPException) as error:
        main.get_or_create_cognito_user(
            {"user_id": "subject"}, "access-token", cursor
        )
    assert error.value.status_code == 409


def test_get_or_create_cognito_user_returns_profile_already_linked_to_same_subject(
    monkeypatch,
):
    """Verify a matching Cognito subject on an email-matched profile is reused."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [None, {**USER, "external_auth_id": "subject"}]
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(
            return_value={
                "UserAttributes": [
                    {"Name": "email", "Value": USER["email"]},
                    {"Name": "email_verified", "Value": "true"},
                ]
            }
        ),
    )

    assert main.get_or_create_cognito_user(
        {"user_id": "subject"}, "access-token", cursor
    ) == {**USER, "external_auth_id": "subject"}


@pytest.mark.parametrize(
    ("update_result", "retry_result", "expected_user", "expected_status"),
    [
        (None, USER, USER, None),
        (None, None, None, 409),
    ],
)
def test_cognito_profile_link_race_is_resolved_or_rejected(
    monkeypatch, update_result, retry_result, expected_user, expected_status
):
    """Verify a concurrent Cognito profile link is re-read and never silently lost."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        None,
        {**USER, "external_auth_id": None},
        update_result,
        retry_result,
    ]
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(
            return_value={
                "UserAttributes": [
                    {"Name": "email", "Value": USER["email"]},
                    {"Name": "email_verified", "Value": "true"},
                ]
            }
        ),
    )

    if expected_status:
        with pytest.raises(HTTPException) as error:
            main.get_or_create_cognito_user({"user_id": "subject"}, "access-token", cursor)
        assert error.value.status_code == expected_status
    else:
        assert main.get_or_create_cognito_user(
            {"user_id": "subject"}, "access-token", cursor
        ) == expected_user


def test_cognito_profile_creates_a_new_local_user(monkeypatch):
    """Verify a first-time Cognito subject gets a deterministic local username."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        None,
        None,
        {"user_id": 14, "username": "cognito_subject123", "email": USER["email"]},
    ]
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(
            return_value={
                "UserAttributes": [
                    {"Name": "email", "Value": USER["email"]},
                    {"Name": "email_verified", "Value": "true"},
                ]
            }
        ),
    )

    result = main.get_or_create_cognito_user(
        {"user_id": "subject-123"}, "access-token", cursor
    )

    assert result["username"] == "cognito_subject123"
    assert cursor.execute.call_args.args[1] == (
        "cognito_subject123",
        USER["email"],
        "subject-123",
    )


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("UsernameExistsException", 409),
        ("CodeMismatchException", 400),
        ("ExpiredCodeException", 400),
        ("InvalidParameterException", 400),
        ("InvalidPasswordException", 400),
        ("NotAuthorizedException", 401),
        ("UserNotFoundException", 401),
        ("LimitExceededException", 429),
        ("TooManyRequestsException", 429),
        ("InternalErrorException", 502),
    ],
)
def test_cognito_http_error_translates_provider_error_codes(code, status_code, caplog):
    """Verify known Cognito errors map to stable HTTP statuses and unknown errors log."""
    error = main.cognito_http_error(main.CognitoApiError(code))

    assert error.status_code == status_code
    if status_code == 502:
        assert code in caplog.text


@pytest.mark.parametrize("authentication", [None, {}, {"AccessToken": ""}])
def test_cognito_tokens_rejects_incomplete_authentication(monkeypatch, authentication):
    """Verify Cognito challenges without an access token are not treated as login success."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(return_value={"AuthenticationResult": authentication}),
    )

    with pytest.raises(HTTPException) as error:
        main.cognito_tokens("reader@example.com", "password")
    assert error.value.status_code == 409


def test_cognito_tokens_omits_absent_refresh_token(monkeypatch):
    """Verify optional refresh token fields are omitted when Cognito does not return one."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(
        main,
        "cognito_api",
        MagicMock(
            return_value={
                "AuthenticationResult": {
                    "AccessToken": "access-token",
                    "TokenType": "Token",
                }
            }
        ),
    )

    assert main.cognito_tokens("reader@example.com", "password") == {
        "access_token": "access-token",
        "token_type": "token",
        "expires_in": None,
    }


@pytest.mark.parametrize(
    ("endpoint", "body"),
    [
        (main.register_cognito, main.CognitoRegisterRequest(
            email="reader@example.com", password="Valid!Password1"
        )),
        (main.confirm_cognito, main.CognitoConfirmRequest(
            email="reader@example.com", confirmation_code="123456"
        )),
        (main.login_cognito, main.CognitoLoginRequest(
            email="reader@example.com", password="Valid!Password1"
        )),
    ],
)
def test_cognito_endpoints_are_disabled_by_default(monkeypatch, endpoint, body):
    """Verify each Cognito endpoint is explicitly disabled unless configured."""
    monkeypatch.setenv("USE_COGNITO", "false")

    with pytest.raises(HTTPException) as error:
        endpoint(body)
    assert error.value.status_code == 503


def test_cognito_register_handles_provider_and_configuration_errors(monkeypatch):
    """Verify Cognito registration maps service errors and missing configuration."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    body = main.CognitoRegisterRequest(email=USER["email"], password="Valid!Password1")

    for provider_error, expected_status in (
        (main.CognitoApiError("UsernameExistsException"), 409),
        (RuntimeError("Cognito unavailable"), 503),
    ):
        monkeypatch.setattr(main, "cognito_api", MagicMock(side_effect=provider_error))
        with pytest.raises(HTTPException) as error:
            main.register_cognito(body)
        assert error.value.status_code == expected_status

    monkeypatch.delenv("COGNITO_CLIENT_ID")
    with pytest.raises(HTTPException) as error:
        main.register_cognito(body)
    assert error.value.status_code == 503


def test_cognito_register_uses_default_email_delivery(monkeypatch):
    """Verify sign-up remains successful when Cognito omits delivery metadata."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(main, "cognito_api", MagicMock(return_value={}))

    assert main.register_cognito(
        main.CognitoRegisterRequest(email=USER["email"], password="Valid!Password1")
    )["delivery_medium"] == "EMAIL"


def test_cognito_confirm_handles_success_provider_errors_and_configuration(monkeypatch):
    """Verify Cognito email confirmation success and explicit error handling."""
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    body = main.CognitoConfirmRequest(email=f" {USER['email']} ", confirmation_code=" 123456 ")
    request = MagicMock(return_value={})
    monkeypatch.setattr(main, "cognito_api", request)

    assert main.confirm_cognito(body) == {
        "message": "Email confirmed. Sign in with your email and password."
    }
    assert request.call_args.args[1]["Username"] == USER["email"]
    assert request.call_args.args[1]["ConfirmationCode"] == "123456"

    for provider_error, expected_status in (
        (main.CognitoApiError("CodeMismatchException"), 400),
        (RuntimeError("Cognito unavailable"), 503),
    ):
        monkeypatch.setattr(main, "cognito_api", MagicMock(side_effect=provider_error))
        with pytest.raises(HTTPException) as error:
            main.confirm_cognito(body)
        assert error.value.status_code == expected_status

    monkeypatch.delenv("COGNITO_CLIENT_ID")
    with pytest.raises(HTTPException) as error:
        main.confirm_cognito(body)
    assert error.value.status_code == 503


def test_cognito_login_maps_provider_and_configuration_errors(monkeypatch):
    """Verify Cognito login returns HTTP errors for provider and configuration failures."""
    monkeypatch.setenv("USE_COGNITO", "true")
    body = main.CognitoLoginRequest(email=USER["email"], password="Valid!Password1")
    monkeypatch.setattr(
        main,
        "cognito_tokens",
        MagicMock(side_effect=main.CognitoApiError("NotAuthorizedException")),
    )
    with pytest.raises(HTTPException) as error:
        main.login_cognito(body)
    assert error.value.status_code == 401

    monkeypatch.setattr(
        main,
        "cognito_tokens",
        MagicMock(side_effect=RuntimeError("Cognito unavailable")),
    )
    with pytest.raises(HTTPException) as error:
        main.login_cognito(body)
    assert error.value.status_code == 503


def test_cognito_register_request_rejects_invalid_email():
    """Verify Cognito registration validates email before calling the provider."""
    with pytest.raises(ValueError, match="valid email"):
        main.CognitoRegisterRequest(email="not-an-email", password="Valid!Password1")


def test_register_translates_unique_violation(monkeypatch):
    """Verify duplicate registration details become HTTP 409."""
    cursor = MagicMock()
    cursor.execute.side_effect = main.psycopg2.errors.UniqueViolation("duplicate")
    monkeypatch.setattr(main, "password_hasher", MagicMock())

    with pytest.raises(HTTPException) as error:
        main.register(main.RegisterRequest(username="reader", email="reader@example.com", password="password123"), cursor)

    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "verification_error",
    [main.VerificationError("invalid hash"), main.InvalidHashError("invalid hash")],
)
def test_login_rejects_unverifiable_password_hash(monkeypatch, verification_error):
    """Verify invalid stored password hashes fail authentication."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {**USER, "password_hash": "invalid-hash"}
    hasher = MagicMock()
    hasher.verify.side_effect = verification_error
    monkeypatch.setattr(main, "password_hasher", hasher)

    with pytest.raises(HTTPException) as error:
        main.login(main.LoginRequest(username="reader", password="password123"), cursor)

    assert error.value.status_code == 401


def test_connect_closes_connection_after_success_or_error(monkeypatch):
    """Verify direct database connections close after success or query failure."""
    connection = MagicMock()
    monkeypatch.setattr(main.psycopg2, "connect", MagicMock(return_value=connection))
    for name, value in {
        "DB_NAME": "library_test",
        "DB_USER": "tester",
        "DB_PASSWORD": "password",
        "DB_HOST": "localhost",
        "DB_PORT": "5440",
    }.items():
        monkeypatch.setenv(name, value)

    main.connect()

    connection.cursor.return_value.execute.assert_called_once_with("SELECT version();")
    connection.close.assert_called_once_with()

    failed_connection = MagicMock()
    failed_connection.cursor.return_value.execute.side_effect = RuntimeError("query failed")
    monkeypatch.setattr(main.psycopg2, "connect", MagicMock(return_value=failed_connection))
    with pytest.raises(RuntimeError, match="query failed"):
        main.connect()
    failed_connection.close.assert_called_once_with()

    monkeypatch.setattr(
        main.psycopg2,
        "connect",
        MagicMock(side_effect=OSError("connection refused")),
    )
    with pytest.raises(OSError, match="connection refused"):
        main.connect()


@pytest.mark.parametrize(
    ("endpoint", "expected_query"),
    [
        (main.get_book_summaries_from_database, "SELECT book_id, book_title FROM book_info;"),
        (main.get_details_from_database, "SELECT * FROM book_info;"),
    ],
)
def test_book_listing_endpoints_return_rows(endpoint, expected_query):
    """Verify both catalog-listing endpoints return their database rows."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_id": 1}]

    assert endpoint(USER, cursor) == {"books": [{"book_id": 1}]}
    cursor.execute.assert_called_once_with(expected_query)


@pytest.mark.parametrize(
    ("endpoint", "expected_detail"),
    [
        (main.get_book_summaries_from_database, "Could not find book details"),
        (main.get_details_from_database, "Could not find info"),
    ],
)
def test_book_listing_endpoints_translate_database_errors(endpoint, expected_detail):
    """Verify catalog-listing database errors become endpoint-specific responses."""
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        endpoint(USER, cursor)

    assert error.value.status_code == 500
    assert error.value.detail == expected_detail


def test_user_add_book_reuses_existing_book_and_adds_author(monkeypatch):
    """Verify existing catalog books are reused and author relations are added when supplied."""
    existing = {"book_id": 11, "book_title": "Example"}
    cursor = MagicMock()
    cursor.fetchone.side_effect = [existing, {"book_id": 11}]

    result = main.user_add_book(
        main.Book(book_isbn="ISBN-11", book_title="Example"), USER, cursor
    )
    assert result["book"] == existing
    assert cursor.execute.call_count == 2

    cursor = MagicMock()
    cursor.fetchone.side_effect = [None, existing, {"book_id": 11}]
    main.user_add_book(
        main.Book(book_isbn="ISBN-11", book_title="Example", author_id=2, creator_role_id=3),
        USER,
        cursor,
    )
    assert cursor.execute.call_count == 4
    assert cursor.execute.call_args_list[2].args[1] == (11, 2, 3)


@pytest.mark.parametrize(
    ("database_error", "status_code", "detail"),
    [
        (main.psycopg2.errors.UniqueViolation("duplicate"), 409, "ISBN or code"),
        (main.psycopg2.errors.ForeignKeyViolation("foreign key"), 400, "author_id"),
        (main.psycopg2.errors.CheckViolation("check"), 400, "ISBN or an internal_code"),
        (main.psycopg2.Error("database"), 500, "A database error occurred"),
    ],
)
def test_user_add_book_translates_database_errors(database_error, status_code, detail):
    """Verify book creation maps database constraint failures to HTTP errors."""
    cursor = MagicMock()
    cursor.execute.side_effect = database_error

    with pytest.raises(HTTPException) as error:
        main.user_add_book(main.Book(book_isbn="ISBN-11", book_title="Example"), USER, cursor)

    assert error.value.status_code == status_code
    assert detail in error.value.detail


@pytest.mark.parametrize(
    ("endpoint", "argument"),
    [
        (main.search_books_by_media_type, "media_type"),
        (main.search_books_by_book_genre, "genre"),
        (main.search_books_by_author, "author"),
        (main.get_comic_book_from_database, "comic"),
    ],
)
def test_book_search_endpoints_trim_and_return_results(endpoint, argument):
    """Verify book-search endpoints trim input and return matching results."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_id": 3}]

    result = endpoint("  example  ", USER, cursor)

    expected_key = "comic_books" if argument == "comic" else "books"
    if argument == "comic":
        assert result == {expected_key: [{"book_id": 3}]}
    else:
        assert result == {"query": "example", expected_key: [{"book_id": 3}]}
    assert cursor.execute.call_args.args[1] == ("%example%",)


@pytest.mark.parametrize(
    ("endpoint", "argument"),
    [
        (main.search_books_by_media_type, "media_type"),
        (main.search_books_by_book_genre, "genre"),
        (main.search_books_by_author, "author"),
        (main.get_comic_book_from_database, "comic"),
    ],
)
def test_book_search_endpoints_reject_blank_search_terms(endpoint, argument):
    """Verify book-search endpoints reject blank terms before querying."""
    cursor = MagicMock()

    with pytest.raises(HTTPException) as error:
        endpoint("  ", USER, cursor)

    assert error.value.status_code == 400
    cursor.execute.assert_not_called()


@pytest.mark.parametrize(
    ("endpoint", "argument", "message"),
    [
        (main.search_books_by_media_type, "media_type", "Search by media type failed"),
        (main.search_books_by_book_genre, "genre", "Search by book genre failed"),
        (main.search_books_by_author, "author", "Search by author failed"),
        (main.get_comic_book_from_database, "comic", "database unavailable"),
    ],
)
def test_book_search_endpoints_translate_database_errors(endpoint, argument, message):
    """Verify book-search database failures become endpoint errors."""
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        endpoint("example", USER, cursor)

    assert error.value.status_code == 500
    assert message in error.value.detail


@pytest.mark.parametrize(
    ("endpoint", "arguments", "expected"),
    [
        (
            main.description_removal,
            (9, USER),
            main.Book_Description(book_id=9, book_title="Example", book_description=None),
        ),
        (
            main.description_change_by_id,
            (9, main.Book_Description_Update(book_description="Notes"), USER),
            main.Book_Description(book_id=9, book_title="Example", book_description="Notes"),
        ),
        (
            main.description_change,
            ("Example", main.Book_Description_Update(book_description="Notes"), USER),
            main.Book_Description(book_id=9, book_title="Example", book_description="Notes"),
        ),
    ],
)
def test_book_description_endpoints_return_updated_row(endpoint, arguments, expected):
    """Verify description endpoints return the updated user-specific record."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "book_id": 9,
        "book_title": "Example",
        "book_description": expected.book_description,
    }

    assert endpoint(*arguments, cursor) == expected


@pytest.mark.parametrize(
    ("endpoint", "arguments", "message"),
    [
        (main.description_removal, (9, USER), main.NOT_IN_LIBRARY),
        (main.description_change_by_id, (9, main.Book_Description_Update(book_description="Notes"), USER), main.NOT_IN_LIBRARY),
        (main.description_change, ("Example", main.Book_Description_Update(book_description="Notes"), USER), main.NOT_IN_LIBRARY),
        (main.delete_book_by_id, (9, USER), main.NOT_IN_LIBRARY),
        (main.delete_book_endpoint, ("Example", USER), main.NOT_IN_LIBRARY),
        (main.delete_game_endpoint, ("Catan", USER), "Game not found in your library."),
        (main.update_book_progress_by_title, ("Example", main.BookProgressUpdate(read_status="read"), USER), "Book not found in your library."),
    ],
)
def test_delete_and_update_endpoints_return_not_found(endpoint, arguments, message):
    """Verify delete and update endpoints return HTTP 404 for missing records."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    with pytest.raises(HTTPException) as error:
        endpoint(*arguments, cursor)

    assert error.value.status_code == 404
    assert error.value.detail == message


@pytest.mark.parametrize(
    ("endpoint", "arguments", "message"),
    [
        (main.description_removal, (9, USER), "Could not remove description"),
        (main.description_change_by_id, (9, main.Book_Description_Update(book_description="Notes"), USER), "Could not update description"),
        (main.description_change, ("Example", main.Book_Description_Update(book_description="Notes"), USER), "Could not update description"),
        (main.delete_book_by_id, (9, USER), "Could not remove book"),
        (main.delete_book_endpoint, ("Example", USER), "Could not remove book"),
        (main.delete_game_endpoint, ("Catan", USER), "Could not remove game"),
        (main.update_book_progress_by_title, ("Example", main.BookProgressUpdate(read_status="read"), USER), "Progress sync failed"),
    ],
)
def test_delete_and_update_endpoints_translate_database_errors(endpoint, arguments, message):
    """Verify delete and update database failures become HTTP 500 responses."""
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        endpoint(*arguments, cursor)

    assert error.value.status_code == 500
    assert message in error.value.detail


def test_delete_book_endpoints_remove_rows():
    """Verify deleting a book removes only the user-library association."""
    book = {"book_id": 9, "book_title": "Example"}
    cursor = MagicMock()
    cursor.fetchone.return_value = book

    assert main.delete_book_by_id(9, USER, cursor) == {
        "message": "Book removed from your library",
        "book": book,
    }
    cursor.fetchone.return_value = book
    assert main.delete_book_endpoint(" Example ", USER, cursor) == {
        "message": "Book removed from your library",
        "book": book,
    }
    assert cursor.execute.call_args.args[1] == ("Example", USER["user_id"])


def test_get_all_games_returns_user_games_and_translates_errors():
    """Verify game listings are user-scoped and database failures are handled."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"game_id": 4}]

    assert main.get_all_games(USER, cursor) == {"games": [{"game_id": 4}]}
    assert cursor.execute.call_args.args[1] == (USER["user_id"],)

    cursor.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(HTTPException) as error:
        main.get_all_games(USER, cursor)
    assert error.value.status_code == 500
    assert error.value.detail == "Could not retrieve games"


def test_add_game_reuses_existing_game_and_translates_unexpected_errors():
    """Verify existing games are reused and unexpected errors are surfaced."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"game_id": 4, "game_title": "Catan"}, {"game_id": 4}]

    result = main.add_game(main.Game(game_title="Catan"), USER, cursor)

    assert result["game"]["game_id"] == 4
    assert cursor.execute.call_count == 2

    cursor.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(HTTPException) as error:
        main.add_game(main.Game(game_title="Catan"), USER, cursor)
    assert error.value.status_code == 500
    assert "database unavailable" in error.value.detail


def test_update_book_progress_returns_updated_record():
    """Verify book progress updates return the normalized saved record."""
    cursor = MagicMock()
    row = {"book_id": 9, "book_title": "Example", "read_status": "read", "rating": 5}
    cursor.fetchone.return_value = row

    result = main.update_book_progress_by_title(
        " Example ", main.BookProgressUpdate(read_status="read", rating=5), USER, cursor
    )

    assert result == {"status": "success", "updated_record": row}
    assert cursor.execute.call_args.args[1] == ("read", 5, USER["user_id"], "Example")


@pytest.mark.parametrize(
    ("username", "email", "message"),
    [
        ("invalid username", "reader@example.com", "Username must be 3-30 characters"),
        ("reader", "not-an-email", "Enter a valid email address"),
        ("reader", "a" * 245 + "@example.com", "Enter a valid email address"),
    ],
)
def test_register_request_rejects_invalid_username_or_email(username, email, message):
    """Verify registration rejects invalid usernames and email addresses."""
    with pytest.raises(ValueError, match=message):
        main.RegisterRequest(username=username, email=email, password="password123")


def test_get_current_user_requires_credentials():
    """Verify current-user lookup requires bearer credentials."""
    with pytest.raises(HTTPException) as error:
        main.get_current_user(None, MagicMock())

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_read_me_returns_authenticated_user():
    """Verify the profile endpoint returns the authenticated user."""
    assert main.read_me(USER) == {"user": USER}


@pytest.mark.parametrize(
    ("book_data", "message"),
    [
        ({"book_title": "   ", "book_isbn": "ISBN-1"}, "book_title cannot be empty"),
        ({"book_title": "Example"}, "Either book_isbn or internal_code is required"),
    ],
)
def test_book_model_rejects_empty_title_or_missing_identifier(book_data, message):
    """Verify books with blank titles or no identifier are rejected."""
    with pytest.raises(ValueError, match=message):
        main.Book(**book_data)


def test_search_title_rejects_blank_term_and_translates_database_error():
    """Verify title search rejects blank terms and reports database failures."""
    cursor = MagicMock()
    with pytest.raises(HTTPException) as blank:
        main.search_title_by_word("   ", USER, cursor)
    assert blank.value.status_code == 400
    cursor.execute.assert_not_called()

    cursor.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(HTTPException) as failed:
        main.search_title_by_word("Example", USER, cursor)
    assert failed.value.status_code == 500
    assert failed.value.detail == "Search failed: database unavailable"


def test_search_books_by_pages_translates_database_error():
    """Verify page-search database failures become HTTP 500 responses."""
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        main.search_books_by_pages(10, 20, cursor)

    assert error.value.status_code == 500
    assert error.value.detail == "Search by page count failed: database unavailable"


def test_get_book_details_translates_database_error():
    """Verify book-detail database failures become HTTP 500 responses."""
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        main.get_book_details(9, cursor)

    assert error.value.status_code == 500
    assert error.value.detail == "database unavailable"


def test_get_book_database_prints_rows_and_releases_connection(monkeypatch, capsys):
    """Verify the book database helper prints results and releases its connection."""
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_title": "Example"}, {"book_title": "Another"}]
    connection.cursor.return_value = cursor
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    release = MagicMock()
    monkeypatch.setattr(main.db_manager, "release_conn", release)

    assert main.get_book_database() == [
        {"book_title": "Example"},
        {"book_title": "Another"},
    ]
    assert capsys.readouterr().out == "Found 2 books:\nExample\nAnother\n"
    cursor.close.assert_called_once_with()
    release.assert_called_once_with(connection)


def test_get_book_database_reraises_errors_and_releases_connection(monkeypatch, capsys):
    """Verify the book database helper propagates errors and releases its connection."""
    connection = MagicMock()
    connection.cursor.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    release = MagicMock()
    monkeypatch.setattr(main.db_manager, "release_conn", release)

    with pytest.raises(RuntimeError, match="database unavailable"):
        main.get_book_database()

    assert capsys.readouterr().out == "database unavailable\n"
    release.assert_called_once_with(connection)


def test_game_model_rejects_blank_title():
    """Verify game titles containing only whitespace are rejected."""
    with pytest.raises(ValueError, match="game_title cannot be empty"):
        main.Game(game_title="   ")


def test_delete_game_returns_removed_game():
    """Verify deleting a game returns the removed tracked record."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"game_id": 4, "game_title": "Catan"}

    assert main.delete_game_endpoint(" Catan ", USER, cursor) == {
        "message": "Game removed from your library",
        "game": {"game_id": 4, "game_title": "Catan"},
    }
    assert cursor.execute.call_args.args[1] == ("Catan", USER["user_id"])


def test_main_entrypoint_runs_with_optional_dotenv_and_mocked_database(monkeypatch):
    """Verify the entry point tolerates missing dotenv and starts the API."""
    import builtins
    import runpy

    original_import = builtins.__import__

    def import_without_dotenv(name, *args, **kwargs):
        """Simulate dotenv being unavailable while preserving other imports."""
        if name == "dotenv":
            raise ImportError("dotenv unavailable")
        return original_import(name, *args, **kwargs)

    pool = MagicMock()
    monkeypatch.setattr(main.psycopg2.pool, "SimpleConnectionPool", MagicMock(return_value=pool))
    run_server = MagicMock()
    monkeypatch.setattr(main.uvicorn, "run", run_server)
    monkeypatch.setattr(builtins, "__import__", import_without_dotenv)

    runpy.run_path(main.__file__, run_name="__main__")

    pool.getconn.assert_called_once_with()
    pool.putconn.assert_called_once()
    pool.closeall.assert_not_called()
    run_server.assert_called_once_with("main:library_app", host="0.0.0.0", port=8000, reload=True)


def test_main_continues_when_database_check_fails(monkeypatch, capsys):
    """Verify a failed startup database check does not prevent API startup."""
    database_check = MagicMock(side_effect=RuntimeError("database unavailable"))
    initialize_pool = MagicMock()
    run_server = MagicMock()
    monkeypatch.setattr(main, "get_book_database", database_check)
    monkeypatch.setattr(main.db_manager, "initialize_pool", initialize_pool)
    monkeypatch.setattr(main.uvicorn, "run", run_server)

    main.main()

    assert capsys.readouterr().out == (
        "Hello from digital-library-system!\n"
        "Main execution warning: Local database check failed (database unavailable)\n"
    )
    initialize_pool.assert_called_once_with()
    run_server.assert_called_once_with(
        "main:library_app", host="0.0.0.0", port=8000, reload=True
    )

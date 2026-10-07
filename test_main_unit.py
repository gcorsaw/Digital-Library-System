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
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

os.environ.setdefault("DB_NAME", "digital_library_unit_test")
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-that-is-long-enough-32")

import main

"""The USER dictionary represents a mock user object and it's used in tests to 
simulate an authenticated user interacting with the application. It contains 
essential user information such as user_id, username, and email, which are
used to verify that the application correctly handles user-related operations,
such as fetching user-specific data, adding books or games to the user's library, 
and ensuring that the correct user context is applied in database queries. 
The creation of mock user data is going to allow for testing the applcation's
functionality without depending on a real database or user authentication
system, making the tests more reliable and easier to run in isolation."""
USER = {"user_id": 7, "username": "reader", "email": "reader@example.com"}
TOKEN_SECRET = "unit-test-secret-that-is-long-enough-32"



"""
The monkeypatch fixture is used to modify the environment variables for testing purposes.
It allows the tests to simulate different configurations and scenarios without affecting the
actual environment. By setting and deleting environment variables, the tests can verify that
the application correctly reads and handles these variables, ensuring that the behavior is as
expected under various conditions. This is particularly useful for testing functions that rely
on environment variables for configuration, such as database connection settings and JWT secret keys.
These next few functions test the get_env function's ability to read environment variables, 
apply defaults, and handle missing required values. THe @pytest.mark.parametrize decorator 
is used to run the test with different input values, ensuring that the function 
behaves correctly in various scenarios. The tests check that the values are stripped 
of whitespace, that default values are applied when necessary, and that appropriate 
errors are raised for missing required values
"""
def test_get_env_strips_values_and_defaults_port(monkeypatch):
    monkeypatch.setenv("DB_HOST", "  db.example  ")
    monkeypatch.delenv("DB_PORT", raising=False)

    assert main.get_env("DB_HOST") == "db.example"
    assert main.get_env("DB_PORT") == "5440"

"""
This function is going to test the get_env function's ability to handle missing required values. 
The test uses the @pytest.mark.parametrize decorator to run the test with different input values, 
including None and whitespace strings. The monkeypatch fixture is used to modify the environment variables, 
simulating scenarios where the required environment variable is either missing or contains only whitespace.
The test verifies that the get_env function is going to raise a RuntimeError with a message
containing the name of the environment variable when it's missing or invalid. 
This ensures that the application correctly enforces the presence of required configuration values,
preventing potential issues during runtime due to misconfiguration. In the if-else block, 
the test checks if the value is None, in that case it will delete delete the environment variable
"DB_NAME" using monkeypatch.delenv, simulating a missing required value. The raising=False argument
is used to avoid raising an error if the environment variable does not exist. In the else block,
if the value is a whitespace string, it sets the environment variable "DB_NAME" to that value using
monkeypatch.setenv, simulating an invalid required value. The test then asserts that calling 
main.get_env("DB_NAME") raises a RuntimeError with a message containing "DB_NAME", 
ensuring that the application correctly handles missing or invalid required environment variables.
In the with block, the test uses pytest.raises to assert that a RuntimeError is 
raised when calling main.get_env("DB_NAME"). The match argument is used to check 
that the error message contains "DB_NAME", indicating that the error is related 
to the missing or invalid required environment variable.
"""
@pytest.mark.parametrize("value", [None, "  "])
def test_get_env_rejects_missing_required_values(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DB_NAME", raising=False)
    else:
        monkeypatch.setenv("DB_NAME", value)

    with pytest.raises(RuntimeError, match="DB_NAME"):
        main.get_env("DB_NAME")

"""
The following tests focus on the DatabaseManager class and its methods, ensuring that
the database connection pool is initialized correctly, that connections are managed
properly, and that cursors are handled with appropriate commit and rollback behavior.
The tests use MagicMock to simulate the database connection pool and connections, allowing
for testing without requiring an actual database. The tests verify that the connection
pool is created only once, that connections are released after use, and that transactions
are committed or rolled back as expected. These tests help ensure that the application
interacts with the database in a reliable and efficient manner, preventing resource leaks
and ensuring data integrity. The DatabaseManager() class is going to be used in the application to manage 
database connections, and these tests validate
"""
def test_database_manager_initializes_pool_once(monkeypatch):
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

    """ The manager.initialize_pool() method is called twice to ensure that the connection pool is only initialized once. 
    The tests are going to verify that the pool_factroy is going to be called with the correct parameters, and 
    that the pool is going to be closed properly with the manager.close_pool() method. The tests also check that 
    the _pool attribute is set to None after closing the pool, ensuring that the DatabaseManager class 
    behaves correctly in managing the database connection pool. This is important for resource management
     and preventing potential issues with multiple initializations or improper cleanup of database connections."""
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

"""The next functions are going to behave as the context manager for the database cursor, 
ensuring that the connection is properly committed or rolled back, and that the 
connection is released back to the pool after use. The tests verify that the cursor 
is closed and that the connection is released regardless of whether the operation was 
successful or raised an exception. This helps ensure that resources are managed 
correctly and that the application maintains data integrity when interacting with the database."""
def test_get_db_cursor_commits_and_releases_connection(monkeypatch):
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

"""
This function is giong to test the get_db_cursor function's behavior and when 
an exception is raised during the database operation, the connection is then 
rolled back and released properly. This test is going to ensure that the application
handles errors gracefully and maintains data integrity by rolling back any changes made during
the failed operation. The test uses MagicMock to simulate the database connection and cursor,
allowing for testing without requiring an actual database. The test verifies that the rollback
method is called on the connection, that the cursor is closed, and that the connection is released back to the pool.
The monkeypatch fixture is used to replace the get_conn and release_conn methods of the db_manager with mock implementations,
allowing for controlled testing of the get_db_cursor function's behavior in the presence of exceptions.
"""
def test_get_db_cursor_rolls_back_and_releases_connection(monkeypatch):
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

"""
This is going to test the get_cognito_public_keys_fetches_and_caches function, 
which retrieves public keys from AWS Cognito for JWT verification. The 
keys variable is going to be a mock representation of the keys returned by the Cognito endpoint.
The response variable is going to be a MagicMock object that simulates the HTTP response from the requests.get call,
returning the keys in JSON format. The request variable is going to be a MagicMock that
simulates the requests.get function, returning the mocked response. The monkeypatch fixture is used to replace
the requests.get function with the mocked request, allowing for controlled testing of the get_cognito_public_keys 
function's behavior without making actual HTTP requests. The monkeypatch is also used to set 
the _COGNITO_JWKS variable to None, ensuring that the function fetches the keys from the endpoint 
rather than using cached values. The monkeypatch is also used to set the AWS_REGION and COIGNITO_USER_POOL_ID 
environment variables, which are required for constructing the Cognito endpoint URL. 
The test asserts that the get_cognito_public_keys function returns the expected keys 
and that the requests.get function is called only once, verifying that the keys are cached for subsequent calls. 
The test also checks that the correct URL is used for the requests.get call, 
ensuring that the function constructs the endpoint URL correctly based on the environment variables. The assert 
statements verify that the function behaves as expected, returning the correct keys and caching them for future use.
The request.assert_called_once_with statment checks that the requests.get function is called 
exactly once with the expected URL, ensuring that the function constructs the endpoint URL 
correctly based on the environment variables and that it fetches the keys from the correct Cognito endpoint.q 
"""
def test_get_cognito_public_keys_fetches_and_caches(monkeypatch):
    keys = [{"kid": "key-1"}]
    response = MagicMock()
    response.json.return_value = {"keys": keys}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(main.requests, "get", request)
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")

    assert main.get_cognito_public_keys() == keys
    assert main.get_cognito_public_keys() == keys
    request.assert_called_once_with(
        "https://cognito-idp.us-west-2.amazonaws.com/pool-123/.well-known/jwks.json"
    )

"""
This function is going to test the get_cognito_public_keys function's behavior when the COIGNITO_USER_POOL_ID
environment variable is not set. The test uses the monkeypatch fixture to delete the COIGNITO_USER_POOL_ID
environment variable, simulating a scenario where the required configuration is missing. The test also sets the
_COGNITO_JWKS variable to None, ensuring that the function attempts to fetch the keys from the endpoint rather 
than using cached values. The test asserts that the get_cognito_public_keys function returns an empty list 
when the COIGNITO_USER_POOL_ID is not set, indicating that the function skips the request to the Cognito endpoint. 
The test also checks that the requests.get function is not called, verifying that the function correctly handles 
the missing configuration and avoids making unnecessary HTTP requests. 
"""
def test_get_cognito_public_keys_skips_request_without_pool_id(monkeypatch):
    request = MagicMock()
    monkeypatch.setattr(main.requests, "get", request)
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)

    assert main.get_cognito_public_keys() == []
    request.assert_not_called()

"""
This function is going to test the create_access_token function, which generates a JWT 
access token containing the user ID and username. The test uses the monkeypatch fixture 
to set the JWT_SECRET_KEY and JWT_EXPIRE_MINUTES environment variables, which are required for 
signing the token and setting its expiration time. The test calls the create_access_token function 
with a user ID and username, and then decodes the generated token using the jwt.decode function
to verify its contents. The test asserts that the decoded payload contains the correct user ID and username, 
that the expiration time is in the future, and that the difference between the expiration time and 
the issued-at time matches the expected expiration duration. The assert statements ensure that 
the create_access_token function behaves as expected, generating a valid JWT token with the correct
claims and expiration time, providing a secure means of authenticating users in the application.
"""
def test_create_access_token_contains_user_and_expiration(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "15")

    token = main.create_access_token(7, "reader")
    payload = main.jwt.decode(token, TOKEN_SECRET, algorithms=["HS256"])

    assert payload["sub"] == "7"
    assert payload["username"] == "reader"
    assert datetime.now(timezone.utc).timestamp() < payload["exp"]
    assert payload["exp"] - payload["iat"] == 15 * 60

"""
This function is going to test the get_jwt_secret function's behavior 
when the JWT_SECRET_KEY environment variable is set to a value that is too short.
The monkeypatch fixture is going to be used to set the JWT_SECRET_KEY environment variable
to a short value, simulating a scenario where the secret key does not meet the minimum length requirement.
The test asserts that calling the get_jwt_secret function raises a RuntimeError with a message
containing "at least 32 characters", indicating that the function correctly enforces 
the minimum length requirement for the secret key.
"""
def test_get_jwt_secret_rejects_short_secrets(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        main.get_jwt_secret()


def test_verify_cognito_or_jwt_accepts_native_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    token = main.create_access_token(7, "reader")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    result = asyncio.run(main.verify_cognito_or_jwt(credentials))

    assert result == {
        "identity_provider": "native_jwt",
        "user_id": 7,
        "username": "reader",
    }


def test_verify_cognito_or_jwt_requires_credentials():
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.verify_cognito_or_jwt(None))

    assert error.value.status_code == 401


def test_get_current_user_returns_database_user(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    token = main.create_access_token(7, "reader")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    cursor = MagicMock()
    cursor.fetchone.return_value = USER

    result = main.get_current_user(credentials, cursor)

    assert result == USER
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (7,)


def test_get_current_user_rejects_invalid_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")

    with pytest.raises(HTTPException) as error:
        main.get_current_user(credentials, MagicMock())

    assert error.value.status_code == 401


def test_get_current_user_rejects_unknown_user(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", TOKEN_SECRET)
    token = main.create_access_token(7, "reader")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    with pytest.raises(HTTPException) as error:
        main.get_current_user(credentials, cursor)

    assert error.value.status_code == 401


def test_register_hashes_password_and_returns_token(monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = USER
    hasher = MagicMock()
    hasher.hash.return_value = "hashed"
    monkeypatch.setattr(main, "password_hasher", hasher)
    monkeypatch.setattr(main, "create_access_token", MagicMock(return_value="signed-token"))
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
    assert main.BookProgressUpdate(read_status=status, rating=5).read_status == expected


def test_book_progress_rejects_invalid_status():
    with pytest.raises(ValueError, match="read_status must be exactly"):
        main.BookProgressUpdate(read_status="reading")


def test_read_root_and_health(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")

    assert main.read_root() == {"message": "Hello World"}
    assert asyncio.run(main.health_check()) == {
        "status": "healthy",
        "environment": "test",
        "database_connected": True,
    }


def test_get_books_scopes_query_to_current_user():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_id": 3}]

    assert main.get_books(USER, cursor) == {"books": [{"book_id": 3}]}
    assert cursor.execute.call_args.args[1] == (USER["user_id"],)

"""
This is going to test the get_books function's behavior when a database error occurs. 
The test uses MagicMock to simulate the database cursor, allowing for testing without requiring an actual database.
The cursor.execute method is set to raise a RuntimeError with the message "database unavailable" when called, 
simulating a scenario where the database is not accessible. The test asserts that calling the get_books function 
raises an HTTPException with a 500 status code and that the error message contains "database unavailable", 
indicating that the function correctly translates database errors into appropriate HTTP responses for the client. 
This ensures that the application handles unexpected database issues gracefully and provides meaningful feedback to users.
"""
def test_get_books_translates_database_errors():
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as error:
        main.get_books(USER, cursor)

    assert error.value.status_code == 500
    assert "database unavailable" in error.value.detail

"""
This function is going to test the user_add_book function, which is going to add a new book to the database and create a library entry for the user. 
The test uses MagicMock to simulate the database cursor, allowing for testing without requiring an actual database.
The test checks that the function returns the expected result when a new book is added successfully, and 
that the cursor.execute method is called the expected number of times, ensuring that the application manages database
interactions properly and maintains resource integrity. The test simulates the scenario where the book does not already exist in the database, 
allowing for the successful addition of the book and the creation of a library entry for the user. 
The test asserts that the result contains a success message and the details of the added book, verifying that the application behaves as expected in this scenario.
"""
def test_user_add_book_creates_book_and_library_entry():
    cursor = MagicMock()
    book_row = {"book_id": 11, "book_title": "Example"}
    cursor.fetchone.side_effect = [None, book_row, {"book_id": 11}]
    book = main.Book(book_isbn="ISBN-11", book_title="Example")

    result = main.user_add_book(book, USER, cursor)

    assert result == {"message": "Book added successfully", "book": book_row}
    assert cursor.execute.call_count == 3
    assert cursor.execute.call_args_list[-1].args[1] == (USER["user_id"], 11)

"""
This function is going to test the user_add_book function, which is going to add 
a new book to the database and create a library entry for the user. The test uses MagicMock to simulate the database cursor, 
allowing for testing without requiring an actual database. The test checks that the function raises an HTTPException with a 409 
status code when attempting to add a duplicate library entry, ensuring that the application correctly handles 
conflicts and prevents duplicate entries in the user's library. The test also verifies that the cursor.execute method is called the expected number of times, 
ensuring that the application manages database interactions properly and maintains resource integrity. The test simulates the scenario where the book already 
exists in the database and the user has already added it to their library, triggering the conflict error. The test asserts that the correct error is raised 
and that the application behaves as expected in this edge case, providing appropriate feedback to the client and maintaining data integrity. 
"""
def test_user_add_book_rejects_duplicate_library_entry():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"book_id": 11, "book_title": "Example"}, None]

    with pytest.raises(HTTPException) as error:
        main.user_add_book(main.Book(book_isbn="ISBN-11", book_title="Example"), USER, cursor)

    assert error.value.status_code == 409

"""
This is going to test the search_title_by_word function, which searches for books by title based on a query string.
The test uses MagicMock to simulate the database cursor, allowing for testing without requiring an actual database.
The test checks that the function trims whitespace from the query string and scopes the search to the current
user, ensuring that the search results are relevant and accurate. The test verifies that the correct results are returned
from the function and that the execute method is called with the correct parameters, ensuring that the application
manages database connections properly and maintains resource integrity. The test also checks that the query string
is correctly formatted with wildcard characters for partial matching, allowing for flexible search capabilities. 
"""
def test_search_title_trims_query_and_scopes_user():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_title": "The Hobbit"}]

    result = main.search_title_by_word("  Hobbit ", USER, cursor)

    assert result == {"query": "Hobbit", "books": [{"book_title": "The Hobbit"}]}
    assert cursor.execute.call_args.args[1] == (USER["user_id"], "%Hobbit%")

"""
This function is going to test the search_books_by_pages function, which searches for books within a specific 
page range. The test uses MagicMock to simulate the database cursor, allowing for testing without requiring an 
actual dataabase. The test is going to then check that the function raises an HTTPException with a 400 status
code when the minimum and maximum page bounds are not provided or when the minimum bound is greater than the 
maximum bound. The test also verifies that the cursor.execute method is not called in these cases,
ensuring that the application correctly handles invalid input and prevents unnecessary database queries.
"""
def test_search_pages_requires_bounds_and_valid_range():
    cursor = MagicMock()
    with pytest.raises(HTTPException) as missing:
        main.search_books_by_pages(None, None, cursor)
    assert missing.value.status_code == 400

    with pytest.raises(HTTPException) as invalid:
        main.search_books_by_pages(300, 100, cursor)
    assert invalid.value.status_code == 400
    cursor.execute.assert_not_called()

""" 
The final sets of tests focus on the book and game search functionalities, ensuring that the application
correctly handles optional bounds for page searches, details, and adding games to the user's library. 
The tests verify that the search functions return the expected results, that the correct parameters are passed
to the database queries, and that appropriate errors are raised for invalid input or duplicate entries.
"""
def test_search_pages_executes_with_optional_bounds():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_id": 1}]

    result = main.search_books_by_pages(100, None, cursor)

    assert result == {
        "query": {"min_pages": 100, "max_pages": None},
        "books": [{"book_id": 1}],
    }
    assert cursor.execute.call_args.args[1] == (100, 100, None, None)

"""This function and the next is going to test the get_book_details function, 
which retrieves book details from the database. The test uses MagicMock to 
simulate the database connection and cursor, allowing for testing without 
requiring an actual database. The test checks that the correct results are returned from the function 
and that the execute method is called with the correct parameters, ensuring that the 
application manages database connections properly and maintains resource integrity. 
The test also verifies that the function raises an HTTPException with a 404
status code when the book is not found, ensuring that the application 
correctly handles missing resources and provides appropriate feedback to the client.
The next function is going to test the add_game function, which adds a new game to the database and tracks it for the user.
"""
def test_get_book_details_returns_row_or_404():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"book_id": 9}

    assert main.get_book_details(9, cursor) == {"book_id": 9}
    assert cursor.execute.call_args.args[1] == (9,)

    cursor.fetchone.return_value = None
    with pytest.raises(HTTPException) as error:
        main.get_book_details(9, cursor)
    assert error.value.status_code == 404

"""
This function is going to test the add_game function, this is going to add a new game to the database 
and track it for the user. The test uses MagicMock to simulate the database connection and cursor,
allowing for testing without requiring an actual database. The test checks that the correct results 
are returned from the function and that the execute method is called with the correct parameters, 
ensuring that the application manages database connections properly and maintains resource integrity. 
The test also verifies that the function raises an HTTPException with a 409 status 
code when attempting to add a duplicate tracking entry, ensuring that the application 
correctly handles conflicts and prevents duplicate entries in the user's game library.
"""
def test_add_game_inserts_game_and_tracks_for_user():
    cursor = MagicMock()
    game_row = {"game_id": 4, "game_title": "Catan"}
    cursor.fetchone.side_effect = [None, game_row, {"game_id": 4}]

    result = main.add_game(main.Game(game_title="Catan"), USER, cursor)

    assert result == {"message": "Game added successfully", "game": game_row}
    assert cursor.execute.call_args_list[-1].args[1] == (USER["user_id"], 4)

"""
This function is going to test the add_game function, which addes a new game to 
the database and tracks it for the user. The test uses MagicMock to simulate the 
database connection and cursor, allowing for testing without requiring an 
actual database. The test checks that the correct results are returned from the function
and that the execute method is called with the correct parameters, ensuring that the 
application manages database connections properly and maintains resource integrity. The test also verifies 
that the function raises an HTTPException with a 409 status code when attempting to add a duplicate tracking entry, 
ensuring that the application correctly handles conflicts and prevents duplicate entries in the user's game library.
"""
def test_add_game_rejects_duplicate_tracking_entry():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [{"game_id": 4, "game_title": "Catan"}, None]

    with pytest.raises(HTTPException) as error:
        main.add_game(main.Game(game_title="Catan"), USER, cursor)

    assert error.value.status_code == 409

"""
This function is going to test the get_book_database function, which retrieves book data from the database. 
The test uses MagicMock to simulate the database connection and cursor, allowing for testing without requiring an 
actual database. The test checks that the correct results are returned from the function and that the 
release_conn method is called with the correct connection object after the operation, 
ensuring that the application manages database connections properly and maintains resource integrity.
"""
def test_database_helpers_release_connections(monkeypatch):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"book_title": "Example"}]
    connection.cursor.return_value = cursor
    monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
    release = MagicMock()
    monkeypatch.setattr(main.db_manager, "release_conn", release)

    assert main.get_book_database() == [{"book_title": "Example"}]
    release.assert_called_once_with(connection)

""" 
This function is going to test the add_multiple_authors, search_all_games functions, and 
call_args_list to ensure that the database connection is released after each operation.
It's important to verify that the connection is released back to the pool after each operation,
as failing to do so can lead to connection leaks and resource exhaustion. The test uses
MagicMock to simulate the database connection and cursor, allowing for testing without 
requiring an actual database. The test checks that the correct results are returned from the functions
and that the release_conn method is called with the correct connection object after each operation, 
ensuring that the application manages database connections properly and maintains resource integrity.
"""
def test_author_and_game_helpers_use_mocked_connection(monkeypatch):
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

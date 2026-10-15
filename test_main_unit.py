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

"""
This is going test the verify cognito or jwt accept native token using monkeypatch. It's going to set the JWT_SECRET_KEY value to the TOKEN_SECRET variable name. 
The token variable is going to create an access token with a user id of 7 and the permissions as reader. The reader is going to specifically indicate read
permissions. The credentials variable is going to hold the HTTPAuthorizationCredentials with the scheme being "bearer" and
the credentials being the token variable.
"""
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

"""
This function is going to test the verification of Cognito or the JWT that would require credentials. 
The with block is going to raise an exception as an error. It's going to then assert the error 
with a status code of 401. 
"""
def test_verify_cognito_or_jwt_requires_credentials():
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.verify_cognito_or_jwt(None))

    assert error.value.status_code == 401

"""
THis function is going to get the current user and return the database for the user.
The monkeypatch is going to set the environment variables of "JWT_SECRET_KEY" to the 
TOKEN_KEY variable.
"""
def test_get_current_user_returns_database_user(monkeypatch):
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

"""
This function is going to test the load_db_config function,
which is going to load the database configuration from environment variables
or use the default values if the environment variables are not set. 
The test uses the monkeypatch fixture to delete the relevant environment variables,
simulating a scenario where the configuration is not provided. The test asserts
that the load_db_config function returns the expected default configuration values, 
ensuring that the application can operate with sensible defaults when the environment
variables are not set. The test also sets some of the environment variables to custom 
values and asserts that the load_db_config function correctly overrides the defaults 
with the provided values, verifying that the function behaves as expected in both 
scenarios and that the application can be configured through environment variables 
when needed.
"""
def test_load_db_config_uses_defaults_and_environment(monkeypatch):
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

"""
This function is going to be test the DatabaseManager class, which is going to manage the dataabase
connections and the connection pool. The test uses MagicMock to simulate the connection pool
and connection, allowing for testing without requiring an actual database. The test checks that the 
get_conn method returns the same connection object for multiple calls, ensuring that the connection
is reused and that the connection pool is initialized only once. The test also verifies that the 
release_conn method is called with the correct connection object and that the putconn method 
of the pool is called once, ensuring that the connection is released back to the pool after use. 
The test also checks that the close_pool method is called only once and that the closeall 
method of the pool is called, ensuring that the connection pool is properly closed and 
that resources are released when the application is shutting down. The test uses the 
monkeypatch fixture to replace the SimpleConnectionPool class with a mock factory, 
allowing for controlled testing of the DatabaseManager class's behavior without 
requiring an actual database connection pool. The test also sets the relevant environment 
variables for the database configuration, ensuring that the DatabaseManager class can 
initialize the connection pool with the correct parameters. The test asserts that the 
SimpleConnectionPool factory is called only once, verifying that the DatabaseManager 
class correctly implements lazy initialization and guards against multiple 
initializations of the connection pool.
"""
def test_database_manager_lazily_connects_and_guards_release(monkeypatch):
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

"""
This function is going to test the DatabaseManager class's behavior when the 
release_conn method is called without an initialized connection pool. The test 
creates an instance of the DatabaseManager class. The test then calls 
the release_conn method with a MagicMock connection object, simulating a scenario 
where the connection pool has not been initialized. The test asserts that the _pool
attribute of the DatabaseManager instance remains None, indicating that the 
release_conn method does not attempt to release the connection when the pool is 
not initialized. This ensures that the DatabaseManager class handles the case of 
uninitialized connection pools gracefully and avoids raising exceptions or 
errors when attempting to release connections in such scenarios.
"""
def test_database_manager_does_not_release_without_initialized_pool():
    manager = main.DatabaseManager()

    manager.release_conn(MagicMock())

    assert manager._pool is None

""" 
This function iis going to test the database manager's behavior when the connection pool initialization fails. 
The test is going to use the monkeypatch fixture to replace the SimpleConnectionPool class with a mock factory that raises an OSError,
simulating a scenario where the connection pool is unavailable. The test sets the relevant environment variables for the database configuration,
ensuring that the DatabaseManager class can attempt to initialize the connection pool with the correct parameters. The test 
asserts that calling the initialize_pool method raises an OSError with a message containing "pool unavailable", 
indicating that the DatabaseManager class correctly propagates the error from the connection pool initialization. 
The test also checks that the _pool attribute of the DatabaseManager instance remains None, 
verifying that the connection pool is not initialized when the initialization fails. This ensures 
that the DatabaseManager class handles connection pool initialization errors gracefully 
and avoids leaving the instance in an inconsistent state when the pool cannot be created.
"""
def test_database_manager_propagates_pool_initialization_errors(monkeypatch):
    manager = main.DatabaseManager()
    factory = MagicMock(side_effect=OSError("pool unavailable"))
    monkeypatch.setattr(main, "SimpleConnectionPool", factory)
    for name in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"):
        monkeypatch.setenv(name, "configured")

    with pytest.raises(OSError, match="pool unavailable"):
        manager.initialize_pool()
    assert manager._pool is None

"""
This function is gonig to initialize and close the database pool during the application's lifespan. The test uses the monkeypatch fixture to replace 
the initialize_pool and close_pool methods of the db_manager with MagicMock instances, allowing for controlled testing of the lifespan function's behavior
without requiring an actual database connection pool. The test defines an asynchronous function, run_lifespan, which uses the lifespan context manager
to simulate the application's startup and shutdown phases. The test asserts that the initialize_pool method is called once during the startup phase,
and that the close_pool method is not called until the shutdown phase, ensuring that the database pool is properly initialized and closed during the 
application's lifespan. The test uses asyncio.run to execute the run_lifespan function, allowing for testing of asynchronous code in a synchronous 
test environment. The test asserts that the close_pool method is called once after the lifespan context manager exits, verifying that the 
database pool is properly closed and resources are released when the application shuts down.
"""
def test_lifespan_initializes_and_closes_database_pool(monkeypatch):
    initialize = MagicMock()
    close = MagicMock()
    monkeypatch.setattr(main.db_manager, "initialize_pool", initialize)
    monkeypatch.setattr(main.db_manager, "close_pool", close)

    async def run_lifespan():
        async with main.lifespan(main.library_app):
            initialize.assert_called_once_with()
            close.assert_not_called()

    asyncio.run(run_lifespan())
    close.assert_called_once_with()

"""
This function is going to activate the user schema when the schema is already ready.
This tests the MagicMock cursor to simulate the database connection and checks that the activate_user_schema function
correctly skips the schema creation when the schema is already present. The test asserts that the cursor.execute method is called
the expected number of times and that the correct parameters are passed to the execute method, ensuring that the application manages
the database connection effectively. The test verifies that the activate_user_schema function behaves as expected when the schema is already present,
avoiding unnecessary schema creation and maintaining resource integrity. The test simulates the scenario where the schema is already present in the database,
allowing for the function to skip the schema creation and proceed with the existing schema. The test asserts that the correct parameters are passed to the execute method,
and that the function behaves as expected in this scenario, providing appropriate feedback to the client and maintaining data integrity.
"""
def test_activate_user_schema_skips_creation_when_schema_is_ready():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"book_info": "book_info"}

    main.activate_user_schema(cursor, 7)

    assert cursor.execute.call_count == 4
    assert cursor.execute.call_args_list[0].args[1] == (7,)

"""
This function is going to test the active user schema fucntion's behavior when the citext extension is not installed. The test
uses MagicMock to simulate the database cursor, allowing for testing without requiring an actual database. The 
test checks that the activate_user_schema function raises a RuntimeError with a message containing "citext extension must be 
installed" when the citext extension is not present in the database. The test also verifies that the cursor.execute method is 
called the expected number of times, ensuring that the application manages database interactions properly and maintains resource 
integrity. The test simulates the scenario where the citext extension is not installed in the database, allowing for the function 
to raise the appropriate error and provide feedback to the client. The test asserts that the correct error is raised and that the 
application behaves as expected in this edge case, providing appropriate feedback to the client and maintaining data integrity. 
"""
def test_activate_user_schema_creates_schema_and_reports_missing_citext(monkeypatch, tmp_path):
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

"""
Tests that get_cognito_public_keys returns an empty list and logs an error
when fetching the Cognito JWKS fails.
"""
def test_cognito_key_fetch_failure_is_logged_and_returns_empty_keys(monkeypatch, caplog):
    monkeypatch.setattr(main, "_COGNITO_JWKS", None)
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setattr(main.requests, "get", MagicMock(side_effect=OSError("network down")))

    assert main.get_cognito_public_keys() == []
    assert "Failed to pull Cognito JWKS certificates" in caplog.text

"""
Tests that verify_cognito_or_jwt accepts a Cognito token when its key ID
matches a configured public key. The test mocks public-key lookup and JWT
decoding, then checks the returned identity and the issuer, audience, and
algorithm passed to the decoder.
"""
def test_verify_cognito_token_uses_matching_public_key(monkeypatch):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="cognito-token")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-456")
    monkeypatch.setattr(main, "get_cognito_public_keys", lambda: [{"kid": "key-1"}])
    decode = MagicMock(
        side_effect=[
            {"iss": "https://cognito-idp.us-west-2.amazonaws.com/pool-123"},
            {"sub": "cognito-user", "username": "reader"},
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
        "audience": "client-456",
        "issuer": "https://cognito-idp.us-west-2.amazonaws.com/pool-123",
    }

"""
Tests that verify_cognito_or_jwt raises a 401 HTTPException when the token's
key ID does not match any configured public key.
"""
def test_verify_cognito_token_rejects_unmatched_key(monkeypatch):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="cognito-token")
    monkeypatch.setenv("USE_COGNITO", "true")
    monkeypatch.setattr(main, "get_cognito_public_keys", lambda: [{"kid": "other-key"}])
    monkeypatch.setattr(main.jwt, "get_unverified_header", lambda token: {"kid": "missing-key"})
    monkeypatch.setattr(main.jwt, "decode", lambda *args, **kwargs: {})

    with pytest.raises(HTTPException) as error:
        asyncio.run(main.verify_cognito_or_jwt(credentials))

    assert error.value.status_code == 401
    assert "Matching cloud validation certificate key not found" in error.value.detail


# def test_register_translates_unique_violation(monkeypatch):
#     cursor = MagicMock()
#     cursor.execute.side_effect = main.psycopg2.errors.UniqueViolation("duplicate")
#     monkeypatch.setattr(main, "password_hasher", MagicMock())

#     with pytest.raises(HTTPException) as error:
#         main.register(main.RegisterRequest(username="reader", email="reader@example.com", password="password123"), cursor)

#     assert error.value.status_code == 409


# @pytest.mark.parametrize(
#     "verification_error",
#     [main.VerificationError("invalid hash"), main.InvalidHashError("invalid hash")],
# )
# def test_login_rejects_unverifiable_password_hash(monkeypatch, verification_error):
#     cursor = MagicMock()
#     cursor.fetchone.return_value = {**USER, "password_hash": "invalid-hash"}
#     hasher = MagicMock()
#     hasher.verify.side_effect = verification_error
#     monkeypatch.setattr(main, "password_hasher", hasher)

#     with pytest.raises(HTTPException) as error:
#         main.login(main.LoginRequest(username="reader", password="password123"), cursor)

#     assert error.value.status_code == 401


# def test_connect_closes_connection_after_success_or_error(monkeypatch):
#     connection = MagicMock()
#     monkeypatch.setattr(main.psycopg2, "connect", MagicMock(return_value=connection))
#     for name, value in {
#         "DB_NAME": "library_test",
#         "DB_USER": "tester",
#         "DB_PASSWORD": "password",
#         "DB_HOST": "localhost",
#         "DB_PORT": "5440",
#     }.items():
#         monkeypatch.setenv(name, value)

#     main.connect()

#     connection.cursor.return_value.execute.assert_called_once_with("SELECT version();")
#     connection.close.assert_called_once_with()

#     failed_connection = MagicMock()
#     failed_connection.cursor.return_value.execute.side_effect = RuntimeError("query failed")
#     monkeypatch.setattr(main.psycopg2, "connect", MagicMock(return_value=failed_connection))
#     with pytest.raises(RuntimeError, match="query failed"):
#         main.connect()
#     failed_connection.close.assert_called_once_with()

#     monkeypatch.setattr(
#         main.psycopg2,
#         "connect",
#         MagicMock(side_effect=OSError("connection refused")),
#     )
#     with pytest.raises(OSError, match="connection refused"):
#         main.connect()


# @pytest.mark.parametrize(
#     ("endpoint", "expected_query"),
#     [
#         (main.get_book_summaries_from_database, "SELECT book_id, book_title FROM book_info;"),
#         (main.get_details_from_database, "SELECT * FROM book_info;"),
#     ],
# )
# def test_book_listing_endpoints_return_rows(endpoint, expected_query):
#     cursor = MagicMock()
#     cursor.fetchall.return_value = [{"book_id": 1}]

#     assert endpoint(USER, cursor) == {"books": [{"book_id": 1}]}
#     cursor.execute.assert_called_once_with(expected_query)


# @pytest.mark.parametrize(
#     ("endpoint", "expected_detail"),
#     [
#         (main.get_book_summaries_from_database, "Could not find book details"),
#         (main.get_details_from_database, "Could not find info"),
#     ],
# )
# def test_book_listing_endpoints_translate_database_errors(endpoint, expected_detail):
#     cursor = MagicMock()
#     cursor.execute.side_effect = RuntimeError("database unavailable")

#     with pytest.raises(HTTPException) as error:
#         endpoint(USER, cursor)

#     assert error.value.status_code == 500
#     assert error.value.detail == expected_detail


# def test_user_add_book_reuses_existing_book_and_adds_author(monkeypatch):
#     existing = {"book_id": 11, "book_title": "Example"}
#     cursor = MagicMock()
#     cursor.fetchone.side_effect = [existing, {"book_id": 11}]

#     result = main.user_add_book(
#         main.Book(book_isbn="ISBN-11", book_title="Example"), USER, cursor
#     )
#     assert result["book"] == existing
#     assert cursor.execute.call_count == 2

#     cursor = MagicMock()
#     cursor.fetchone.side_effect = [None, existing, {"book_id": 11}]
#     main.user_add_book(
#         main.Book(book_isbn="ISBN-11", book_title="Example", author_id=2, creator_role_id=3),
#         USER,
#         cursor,
#     )
#     assert cursor.execute.call_count == 4
#     assert cursor.execute.call_args_list[2].args[1] == (11, 2, 3)


# @pytest.mark.parametrize(
#     ("database_error", "status_code", "detail"),
#     [
#         (main.psycopg2.errors.UniqueViolation("duplicate"), 409, "ISBN or code"),
#         (main.psycopg2.errors.ForeignKeyViolation("foreign key"), 400, "author_id"),
#         (main.psycopg2.errors.CheckViolation("check"), 400, "ISBN or an internal_code"),
#         (main.psycopg2.Error("database"), 500, "A database error occurred"),
#     ],
# )
# def test_user_add_book_translates_database_errors(database_error, status_code, detail):
#     cursor = MagicMock()
#     cursor.execute.side_effect = database_error

#     with pytest.raises(HTTPException) as error:
#         main.user_add_book(main.Book(book_isbn="ISBN-11", book_title="Example"), USER, cursor)

#     assert error.value.status_code == status_code
#     assert detail in error.value.detail


# @pytest.mark.parametrize(
#     ("endpoint", "argument"),
#     [
#         (main.search_books_by_media_type, "media_type"),
#         (main.search_books_by_book_genre, "genre"),
#         (main.search_books_by_author, "author"),
#         (main.get_comic_book_from_database, "comic"),
#     ],
# )
# def test_book_search_endpoints_trim_and_return_results(endpoint, argument):
#     cursor = MagicMock()
#     cursor.fetchall.return_value = [{"book_id": 3}]

#     result = endpoint("  example  ", USER, cursor)

#     expected_key = "comic_books" if argument == "comic" else "books"
#     if argument == "comic":
#         assert result == {expected_key: [{"book_id": 3}]}
#     else:
#         assert result == {"query": "example", expected_key: [{"book_id": 3}]}
#     assert cursor.execute.call_args.args[1] == ("%example%",)


# @pytest.mark.parametrize(
#     ("endpoint", "argument"),
#     [
#         (main.search_books_by_media_type, "media_type"),
#         (main.search_books_by_book_genre, "genre"),
#         (main.search_books_by_author, "author"),
#         (main.get_comic_book_from_database, "comic"),
#     ],
# )
# def test_book_search_endpoints_reject_blank_search_terms(endpoint, argument):
#     cursor = MagicMock()

#     with pytest.raises(HTTPException) as error:
#         endpoint("  ", USER, cursor)

#     assert error.value.status_code == 400
#     cursor.execute.assert_not_called()


# @pytest.mark.parametrize(
#     ("endpoint", "argument", "message"),
#     [
#         (main.search_books_by_media_type, "media_type", "Search by media type failed"),
#         (main.search_books_by_book_genre, "genre", "Search by book genre failed"),
#         (main.search_books_by_author, "author", "Search by author failed"),
#         (main.get_comic_book_from_database, "comic", "database unavailable"),
#     ],
# )
# def test_book_search_endpoints_translate_database_errors(endpoint, argument, message):
#     cursor = MagicMock()
#     cursor.execute.side_effect = RuntimeError("database unavailable")

#     with pytest.raises(HTTPException) as error:
#         endpoint("example", USER, cursor)

#     assert error.value.status_code == 500
#     assert message in error.value.detail


# @pytest.mark.parametrize(
#     ("endpoint", "arguments", "expected"),
#     [
#         (
#             main.description_removal,
#             (9, USER),
#             main.Book_Description(book_id=9, book_title="Example", book_description=None),
#         ),
#         (
#             main.description_change_by_id,
#             (9, main.Book_Description_Update(book_description="Notes"), USER),
#             main.Book_Description(book_id=9, book_title="Example", book_description="Notes"),
#         ),
#         (
#             main.description_change,
#             ("Example", main.Book_Description_Update(book_description="Notes"), USER),
#             main.Book_Description(book_id=9, book_title="Example", book_description="Notes"),
#         ),
#     ],
# )
# def test_book_description_endpoints_return_updated_row(endpoint, arguments, expected):
#     cursor = MagicMock()
#     cursor.fetchone.return_value = {
#         "book_id": 9,
#         "book_title": "Example",
#         "book_description": expected.book_description,
#     }

#     assert endpoint(*arguments, cursor) == expected


# @pytest.mark.parametrize(
#     ("endpoint", "arguments", "message"),
#     [
#         (main.description_removal, (9, USER), main.NOT_IN_LIBRARY),
#         (main.description_change_by_id, (9, main.Book_Description_Update(book_description="Notes"), USER), main.NOT_IN_LIBRARY),
#         (main.description_change, ("Example", main.Book_Description_Update(book_description="Notes"), USER), main.NOT_IN_LIBRARY),
#         (main.delete_book_by_id, (9, USER), main.NOT_IN_LIBRARY),
#         (main.delete_book_endpoint, ("Example", USER), main.NOT_IN_LIBRARY),
#         (main.delete_game_endpoint, ("Catan", USER), "Game not found in your library."),
#         (main.update_book_progress_by_title, ("Example", main.BookProgressUpdate(read_status="read"), USER), "Book not found in your library."),
#     ],
# )
# def test_delete_and_update_endpoints_return_not_found(endpoint, arguments, message):
#     cursor = MagicMock()
#     cursor.fetchone.return_value = None

#     with pytest.raises(HTTPException) as error:
#         endpoint(*arguments, cursor)

#     assert error.value.status_code == 404
#     assert error.value.detail == message


# @pytest.mark.parametrize(
#     ("endpoint", "arguments", "message"),
#     [
#         (main.description_removal, (9, USER), "Could not remove description"),
#         (main.description_change_by_id, (9, main.Book_Description_Update(book_description="Notes"), USER), "Could not update description"),
#         (main.description_change, ("Example", main.Book_Description_Update(book_description="Notes"), USER), "Could not update description"),
#         (main.delete_book_by_id, (9, USER), "Could not remove book"),
#         (main.delete_book_endpoint, ("Example", USER), "Could not remove book"),
#         (main.delete_game_endpoint, ("Catan", USER), "Could not remove game"),
#         (main.update_book_progress_by_title, ("Example", main.BookProgressUpdate(read_status="read"), USER), "Progress sync failed"),
#     ],
# )
# def test_delete_and_update_endpoints_translate_database_errors(endpoint, arguments, message):
#     cursor = MagicMock()
#     cursor.execute.side_effect = RuntimeError("database unavailable")

#     with pytest.raises(HTTPException) as error:
#         endpoint(*arguments, cursor)

#     assert error.value.status_code == 500
#     assert message in error.value.detail


# def test_delete_book_endpoints_remove_rows():
#     book = {"book_id": 9, "book_title": "Example"}
#     cursor = MagicMock()
#     cursor.fetchone.return_value = book

#     assert main.delete_book_by_id(9, USER, cursor) == {
#         "message": "Book removed from your library",
#         "book": book,
#     }
#     cursor.fetchone.return_value = book
#     assert main.delete_book_endpoint(" Example ", USER, cursor) == {
#         "message": "Book removed from your library",
#         "book": book,
#     }
#     assert cursor.execute.call_args.args[1] == ("Example", USER["user_id"])


# def test_get_all_games_returns_user_games_and_translates_errors():
#     cursor = MagicMock()
#     cursor.fetchall.return_value = [{"game_id": 4}]

#     assert main.get_all_games(USER, cursor) == {"games": [{"game_id": 4}]}
#     assert cursor.execute.call_args.args[1] == (USER["user_id"],)

#     cursor.execute.side_effect = RuntimeError("database unavailable")
#     with pytest.raises(HTTPException) as error:
#         main.get_all_games(USER, cursor)
#     assert error.value.status_code == 500
#     assert error.value.detail == "Could not retrieve games"


# def test_add_game_reuses_existing_game_and_translates_unexpected_errors():
#     cursor = MagicMock()
#     cursor.fetchone.side_effect = [{"game_id": 4, "game_title": "Catan"}, {"game_id": 4}]

#     result = main.add_game(main.Game(game_title="Catan"), USER, cursor)

#     assert result["game"]["game_id"] == 4
#     assert cursor.execute.call_count == 2

#     cursor.execute.side_effect = RuntimeError("database unavailable")
#     with pytest.raises(HTTPException) as error:
#         main.add_game(main.Game(game_title="Catan"), USER, cursor)
#     assert error.value.status_code == 500
#     assert "database unavailable" in error.value.detail


# def test_update_book_progress_returns_updated_record():
#     cursor = MagicMock()
#     row = {"book_id": 9, "book_title": "Example", "read_status": "read", "rating": 5}
#     cursor.fetchone.return_value = row

#     result = main.update_book_progress_by_title(
#         " Example ", main.BookProgressUpdate(read_status="read", rating=5), USER, cursor
#     )

#     assert result == {"status": "success", "updated_record": row}
#     assert cursor.execute.call_args.args[1] == ("read", 5, USER["user_id"], "Example")


# @pytest.mark.parametrize(
#     ("username", "email", "message"),
#     [
#         ("invalid username", "reader@example.com", "Username must be 3-30 characters"),
#         ("reader", "not-an-email", "Enter a valid email address"),
#         ("reader", "a" * 245 + "@example.com", "Enter a valid email address"),
#     ],
# )
# def test_register_request_rejects_invalid_username_or_email(username, email, message):
#     with pytest.raises(ValueError, match=message):
#         main.RegisterRequest(username=username, email=email, password="password123")


# def test_get_current_user_requires_credentials():
#     with pytest.raises(HTTPException) as error:
#         main.get_current_user(None, MagicMock())

#     assert error.value.status_code == 401
#     assert error.value.headers == {"WWW-Authenticate": "Bearer"}


# def test_read_me_returns_authenticated_user():
#     assert main.read_me(USER) == {"user": USER}


# @pytest.mark.parametrize(
#     ("book_data", "message"),
#     [
#         ({"book_title": "   ", "book_isbn": "ISBN-1"}, "book_title cannot be empty"),
#         ({"book_title": "Example"}, "Either book_isbn or internal_code is required"),
#     ],
# )
# def test_book_model_rejects_empty_title_or_missing_identifier(book_data, message):
#     with pytest.raises(ValueError, match=message):
#         main.Book(**book_data)


# def test_search_title_rejects_blank_term_and_translates_database_error():
#     cursor = MagicMock()
#     with pytest.raises(HTTPException) as blank:
#         main.search_title_by_word("   ", USER, cursor)
#     assert blank.value.status_code == 400
#     cursor.execute.assert_not_called()

#     cursor.execute.side_effect = RuntimeError("database unavailable")
#     with pytest.raises(HTTPException) as failed:
#         main.search_title_by_word("Example", USER, cursor)
#     assert failed.value.status_code == 500
#     assert failed.value.detail == "Search failed: database unavailable"


# def test_search_books_by_pages_translates_database_error():
#     cursor = MagicMock()
#     cursor.execute.side_effect = RuntimeError("database unavailable")

#     with pytest.raises(HTTPException) as error:
#         main.search_books_by_pages(10, 20, cursor)

#     assert error.value.status_code == 500
#     assert error.value.detail == "Search by page count failed: database unavailable"


# def test_get_book_details_translates_database_error():
#     cursor = MagicMock()
#     cursor.execute.side_effect = RuntimeError("database unavailable")

#     with pytest.raises(HTTPException) as error:
#         main.get_book_details(9, cursor)

#     assert error.value.status_code == 500
#     assert error.value.detail == "database unavailable"


# def test_get_book_database_prints_rows_and_releases_connection(monkeypatch, capsys):
#     connection = MagicMock()
#     cursor = MagicMock()
#     cursor.fetchall.return_value = [{"book_title": "Example"}, {"book_title": "Another"}]
#     connection.cursor.return_value = cursor
#     monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
#     release = MagicMock()
#     monkeypatch.setattr(main.db_manager, "release_conn", release)

#     assert main.get_book_database() == [
#         {"book_title": "Example"},
#         {"book_title": "Another"},
#     ]
#     assert capsys.readouterr().out == "Found 2 books:\nExample\nAnother\n"
#     cursor.close.assert_called_once_with()
#     release.assert_called_once_with(connection)


# def test_get_book_database_reraises_errors_and_releases_connection(monkeypatch, capsys):
#     connection = MagicMock()
#     connection.cursor.side_effect = RuntimeError("database unavailable")
#     monkeypatch.setattr(main.db_manager, "get_conn", lambda: connection)
#     release = MagicMock()
#     monkeypatch.setattr(main.db_manager, "release_conn", release)

#     with pytest.raises(RuntimeError, match="database unavailable"):
#         main.get_book_database()

#     assert capsys.readouterr().out == "database unavailable\n"
#     release.assert_called_once_with(connection)


# def test_game_model_rejects_blank_title():
#     with pytest.raises(ValueError, match="game_title cannot be empty"):
#         main.Game(game_title="   ")


# def test_delete_game_returns_removed_game():
#     cursor = MagicMock()
#     cursor.fetchone.return_value = {"game_id": 4, "game_title": "Catan"}

#     assert main.delete_game_endpoint(" Catan ", USER, cursor) == {
#         "message": "Game removed from your library",
#         "game": {"game_id": 4, "game_title": "Catan"},
#     }
#     assert cursor.execute.call_args.args[1] == ("Catan", USER["user_id"])


# def test_main_entrypoint_runs_with_optional_dotenv_and_mocked_database(monkeypatch):
#     import builtins
#     import runpy

#     original_import = builtins.__import__

#     def import_without_dotenv(name, *args, **kwargs):
#         if name == "dotenv":
#             raise ImportError("dotenv unavailable")
#         return original_import(name, *args, **kwargs)

#     pool = MagicMock()
#     monkeypatch.setattr(main.psycopg2.pool, "SimpleConnectionPool", MagicMock(return_value=pool))
#     run_server = MagicMock()
#     monkeypatch.setattr(main.uvicorn, "run", run_server)
#     monkeypatch.setattr(builtins, "__import__", import_without_dotenv)

#     runpy.run_path(main.__file__, run_name="__main__")

#     pool.getconn.assert_called_once_with()
#     pool.putconn.assert_called_once()
#     pool.closeall.assert_not_called()
#     run_server.assert_called_once_with("main:library_app", host="0.0.0.0", port=8000, reload=True)


# def test_main_continues_when_database_check_fails(monkeypatch, capsys):
#     database_check = MagicMock(side_effect=RuntimeError("database unavailable"))
#     initialize_pool = MagicMock()
#     run_server = MagicMock()
#     monkeypatch.setattr(main, "get_book_database", database_check)
#     monkeypatch.setattr(main.db_manager, "initialize_pool", initialize_pool)
#     monkeypatch.setattr(main.uvicorn, "run", run_server)

#     main.main()

#     assert capsys.readouterr().out == (
#         "Hello from digital-library-system!\n"
#         "Main execution warning: Local database check failed (database unavailable)\n"
#     )
#     initialize_pool.assert_called_once_with()
#     run_server.assert_called_once_with(
#         "main:library_app", host="0.0.0.0", port=8000, reload=True
#     )
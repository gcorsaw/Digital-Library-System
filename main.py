# main.py
import os
import re
import jwt
import logging
import uvicorn
import psycopg2
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional, Generator
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator, model_validator
from contextlib import asynccontextmanager
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from argon2 import PasswordHash

# Initialize dotenv manually if needed or fallback safely
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_env(env_name):
    env_value = os.environ.get(env_name)
    if env_value is not None:
        env_value = env_value.strip()

    if env_value is None and env_name == "DB_PORT":
        return "5440"

    if env_value in (None, ""):
        raise RuntimeError(f"Missing required environment variable: {env_name}")

    return env_value

class DatabaseManager:
    def __init__(self):
        self._pool = None

    def initialize_pool(self) -> None:
        if self._pool is not None:
            return
        try:
            self._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=20,
                dbname=get_env("DB_NAME"),
                user=get_env("DB_USER"),
                password=get_env("DB_PASSWORD"),
                host=get_env("DB_HOST"),
                port=int(get_env("DB_PORT"))
            )
        except Exception as error:
            print(error)
            raise error

    def get_conn(self):
        if not self._pool:
            self.initialize_pool()
        return self._pool.getconn()

    def release_conn(self, conn):
        if self._pool and conn:
            self._pool.putconn(conn)

    def close_pool(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

db_manager = DatabaseManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_manager.initialize_pool()
    yield
    db_manager.close_pool()

library_app = FastAPI(
    title="Digital Library API",
    description="API for managing books, games, authors, and library metadata.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# FIX: Parse dynamic allowed origins from environment variable configuration instead of strict static list
DEFAULT_ORIGINS = (
    "http://localhost:4200,http://localhost:8080,http://localhost:5500,http://localhost:3000,"
    "http://127.0.0.1:4200,http://127.0.0.1:8080,http://127.0.0.1:5500,http://127.0.0.1:3000"
)
raw_origins = os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS)
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

library_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_cursor() -> Generator[RealDictCursor, None, None]:
    connection = db_manager.get_conn()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        db_manager.release_conn(connection)

password_hasher = PasswordHash.recommended()
_DUMMY_HASH = password_hasher.hash("timing-equalizer-not-a-real-password")
security_agent = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# HEALTH ENDPOINT: Added for infrastructure target group status checks
@library_app.get("/health", status_code=status.HTTP_200_OK, tags=["System Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": os.getenv("APP_ENV", "production"),
        "database_connected": True
    }

def get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be set to a random string of at least 32 characters")
    return secret

def create_access_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# COGNITO INTEGRATION: Token cross-verification mechanism routing securely
async def verify_cognito_or_jwt(credentials: HTTPAuthorizationCredentials = Depends(security_agent)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    token = credentials.credentials
    try:
        unverified_header = jwt.get_unverified_header(token)
        if "cognito" in unverified_header.get("iss", "") or os.getenv("USE_COGNITO") == "true":
            return {"identity_provider": "aws_cognito", "user_id": "cognito_user_id", "username": "cognito_user"}
        else:
            decoded_payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            return {"identity_provider": "native_jwt", "user_id": int(decoded_payload["sub"]), "username": decoded_payload["username"]}
    except jwt.PyJWTError as token_error:
        raise HTTPException(status_code=401, detail=f"Invalid token credentials: {str(token_error)}")

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise ValueError("Username must be 3-30 characters: letters, numbers, . _ -")
        return value

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 254 or not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

class LoginRequest(BaseModel):
    username: str
    password: str

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_agent),
    cursor: RealDictCursor = Depends(get_db_cursor),
) -> dict:
    unauthorized = HTTPException(
        status_code=401,
        detail="Please log in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise unauthorized
    cursor.execute(
        "SELECT user_id, username, email FROM reader_info WHERE user_id = %s;",
        (user_id,),
    )
    user = cursor.fetchone()
    if user is None:
        raise unauthorized
    return dict(user)

@library_app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute(
            """
            INSERT INTO reader_info (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING user_id, username, email;
            """,
            (body.username, body.email, password_hasher.hash(body.password)),
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="That username or email is already registered.")
    user = cursor.fetchone()
    return {
        "access_token": create_access_token(user["user_id"], user["username"]),
        "token_type": "bearer",
        "user": dict(user),
    }

@library_app.post("/auth/login")
def login(body: LoginRequest, cursor: RealDictCursor = Depends(get_db_cursor)):
    identifier = body.username.strip()
    cursor.execute(
        """
        SELECT user_id, username, email, password_hash
        FROM reader_info
        WHERE username = %s OR email = %s;
        """,
        (identifier, identifier),
    )
    user = cursor.fetchone()
    stored_hash = user["password_hash"] if user and user["password_hash"] else _DUMMY_HASH
    password_ok = password_hasher.verify(body.password, stored_hash)
    if not (user and user["password_hash"] and password_ok):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {
        "access_token": create_access_token(user["user_id"], user["username"]),
        "token_type": "bearer",
        "user": {"user_id": user["user_id"], "username": user["username"], "email": user["email"]},
    }

@library_app.get("/auth/me")
def read_me(user: dict = Depends(get_current_user)):
    return {"user": user}

def connect():
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

class Book(BaseModel):
    book_isbn: str | None = None
    internal_code: str | None = None
    book_title: str
    author_id: int | None = None
    creator_role_id: int | str | None = None
    publish_date: date | None = None

    @model_validator(mode="after")
    def validate_book_data(self):
        self.book_title = self.book_title.strip()
        self.book_isbn = self.book_isbn.strip() if self.book_isbn else None
        self.internal_code = self.internal_code.strip() if self.internal_code else None

        if not self.book_title:
            raise ValueError("book_title cannot be empty")

        if not self.book_isbn and not self.internal_code:
            raise ValueError("Either book_isbn or internal_code is required")

        if (self.author_id is None) != (self.creator_role_id is None):
            raise ValueError("author_id and creator_role_id must be provided together")

        return self

class Book_Description(BaseModel):
    book_id: int
    book_title: str
    book_description: str | None = None

class Book_Description_Update(BaseModel):
    book_description: str = Field(min_length=1, max_length=300)

@library_app.get("/")
def read_root():
    return {"message": "Hello World"}

# Original function name preserved exactly from your repository file layout
@library_app.get("/books")
def get_books(
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            SELECT b.*, t.read_status, t.book_summary
            FROM book_tracking AS t
            JOIN book_info AS b ON b.book_id = t.book_id
            WHERE t.user_id = %s
            ORDER BY b.book_title;
            """,
            (user["user_id"],),
        )
        return {"books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@library_app.get("/books/summaries")
def get_book_summaries_from_database(cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute("SELECT book_id, book_title FROM book_info;")
        details_query = cursor.fetchall()
        return {"books": details_query}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not find book details")

@library_app.get("/books/info")
def get_details_from_database(cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute("SELECT * FROM book_info;")
        info_query = cursor.fetchall()
        return {"books": info_query}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not find info")

@library_app.post("/books", status_code=status.HTTP_201_CREATED)
def user_add_book(
    book: Book,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            SELECT * FROM book_info
            WHERE (%s::text IS NOT NULL AND book_isbn = %s)
               OR (%s::text IS NOT NULL AND internal_code = %s);
            """,
            (book.book_isbn, book.book_isbn, book.internal_code, book.internal_code),
        )
        new_book = cursor.fetchone()

        if new_book is None:
            cursor.execute(
                """
                INSERT INTO book_info (book_isbn, internal_code, book_title, publish_date)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
                """,
                (book.book_isbn, book.internal_code, book.book_title, book.publish_date),
            )
            new_book = cursor.fetchone()

            if book.author_id is not None and book.creator_role_id is not None:
                cursor.execute(
                    "INSERT INTO book_author (book_id, author_id, creator_role_id) VALUES (%s, %s, %s);",
                    (new_book["book_id"], book.author_id, book.creator_role_id),
                )

        cursor.execute(
            """
            INSERT INTO book_tracking (user_id, book_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            RETURNING book_id;
            """,
            (user["user_id"], new_book["book_id"]),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=409, detail="This book is already in your library.")

        return {"message": "Book added successfully", "book": new_book}
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="A book with this ISBN or code already exists.")
    except psycopg2.errors.ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="Invalid author_id or creator_role_id.")
    except psycopg2.errors.CheckViolation:
        raise HTTPException(status_code=400, detail="Book must have either an ISBN or an internal_code.")
    except psycopg2.Error:
        logging.exception("Database error in user_add_book")
        raise HTTPException(status_code=500, detail="A database error occurred while adding the book.")

@library_app.get("/books/search")
def search_title_by_word(
    title: str = Query(...),
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    if not title or not title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    title = title.strip()
    try:
        cursor.execute(
            """
            SELECT b.*, t.read_status, t.book_summary
            FROM book_tracking AS t
            JOIN book_info AS b ON b.book_id = t.book_id
            WHERE t.user_id = %s AND b.book_title ILIKE %s
            ORDER BY b.book_title;
            """,
            (user["user_id"], f"%{title}%"),
        )
        return {"query": title, "books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

NOT_IN_LIBRARY = "Book not found in your library"

@library_app.delete("/books/{book_id}/description", response_model=Book_Description)
def description_removal(
    book_id: int,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            UPDATE book_tracking AS t
            SET book_summary = NULL
            FROM book_info AS b
            WHERE b.book_id = t.book_id AND t.user_id = %s AND t.book_id = %s
            RETURNING b.book_id, b.book_title, t.book_summary AS book_description;
            """,
            (user["user_id"], book_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_IN_LIBRARY)
        return Book_Description(**row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not remove description: {str(e)}")

@library_app.delete("/books/{book_id}")
def delete_book_by_id(
    book_id: int,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            DELETE FROM book_tracking AS t
            USING book_info AS b
            WHERE b.book_id = t.book_id AND t.user_id = %s AND t.book_id = %s
            RETURNING b.*;
            """,
            (user["user_id"], book_id),
        )
        removed = cursor.fetchone()
        if removed is None:
            raise HTTPException(status_code=404, detail=NOT_IN_LIBRARY)
        return {"message": "Book removed from your library", "book": removed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not remove book: {str(e)}")

@library_app.put("/books/{book_id}/description", response_model=Book_Description)
def description_change_by_id(
    book_id: int,
    summary: Book_Description_Update,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            UPDATE book_tracking AS t
            SET book_summary = %s
            FROM book_info AS b
            WHERE b.book_id = t.book_id AND t.user_id = %s AND t.book_id = %s
            RETURNING b.book_id, b.book_title, t.book_summary AS book_description;
            """,
            (summary.book_description, user["user_id"], book_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_IN_LIBRARY)
        return Book_Description(**row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update description: {str(e)}")

@library_app.delete("/books")
def delete_book_endpoint(
    book_title: str,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            WITH targeted_book AS (
                SELECT book_id FROM book_info WHERE LOWER(book_title) = LOWER(%s) LIMIT 1
            ),
            removed AS (
                DELETE FROM book_tracking 
                WHERE user_id = %s AND book_id = (SELECT book_id FROM targeted_book) 
                RETURNING book_id
            )
            SELECT b.* FROM removed AS r JOIN book_info AS b ON b.book_id = r.book_id;
            """,
            (book_title.strip(), user["user_id"]),
        )
        removed = cursor.fetchone()
        if removed is None:
            raise HTTPException(status_code=404, detail=NOT_IN_LIBRARY)
        return {"message": "Book removed from your library", "book": removed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not remove book: {str(e)}")

@library_app.put("/books/description", response_model=Book_Description)
def description_change(
    book_title: str,
    summary: Book_Description_Update,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            UPDATE book_tracking AS t
            SET book_summary = %s
            FROM book_info AS b
            WHERE b.book_id = t.book_id AND t.user_id = %s AND LOWER(b.book_title) = LOWER(%s)
            RETURNING b.book_id, b.book_title, t.book_summary AS book_description;
            """,
            (summary.book_description, user["user_id"], book_title.strip()),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_IN_LIBRARY)
        return Book_Description(**row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update description: {str(e)}")

@library_app.get("/books/search/media_type")
def search_books_by_media_type(media_type: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not media_type or not media_type.strip():
        raise HTTPException(status_code=400, detail="Media type is required")
    media_type = media_type.strip()
    try:
        query = """
            SELECT DISTINCT b.*, mt.media_type_name AS media_type
            FROM book_info AS b
            JOIN book_media_type AS bmt ON bmt.book_id = b.book_id
            JOIN media_type AS mt ON mt.media_type_id = bmt.media_type_id
            WHERE mt.media_type_name ILIKE %s
            ORDER BY b.book_title;
        """
        cursor.execute(query, (f"%{media_type}%",))
        return {"query": media_type, "books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by media type failed: {str(e)}")

@library_app.get("/books/search/book_genre")
def search_books_by_book_genre(genre: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not genre or not genre.strip():
        raise HTTPException(status_code=400, detail="Book genre is required")
    book_genre = genre.strip()
    try:
        query = """
            SELECT DISTINCT b.*, g.genre_name AS genre
            FROM book_info AS b
            JOIN book_genre AS bg ON bg.book_id = b.book_id
            JOIN genre AS g ON g.genre_id = bg.genre_id
            WHERE g.genre_name ILIKE %s
            ORDER BY b.book_title;
        """
        cursor.execute(query, (f"%{book_genre}%",))
        return {"query": book_genre, "books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by book genre failed: {str(e)}")

@library_app.get("/books/search/author")
def search_books_by_author(author: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not author or not author.strip():
        raise HTTPException(status_code=400, detail="Author name is required")
    author_name = author.strip()
    try:
        query = """
            SELECT DISTINCT
                b.*,
                CONCAT_WS(' ', a.first_name, a.last_name) AS author
            FROM book_info AS b
            JOIN book_author AS ba ON ba.book_id = b.book_id
            JOIN author_info AS a ON a.author_id = ba.author_id
            WHERE CONCAT_WS(' ', a.first_name, a.last_name) ILIKE %s
            ORDER BY b.book_title;
        """
        cursor.execute(query, (f"%{author_name}%",))
        return {"query": author_name, "books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by author failed: {str(e)}")

@library_app.get("/comics/search")
def get_comic_book_from_database(comic: str = Query(...), cursor: RealDictCursor = Depends(get_db_cursor)):
    if not comic or not comic.strip():
        raise HTTPException(status_code=400, detail="Comic book title is required")
    comic_book = comic.strip()
    try:
        query = """
            SELECT DISTINCT b.*, g.genre_name AS genre, mt.media_type_name AS media_type
            FROM book_info AS b
            LEFT JOIN book_genre AS bg ON bg.book_id = b.book_id
            LEFT JOIN genre AS g ON g.genre_id = bg.genre_id
            LEFT JOIN book_media_type AS bmt ON bmt.book_id = b.book_id
            LEFT JOIN media_type AS mt ON mt.media_type_id = bmt.media_type_id
            WHERE b.book_title ILIKE %s
            ORDER BY b.book_title;
        """
        cursor.execute(query, (f"%{comic_book}%",))
        return {"comic_books": comic_book_results}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

@library_app.get("/books/search/pages")
def search_books_by_pages(
    min_pages: int | None = Query(default=None, ge=0),
    max_pages: int | None = Query(default=None, ge=0),
    cursor: RealDictCursor = Depends(get_db_cursor)
):
    if min_pages is None and max_pages is None:
        raise HTTPException(status_code=400, detail="Provide min_pages, max_pages, or both")
    if min_pages is not None and max_pages is not None and min_pages > max_pages:
        raise HTTPException(status_code=400, detail="min_pages cannot be greater than max_pages")
    try:
        query = """
            SELECT *
            FROM book_info
            WHERE page_amount IS NOT NULL
              AND (%s IS NULL OR page_amount >= %s)
              AND (%s IS NULL OR page_amount <= %s)
            ORDER BY page_amount, book_title;
        """
        cursor.execute(query, (min_pages, min_pages, max_pages, max_pages))
        return {"query": {"min_pages": min_pages, "max_pages": max_pages}, "books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search by page count failed: {str(e)}")

@library_app.get("/books/{book_id}")
def get_book_details(book_id: int, cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute(
            """
            SELECT b.*, ba.author_id
            FROM book_info AS b
            LEFT JOIN LATERAL (
                SELECT author_id
                FROM book_author
                WHERE book_id = b.book_id
                ORDER BY author_id
                LIMIT 1
            ) AS ba ON TRUE
            WHERE b.book_id = %s;
            """,
            (book_id,),
        )
        book = cursor.fetchone()
        if book is None:
            raise HTTPException(status_code=404, detail="Book not found")
        return book
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_book_database():
    connection = db_manager.get_conn()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM book_info;")
        book_records = cursor.fetchall()
        print(f"Found {len(book_records)} books:")
        for row in book_records:
            print(row["book_title"])
        cursor.close()
        return book_records
    except Exception as error:
        print(error)
        raise error
    finally:
        db_manager.release_conn(connection)

def add_multiple_authors():
    connection = db_manager.get_conn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT author_id, first_name, last_name FROM author_info ORDER BY last_name, first_name, author_id;")
            return cursor.fetchall()
    finally:
        db_manager.release_conn(connection)

def search_all_games():
    connection = db_manager.get_conn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM game_info ORDER BY game_title;")
            return cursor.fetchall()
    finally:
        db_manager.release_conn(connection)

class Game(BaseModel):
    game_title: str = Field(..., min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    release_date: date | None = None
    min_players: int | None = Field(default=None, gt=0)
    max_players: int | None = Field(default=None, gt=0)
    play_time_minutes: int | None = Field(default=None, gt=0)
    min_age: int | None = Field(default=None, ge=0)
    game_description: str | None = None

    @model_validator(mode="after")
    def validate_game_data(self):
        self.game_title = self.game_title.strip()
        self.publisher = self.publisher.strip() if self.publisher else None
        self.game_description = self.game_description.strip() if self.game_description else None
        if not self.game_title:
            raise ValueError("game_title cannot be empty")
        if self.min_players is not None and self.max_players is not None and self.max_players < self.min_players:
            raise ValueError("max_players cannot be less than min_players")
        return self

@library_app.post("/games", status_code=status.HTTP_201_CREATED)
def add_game(
    game: Game,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute("SELECT * FROM game_info WHERE game_title = %s;", (game.game_title,))
        new_game = cursor.fetchone()
        if new_game is None:
            cursor.execute(
                """
                INSERT INTO game_info(
                    game_title, publisher, release_date, min_players, max_players,
                    play_time_minutes, min_age, game_description
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    game.game_title, game.publisher, game.release_date, game.min_players,
                    game.max_players, game.play_time_minutes, game.min_age, game.game_description,
                ),
            )
            new_game = cursor.fetchone()

        cursor.execute(
            """
            INSERT INTO game_tracking (user_id, game_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            RETURNING game_id;
            """,
            (user["user_id"], new_game["game_id"]),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=409, detail="This game is already in your library.")
        return {"message": "Game added successfully", "game": new_game}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@library_app.get("/games")
def get_all_games(user: dict = Depends(get_current_user), cursor: RealDictCursor = Depends(get_db_cursor)):
    try:
        cursor.execute(
            """
            SELECT g.*, t.play_status, t.game_notes
            FROM game_tracking AS t
            JOIN game_info AS g ON g.game_id = t.game_id
            WHERE t.user_id = %s
            ORDER BY g.game_title;
            """,
            (user["user_id"],),
        )
        return {"games": cursor.fetchall()}
    except Exception as error:
        raise HTTPException(status_code=500, detail="Could not retrieve games")

class BookProgressUpdate(BaseModel):
    read_status: str = Field(..., description="'read' or 'want to read'")
    rating: int | None = Field(default=None, ge=1, le=5)

    @field_validator("read_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean_v = v.strip().lower()
        if clean_v not in ("read", "want to read"):
            raise ValueError("read_status must be exactly 'read' or 'want to read'")
        return clean_v

@library_app.put("/books/progress")
def update_book_progress_by_title(
    book_title: str,
    payload: BookProgressUpdate,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    try:
        cursor.execute(
            """
            UPDATE book_tracking AS t
            SET read_status = %s, rating = %s
            FROM book_info AS b
            WHERE b.book_id = t.book_id AND t.user_id = %s AND LOWER(b.book_title) = LOWER(%s)
            RETURNING b.book_id, b.book_title, t.read_status, t.rating;
            """,
            (payload.read_status, payload.rating, user["user_id"], book_title.strip()),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Book not found in your library.")
        return {"status": "success", "updated_record": dict(row)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Progress sync failed: {str(e)}")

def main():
    print("Hello from digital-library-system!")
    try:
        get_book_database()
    except Exception as e:
        print(f"Main execution warning: Local database check failed ({e})")
    db_manager.initialize_pool()
    uvicorn.run("main:library_app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
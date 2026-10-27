# main.py
import re
import logging
import uvicorn
import psycopg2
import requests
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional, Generator
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator, model_validator
from contextlib import asynccontextmanager
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

# Initialize dotenv manually if needed or fallback safely
_COGNITO_JWKS = None
COGNITO_ISSUER_PREFIX = "https://cognito-idp."
cognito_endpoint = os.getenv("AWS_COGNITO_ENDPOINT")

# When set (e.g. http://cognito-local:9229), all Cognito calls go to the local
# emulator instead of the real AWS endpoint.
COGNITO_ENDPOINT = os.getenv("AWS_COGNITO_ENDPOINT", "").strip()
# cognito-local stamps tokens with this issuer base, regardless of the Docker hostname.
COGNITO_LOCAL_ISSUER = os.getenv("COGNITO_LOCAL_ISSUER", "http://localhost:9229").strip()


class CognitoApiError(Exception):
    """Represent an error returned by the Cognito user-pool API."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def cognito_configuration():
    """Return required Cognito settings when the integration is enabled."""
    region = os.getenv("AWS_REGION", "").strip()
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "").strip()
    client_id = os.getenv("COGNITO_CLIENT_ID", "").strip()
    if not region or not user_pool_id or not client_id:
        raise RuntimeError(
            "AWS_REGION, COGNITO_USER_POOL_ID, and COGNITO_CLIENT_ID are required when USE_COGNITO=true"
        )
    return region, user_pool_id, client_id


def cognito_api_url(region: str) -> str:
    """Return the Cognito API URL: the local emulator if configured, otherwise AWS."""
    if COGNITO_ENDPOINT:
        return COGNITO_ENDPOINT.rstrip("/") + "/"
    return f"https://cognito-idp.{region}.amazonaws.com/"


def cognito_issuer(region: str, user_pool_id: str) -> str:
    """Return the token issuer expected for the configured user pool."""
    if COGNITO_ENDPOINT:
        return f"{COGNITO_LOCAL_ISSUER.rstrip('/')}/{user_pool_id}"
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def cognito_jwks_url(region: str, user_pool_id: str) -> str:
    """Return the URL that serves the pool's signing keys."""
    if COGNITO_ENDPOINT:
        return f"{COGNITO_ENDPOINT.rstrip('/')}/{user_pool_id}/.well-known/jwks.json"
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"


def cognito_api(target: str, payload: dict) -> dict:
    """Call a public Cognito user-pool API operation over HTTPS."""
    region, _, _ = cognito_configuration()
    try:
        response = requests.post(
            cognito_api_url(region),
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": f"AWSCognitoIdentityProviderService.{target}",
            },
            json=payload,
            timeout=10,
        )
    except requests.RequestException as error:
        logging.exception("Cognito request %s failed", target)
        raise RuntimeError("Cognito is temporarily unavailable") from error

    try:
        response_payload = response.json()
    except ValueError as error:
        raise RuntimeError("Cognito returned an invalid response") from error

    if not isinstance(response_payload, dict):
        raise RuntimeError("Cognito returned an invalid response")
    if not response.ok:
        error_type = response_payload.get("__type", "")
        code = error_type.rsplit("#", 1)[-1].split(":", 1)[0]
        raise CognitoApiError(code or "CognitoServiceError")
    return response_payload

def load_db_config():
    """Collect database connection settings, using local-development defaults."""
    # Fallback to local development credentials if variables aren't set yet
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "digital_library"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "secretpassword"),
        "port": os.getenv("DB_PORT", "5440")
    }

def get_cognito_public_keys(force_refresh: bool = False):
    """Fetch and cache the Cognito JWKS keys used to verify access tokens."""
    global _COGNITO_JWKS
    if _COGNITO_JWKS is None or force_refresh:
        region, user_pool_id, _ = cognito_configuration()
        url = cognito_jwks_url(region, user_pool_id)
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            document = response.json()
            if not isinstance(document, dict):
                raise ValueError("Cognito JWKS response is not an object")
            keys = document.get("keys")
            if not isinstance(keys, list):
                raise ValueError("Cognito JWKS response does not contain a keys list")
            _COGNITO_JWKS = keys
        except (requests.RequestException, ValueError) as error:
            logging.exception("Failed to pull Cognito JWKS certificates")
            raise RuntimeError("Unable to retrieve Cognito signing keys") from error
    return _COGNITO_JWKS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_env(env_name):
    """Read a required environment setting, defaulting DB_PORT for local use."""
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
        """Create a manager whose connection pool is initialized on demand."""
        self._pool = None

    def initialize_pool(self) -> None:
        """Create the shared PostgreSQL connection pool if it is not initialized."""
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
                port=int(get_env("DB_PORT")),
                sslmode=os.getenv("DB_SSLMODE", "prefer")
            )
        except Exception as error:
            print(error)
            raise error

    def get_conn(self):
        """Return a pooled connection, initializing the pool when necessary."""
        if not self._pool:
            self.initialize_pool()
        return self._pool.getconn()

    def release_conn(self, conn):
        """Return a checked-out connection to the pool when both are available."""
        if self._pool and conn:
            self._pool.putconn(conn)

    def close_pool(self) -> None:
        """Close all pooled connections and reset the manager to an uninitialized state."""
        if self._pool:
            self._pool.closeall()
            self._pool = None

db_manager = DatabaseManager()
USER_SCHEMA_FILE = Path(__file__).with_name("user-schema.sql")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database pool on startup and close it during shutdown."""
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
    allow_origins=["http://localhost:8080"], # or ["*"] for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_cursor() -> Generator[RealDictCursor, None, None]:
    """Yield a dictionary cursor and commit or roll back its request transaction."""
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

def activate_user_schema(cursor: RealDictCursor, user_id: int) -> None:
    """Create and select a user's schema, applying its tables on first use."""
    schema_name = f"library_user_{int(user_id)}"
    cursor.execute("SELECT pg_advisory_xact_lock(%s);", (int(user_id),))
    cursor.execute(
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema_name))
    )
    cursor.execute(
        sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(
            sql.Identifier(schema_name)
        )
    )
    cursor.execute("SELECT to_regclass('book_info') AS book_info;")
    if cursor.fetchone()["book_info"] is None:
        cursor.execute(
            """
            SELECT namespace.nspname
            FROM pg_catalog.pg_extension AS extension
            JOIN pg_catalog.pg_namespace AS namespace
              ON namespace.oid = extension.extnamespace
            WHERE extension.extname = 'citext';
            """
        )
        extension_schema = cursor.fetchone()
        if extension_schema is None:
            raise RuntimeError("The PostgreSQL citext extension must be installed.")
        citext_type = f"{sql.Identifier(extension_schema['nspname']).as_string(cursor)}.citext"
        schema_ddl = USER_SCHEMA_FILE.read_text().replace("public.citext", citext_type)
        cursor.execute(schema_ddl)

password_hasher = PasswordHasher()
_DUMMY_HASH = password_hasher.hash("timing-equalizer-not-a-real-password")
_COGNITO_JWKS = None
security_agent = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# HEALTH ENDPOINT: Added for infrastructure target group status checks
@library_app.get("/health", status_code=status.HTTP_200_OK, tags=["System Health"])
async def health_check():
    """Return the basic health payload used by deployment probes."""
    return {
        "status": "healthy",
        "environment": os.getenv("APP_ENV", "production"),
        "database_connected": True
    }

def get_jwt_secret() -> str:
    """Return the configured JWT signing key, rejecting missing or short values."""
    secret = os.environ.get("JWT_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be set to a random string of at least 32 characters")
    return secret

def create_access_token(user_id: int, username: str) -> str:
    """Sign a native bearer token with the user's ID and configured expiration."""
    now = datetime.now(timezone.utc)
    minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def native_auth_enabled() -> bool:
    """Return whether username/password (native) accounts are allowed.

    ALLOW_NATIVE_AUTH=true  -> native and Cognito can be used side by side.
    ALLOW_NATIVE_AUTH=false -> native accounts are off.
    Unset                   -> native is on only when Cognito is off (original behavior).
    """
    explicit = os.getenv("ALLOW_NATIVE_AUTH", "").strip().lower()
    if explicit in {"true", "false"}:
        return explicit == "true"
    return os.getenv("USE_COGNITO", "false").lower() != "true"


def cognito_auth_enabled() -> bool:
    """Return whether Amazon Cognito sign-in is enabled."""
    return os.getenv("USE_COGNITO", "false").lower() == "true"


def decode_bearer_token(token: str) -> dict:
    """Verify a native JWT or Cognito access token and return its identity."""
    try:
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified_payload.get("iss", "")

        if issuer.startswith(COGNITO_ISSUER_PREFIX) or (
            COGNITO_ENDPOINT and issuer.startswith(COGNITO_LOCAL_ISSUER)
        ):
            if os.getenv("USE_COGNITO", "false").lower() != "true":
                raise jwt.PyJWTError("Cognito authentication is disabled")
            region, user_pool_id, client_id = cognito_configuration()
            expected_issuer = cognito_issuer(region, user_pool_id)
            if issuer != expected_issuer:
                raise jwt.PyJWTError("Token issuer does not match the configured Cognito user pool")

            key_id = jwt.get_unverified_header(token).get("kid")
            keys = get_cognito_public_keys()
            jwk = next((key for key in keys if key.get("kid") == key_id), None)
            if jwk is None:
                keys = get_cognito_public_keys(force_refresh=True)
                jwk = next((key for key in keys if key.get("kid") == key_id), None)
            if jwk is None:
                raise jwt.PyJWTError("Matching Cognito signing key was not found")

            claims = jwt.decode(
                token,
                jwt.PyJWK.from_dict(jwk).key,
                algorithms=["RS256"],
                issuer=expected_issuer,
                options={
                    "verify_aud": False,
                    "require": ["exp", "iat", "sub", "token_use", "client_id"],
                },
            )
            if claims["token_use"] != "access" or claims["client_id"] != client_id:
                raise jwt.PyJWTError("Token is not an access token for this Cognito app client")
            return {
                "identity_provider": "aws_cognito",
                "user_id": claims["sub"],
                "username": claims.get("username"),
            }

        claims = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "username"]},
        )
        return {
            "identity_provider": "native_jwt",
            "user_id": int(claims["sub"]),
            "username": claims["username"],
        }
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


async def verify_cognito_or_jwt(credentials: HTTPAuthorizationCredentials = Depends(security_agent)):
    """Validate a Cognito or native JWT and return its provider and user identity."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return decode_bearer_token(credentials.credentials)

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str) -> str:
        """Trim and validate a username against the allowed characters and length."""
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise ValueError("Username must be 3-30 characters: letters, numbers, . _ -")
        return value

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        """Trim and validate the email address and its maximum length."""
        value = value.strip()
        if len(value) > 254 or not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

class LoginRequest(BaseModel):
    username: str
    password: str


class CognitoRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        """Validate and normalize the email used as the Cognito username."""
        value = value.strip()
        if len(value) > 254 or not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class CognitoConfirmRequest(BaseModel):
    email: str
    confirmation_code: str = Field(min_length=1, max_length=64)


class CognitoLoginRequest(BaseModel):
    email: str
    password: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_agent),
    cursor: RealDictCursor = Depends(get_db_cursor),
) -> dict:
    """Authenticate a native or Cognito token, load its profile, and activate its schema."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Please log in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    identity = decode_bearer_token(credentials.credentials)
    if identity["identity_provider"] == "native_jwt" and not native_auth_enabled():
        raise unauthorized
    if identity["identity_provider"] == "aws_cognito":
        user = get_or_create_cognito_user(identity, credentials.credentials, cursor)
    else:
        cursor.execute(
            "SELECT user_id, username, email FROM reader_info WHERE user_id = %s;",
            (identity["user_id"],),
        )
        user = cursor.fetchone()
    if user is None:
        raise unauthorized
    activate_user_schema(cursor, user["user_id"])
    return dict(user)

def get_or_create_cognito_user(identity: dict, access_token: str, cursor: RealDictCursor) -> dict:
    """Resolve Cognito sub to a local profile, linking only a verified matching email."""
    cursor.execute(
        "SELECT user_id, username, email FROM reader_info WHERE external_auth_id = %s;",
        (identity["user_id"],),
    )
    user = cursor.fetchone()
    if user is not None:
        return user

    try:
        user_info = cognito_api("GetUser", {"AccessToken": access_token})
    except CognitoApiError as error:
        raise HTTPException(status_code=401, detail="Invalid Cognito access token.") from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    attributes = {item["Name"]: item["Value"] for item in user_info.get("UserAttributes", [])}
    email = attributes.get("email", "").strip()
    if not email or attributes.get("email_verified", "").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified email address is required for a Cognito account.",
        )

    cursor.execute(
        "SELECT user_id, username, email, external_auth_id FROM reader_info WHERE email = %s;",
        (email,),
    )
    user = cursor.fetchone()
    if user is not None:
        if user.get("external_auth_id") not in (None, identity["user_id"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already linked to a different Cognito account.",
            )
        if user.get("external_auth_id") is None:
            cursor.execute(
                """
                UPDATE reader_info
                SET external_auth_id = %s
                WHERE user_id = %s AND external_auth_id IS NULL
                RETURNING user_id, username, email;
                """,
                (identity["user_id"], user["user_id"]),
            )
            linked_user = cursor.fetchone()
            if linked_user is not None:
                return linked_user
            cursor.execute(
                "SELECT user_id, username, email FROM reader_info WHERE external_auth_id = %s;",
                (identity["user_id"],),
            )
            linked_user = cursor.fetchone()
            if linked_user is not None:
                return linked_user
            raise HTTPException(status_code=409, detail="Unable to link this Cognito account.")
        return user

    username_suffix = re.sub(r"[^a-zA-Z0-9]", "", identity["user_id"])[:20].lower()
    cursor.execute(
        """
        INSERT INTO reader_info (username, email, external_auth_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (external_auth_id) DO UPDATE SET external_auth_id = EXCLUDED.external_auth_id
        RETURNING user_id, username, email;
        """,
        (f"cognito_{username_suffix}", email, identity["user_id"]),
    )
    return cursor.fetchone()

@library_app.get("/auth/options", tags=["Authentication"])
def auth_options():
    """Report which sign-in methods the frontend should offer."""
    return {"native": native_auth_enabled(), "cognito": cognito_auth_enabled()}


@library_app.post("/auth/register")
def register(body: RegisterRequest, cursor: RealDictCursor = Depends(get_db_cursor)):
    """Create an account, initialize its schema, and return a bearer token."""
    if not native_auth_enabled():
        raise HTTPException(
            status_code=503,
            detail="Native registration is disabled. Use /auth/cognito/register instead."
        )
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
    activate_user_schema(cursor, user["user_id"])
    return {
        "access_token": create_access_token(user["user_id"], user["username"]),
        "token_type": "bearer",
        "user": dict(user),
    }



def cognito_http_error(error: CognitoApiError) -> HTTPException:
    """Translate Cognito errors into stable API responses without exposing provider details."""
    if error.code == "UsernameExistsException":
        return HTTPException(status_code=409, detail="An account with this email already exists.")
    if error.code == "CodeMismatchException":
        return HTTPException(
            status_code=400,
            detail="Incorrect confirmation code. Use the latest code for this same email address.",
        )
    if error.code == "ExpiredCodeException":
        return HTTPException(
            status_code=400,
            detail="The confirmation code has expired. A new code must be issued before confirming.",
        )
    if error.code in {
        "InvalidParameterException",
        "InvalidPasswordException",
    }:
        return HTTPException(status_code=400, detail="Cognito rejected the supplied account details.")
    if error.code in {"NotAuthorizedException", "UserNotFoundException"}:
        return HTTPException(status_code=401, detail="Invalid email, password, or confirmation code.")
    if error.code in {"LimitExceededException", "TooManyRequestsException"}:
        return HTTPException(status_code=429, detail="Too many Cognito requests. Try again later.")
    logging.error("Cognito operation failed with provider error %s", error.code)
    return HTTPException(status_code=502, detail="Cognito could not complete the request.")


def cognito_tokens(email: str, password: str) -> dict:
    """Authenticate a confirmed Cognito user and return bearer-token fields."""
    _, _, client_id = cognito_configuration()
    result = cognito_api(
        "InitiateAuth",
        {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": client_id,
            "AuthParameters": {"USERNAME": email, "PASSWORD": password},
        },
    )
    authentication = result.get("AuthenticationResult")
    if not authentication or not authentication.get("AccessToken"):
        raise HTTPException(
            status_code=409,
            detail="Cognito requires an additional authentication step that this client does not support.",
        )
    token_response = {
        "access_token": authentication["AccessToken"],
        "token_type": authentication.get("TokenType", "Bearer").lower(),
        "expires_in": authentication.get("ExpiresIn"),
    }
    if authentication.get("RefreshToken"):
        token_response["refresh_token"] = authentication["RefreshToken"]
    return token_response


@library_app.post("/auth/cognito/register", status_code=status.HTTP_202_ACCEPTED)
def register_cognito(body: CognitoRegisterRequest):
    """Create a Cognito account and request email confirmation."""
    if os.getenv("USE_COGNITO", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="Cognito authentication is not enabled.")
    try:
        _, _, client_id = cognito_configuration()
        result = cognito_api(
            "SignUp",
            {
                "ClientId": client_id,
                "Username": body.email,
                "Password": body.password,
                "UserAttributes": [{"Name": "email", "Value": body.email}],
            },
        )
    except CognitoApiError as error:
        raise cognito_http_error(error) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    delivery = result.get("CodeDeliveryDetails", {})
    message = "Check your email for a Cognito confirmation code."
    local_code = os.getenv("COGNITO_LOCAL_CODE", "").strip()
    if COGNITO_ENDPOINT and local_code:
        message = f"Local Cognito confirmation code: {local_code}"
    return {
        "message": message,
        "delivery_medium": delivery.get("DeliveryMedium", "EMAIL"),
    }


@library_app.post("/auth/cognito/confirm")
def confirm_cognito(body: CognitoConfirmRequest):
    """Confirm a Cognito email address before the user signs in."""
    if os.getenv("USE_COGNITO", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="Cognito authentication is not enabled.")
    try:
        _, _, client_id = cognito_configuration()
        cognito_api(
            "ConfirmSignUp",
            {
                "ClientId": client_id,
                "Username": body.email.strip(),
                "ConfirmationCode": body.confirmation_code.strip(),
            },
        )
        return {"message": "Email confirmed. Sign in with your email and password."}
    except CognitoApiError as error:
        raise cognito_http_error(error) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@library_app.post("/auth/cognito/login")
def login_cognito(body: CognitoLoginRequest):
    """Authenticate with Cognito and return an access token for protected API routes."""
    if os.getenv("USE_COGNITO", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="Cognito authentication is not enabled.")
    try:
        return cognito_tokens(body.email.strip(), body.password)
    except CognitoApiError as error:
        raise cognito_http_error(error) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@library_app.post("/auth/login")
def login(body: LoginRequest, cursor: RealDictCursor = Depends(get_db_cursor)):
    """Authenticate by username or email and return a bearer token on success."""
    if not native_auth_enabled():
        raise HTTPException(
            status_code=503,
            detail="Native login is disabled. Use /auth/cognito/login instead."
        )
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
    try:
        password_ok = password_hasher.verify(stored_hash, body.password)
    except (VerificationError, InvalidHashError):
        password_ok = False
    if not (user and user["password_hash"] and password_ok):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {
        "access_token": create_access_token(user["user_id"], user["username"]),
        "token_type": "bearer",
        "user": {"user_id": user["user_id"], "username": user["username"], "email": user["email"]},
    }


@library_app.get("/auth/me")
def read_me(user: dict = Depends(get_current_user)):
    """Return the authenticated user's public account details."""
    return {"user": user}

def connect():
    """Open a direct database connection, print its version, and close it."""
    connection = None
    try:
        connection = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST"),
            port=int(get_env("DB_PORT")),
                sslmode=os.getenv("DB_SSLMODE", "prefer")
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
        """Normalize book text and enforce identifier and author-field pairing."""
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
    """Return a basic response from the API root endpoint."""
    return {"message": "Hello World"}

@library_app.get("/books")
def get_books(
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """List the authenticated user's tracked books with status and summary."""
    try:
        cursor.execute(
            """
            SELECT b.*, t.read_status, t.book_summary
            FROM book_tracking AS t
            JOIN book_info AS b ON b.book_id = t.book_id
            WHERE t.user_id = %s
            ORDER BY LOWER(b.book_title), b.book_title;
            """,
            (user["user_id"],),
        )
        return {"books": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@library_app.get("/books/summaries")
def get_book_summaries_from_database(
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Return book IDs and titles from the active user's book catalog."""
    try:
        cursor.execute("SELECT book_id, book_title FROM book_info;")
        details_query = cursor.fetchall()
        return {"books": details_query}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not find book details")

@library_app.get("/books/info")
def get_details_from_database(
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Return complete book records from the active user's catalog."""
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
    """Find or create a catalog book, then add it to the user's library."""
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
    """Search the active catalog for titles containing the supplied text."""
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
    """Clear a book's user-specific summary and return the updated record."""
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
    """Remove a book from the user's library without deleting its catalog record."""
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
    """Update a tracked book's user-specific summary by book ID."""
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
    """Remove the case-insensitive title match from the user's library."""
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
    """Update a tracked book's user-specific summary by title."""
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
def search_books_by_media_type(
    media_type: str = Query(...),
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Find catalog books whose media type contains the supplied text."""
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
def search_books_by_book_genre(
    genre: str = Query(...),
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Find catalog books whose genre contains the supplied text."""
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
def search_books_by_author(
    author: str = Query(...),
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Find catalog books whose author's full name contains the supplied text."""
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
def get_comic_book_from_database(
    comic: str = Query(...),
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Search book titles and include any matching genre and media type details."""
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
        return {"comic_books": cursor.fetchall()}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

@library_app.get("/books/search/pages")
def search_books_by_pages(
    min_pages: int | None = Query(default=None, ge=0),
    max_pages: int | None = Query(default=None, ge=0),
    cursor: RealDictCursor = Depends(get_db_cursor),
    user: dict = Depends(get_current_user),
):
    """Find books within the optional inclusive page-count bounds."""
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
def get_book_details(
    book_id: int,
    cursor: RealDictCursor = Depends(get_db_cursor),
    user: dict = Depends(get_current_user),
):
    """Return one catalog book with its first associated author ID, if present."""
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
    """Print and return all book records using a pooled database connection."""
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
    """Return authors ordered by name and ID using a pooled connection."""
    connection = db_manager.get_conn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT author_id, first_name, last_name FROM author_info ORDER BY last_name, first_name, author_id;")
            return cursor.fetchall()
    finally:
        db_manager.release_conn(connection)

def search_all_games():
    """Return all game records ordered by title using a pooled connection."""
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
        """Normalize optional game text and validate its title and player range."""
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
    """Find or create a game record, then add it to the user's tracked games."""
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@library_app.get("/games")
def get_all_games(
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """List the authenticated user's tracked games and personal status or notes."""
    try:
        cursor.execute(
            """
            SELECT g.*, t.play_status, t.game_notes
            FROM game_tracking AS t
            JOIN game_info AS g ON g.game_id = t.game_id
            WHERE t.user_id = %s
            ORDER BY LOWER(g.game_title), g.game_title;
            """,
            (user["user_id"],),
        )
        return {"games": cursor.fetchall()}
    except Exception as error:
        raise HTTPException(status_code=500, detail="Could not retrieve games")

@library_app.delete("/games")
def delete_game_endpoint(
    game_title: str,
    user: dict = Depends(get_current_user),
    cursor: RealDictCursor = Depends(get_db_cursor),
):
    """Remove a case-insensitive title match from the user's tracked games."""
    try:
        cursor.execute(
            """
            WITH targeted_game AS (
                SELECT game_id FROM game_info WHERE LOWER(game_title) = LOWER(%s) LIMIT 1
            ),
            removed AS (
                DELETE FROM game_tracking
                WHERE user_id = %s AND game_id = (SELECT game_id FROM targeted_game)
                RETURNING game_id
            )
            SELECT g.* FROM removed AS r JOIN game_info AS g ON g.game_id = r.game_id;
            """,
            (game_title.strip(), user["user_id"]),
        )
        removed = cursor.fetchone()
        if removed is None:
            raise HTTPException(status_code=404, detail="Game not found in your library.")
        return {"message": "Game removed from your library", "game": removed}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not remove game: {str(error)}")

class BookProgressUpdate(BaseModel):
    read_status: str = Field(..., description="'read' or 'want to read'")
    rating: int | None = Field(default=None, ge=1, le=5)

    @field_validator("read_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Normalize read status and restrict it to the supported values."""
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
    """Update a tracked book's read status and optional rating by title."""
    try:
        cursor.execute(
            """
            UPDATE book_tracking AS t
            SET read_status = CASE WHEN %s = 'read' THEN 'finished' ELSE 'want' END,
                book_ratings = %s
            FROM book_info AS b
            WHERE b.book_id = t.book_id AND t.user_id = %s AND LOWER(b.book_title) = LOWER(%s)
            RETURNING b.book_id, b.book_title,
                CASE t.read_status
                    WHEN 'finished' THEN 'read'
                    WHEN 'want' THEN 'want to read'
                    ELSE t.read_status
                END AS read_status,
                t.book_ratings AS rating;
            """,
            (payload.read_status, payload.rating, user["user_id"], book_title.strip()),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Book not found in your library.")
        return {"status": "success", "updated_record": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Progress sync failed: {str(e)}")

def main():
    """Run a best-effort database check, initialize the pool, and start the API."""
    print("Hello from digital-library-system!")
    try:
        get_book_database()
    except Exception as e:
        print(f"Main execution warning: Local database check failed ({e})")
    db_manager.initialize_pool()
    uvicorn.run("main:library_app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
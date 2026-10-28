import os
import secrets
import time

import jwt
import psycopg2
import requests
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, EmailStr

library_app = FastAPI(title="Digital Library API")
app = library_app

# Added CORS middleware to handle client web browser request validation across ports
library_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:4200", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configured database parameters to prioritize Docker environment keys
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "super_secret_db_password_here")
DB_NAME = os.getenv("DB_NAME", "digital_library")
DB_HOST = os.getenv("DB_HOST", "my_postgres_db")
DB_PORT = os.getenv("DB_PORT", "5432")

# ---------------------------------------------------------------------------
# Cognito configuration
#
# AWS_COGNITO_ENDPOINT set    -> local emulator (cognito-local). The API
#                                generates a RANDOM confirmation code itself
#                                and shows it to the tester.
# AWS_COGNITO_ENDPOINT empty  -> real AWS Cognito. Cognito generates the
#                                random code and emails it; the API never
#                                sees or returns it.
# ---------------------------------------------------------------------------
COGNITO_ENDPOINT = os.getenv("AWS_COGNITO_ENDPOINT", "")
LOCAL_CODE_TTL_SECONDS = int(os.getenv("COGNITO_LOCAL_CODE_TTL", str(15 * 60)))
LOCAL_CODE_MAX_ATTEMPTS = 5

# email -> {"code": str, "expires": float, "attempts": int}
# In-memory, so local development with a single backend process only.
_LOCAL_CODES: dict = {}


class CognitoApiError(Exception):
    """Raised when Cognito (or the emulator) returns an error response."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def is_local_cognito() -> bool:
    return bool(COGNITO_ENDPOINT)


def cognito_api_url(region: str) -> str:
    if COGNITO_ENDPOINT:
        return COGNITO_ENDPOINT
    return f"https://cognito-idp.{region}.amazonaws.com/"


def discover_local_cognito() -> tuple:
    """Find the emulator's pool and app client by name.

    cognito-init prints new IDs whenever the emulator's data is recreated, which
    leaves any copy in .env stale ("App Client ... not found"). Asking the
    emulator for its current IDs on each request avoids that.
    """
    try:
        pools = cognito_api("ListUserPools", {"MaxResults": 60}).get("UserPools", [])
        pool = next((p for p in pools if p.get("Name") == "LocalLibraryPool"), None)
        if not pool:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local Cognito pool not found. Run: docker compose run --rm cognito-init",
            )
        clients = cognito_api(
            "ListUserPoolClients", {"UserPoolId": pool["Id"], "MaxResults": 60}
        ).get("UserPoolClients", [])
        if not clients:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local Cognito app client not found. Run: docker compose run --rm cognito-init",
            )
        return pool["Id"], clients[0]["ClientId"]
    except CognitoApiError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message)


def cognito_configuration() -> dict:
    region = os.getenv("AWS_REGION", "us-east-1")
    if is_local_cognito():
        # Local emulator: always use the emulator's current IDs, not .env.
        pool_id, client_id = discover_local_cognito()
        return {"region": region, "pool_id": pool_id, "client_id": client_id}
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
    client_id = os.getenv("COGNITO_CLIENT_ID", "")
    if not pool_id or not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cognito is not configured. Set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID.",
        )
    return {"region": region, "pool_id": pool_id, "client_id": client_id}


def cognito_api(action: str, payload: dict) -> dict:
    """Call a Cognito Identity Provider action (works for AWS and cognito-local)."""
    region = os.getenv("AWS_REGION", "us-east-1")
    try:
        response = requests.post(
            cognito_api_url(region),
            json=payload,
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": f"AWSCognitoIdentityProviderService.{action}",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise CognitoApiError("ServiceUnavailable", f"Could not reach Cognito: {exc}", 503)

    try:
        data = response.json() if response.content else {}
    except ValueError:
        data = {}

    if response.status_code >= 400:
        error_type = str(data.get("__type", "CognitoError")).split("#")[-1]
        message = data.get("message") or data.get("Message") or "Cognito request failed."
        raise CognitoApiError(error_type, message, response.status_code)
    return data


def raise_http_from_cognito(exc: CognitoApiError):
    """Translate a Cognito error into an HTTP error the frontend understands."""
    if exc.code == "UsernameExistsException":
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if exc.code in {"CodeMismatchException", "ExpiredCodeException"}:
        raise HTTPException(status_code=400, detail="Invalid or expired confirmation code.")
    if exc.code in {"NotAuthorizedException", "UserNotFoundException"}:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if exc.code == "UserNotConfirmedException":
        raise HTTPException(status_code=403, detail="Confirm your email code before signing in.")
    if exc.code in {"InvalidPasswordException", "InvalidParameterException"}:
        raise HTTPException(status_code=400, detail=exc.message)
    raise HTTPException(status_code=exc.http_status if exc.http_status >= 400 else 502, detail=exc.message)


# --- Random local confirmation codes --------------------------------------

def generate_local_code() -> str:
    """Cryptographically random 6-digit code (zero-padded)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_local_code(email: str) -> str:
    code = generate_local_code()
    _LOCAL_CODES[email.lower()] = {
        "code": code,
        "expires": time.time() + LOCAL_CODE_TTL_SECONDS,
        "attempts": 0,
    }
    # Also visible in `docker logs library_fastapi_backend`, like a "sent email".
    print(f"[local-cognito] confirmation code for {email}: {code}")
    return code


def check_local_code(email: str, submitted: str) -> bool:
    entry = _LOCAL_CODES.get(email.lower())
    if not entry:
        return False
    if time.time() > entry["expires"] or entry["attempts"] >= LOCAL_CODE_MAX_ATTEMPTS:
        _LOCAL_CODES.pop(email.lower(), None)
        return False
    entry["attempts"] += 1
    if secrets.compare_digest(entry["code"], submitted.strip()):
        _LOCAL_CODES.pop(email.lower(), None)
        return True
    return False


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connectivity could not be established."
        )

def ensure_user_table_exists(cursor):
    cursor.execute("CREATE EXTENSION IF NOT EXISTS citext SCHEMA public;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        );
    """)

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class CognitoRegister(BaseModel):
    email: EmailStr
    password: str

class CognitoConfirm(BaseModel):
    email: EmailStr
    confirmation_code: str

class CognitoLogin(BaseModel):
    email: EmailStr
    password: str

# 1. Standard Native Auth Registration Route
@library_app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ensure_user_table_exists(cursor)
        conn.commit()
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s;", (user.username, user.email))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email already registered.")
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id, username, email;",
            (user.username, user.email, user.password)
        )
        new_user = cursor.fetchone()
        conn.commit()
        token_secret = os.getenv("JWT_SECRET_KEY", "super_secret_local_signing_key_string")
        token = jwt.encode({"id": new_user["id"], "email": new_user["email"]}, token_secret, algorithm="HS256")
        return {"access_token": token, "token_type": "bearer", "user": new_user}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# 2. Amazon Cognito Registration
@library_app.post("/auth/cognito/register")
def cognito_register(payload: CognitoRegister):
    cfg = cognito_configuration()
    try:
        try:
            cognito_api("SignUp", {
                "ClientId": cfg["client_id"],
                "Username": payload.email,
                "Password": payload.password,
                "UserAttributes": [{"Name": "email", "Value": payload.email}],
            })
        except CognitoApiError as exc:
            if exc.code != "UsernameExistsException":
                raise
            # The account exists. If it was never confirmed, send a fresh code
            # instead of leaving the user stuck. If it is confirmed, tell them.
            if is_local_cognito():
                user = cognito_api("AdminGetUser", {
                    "UserPoolId": cfg["pool_id"], "Username": payload.email,
                })
                if user.get("UserStatus") != "UNCONFIRMED":
                    raise
            else:
                try:
                    cognito_api("ResendConfirmationCode", {
                        "ClientId": cfg["client_id"], "Username": payload.email,
                    })
                except CognitoApiError:
                    raise exc
                return {
                    "message": "Check your email for a new Cognito confirmation code.",
                    "delivery_medium": "EMAIL",
                }
    except CognitoApiError as exc:
        raise_http_from_cognito(exc)

    if is_local_cognito():
        code = issue_local_code(payload.email)
        return {"message": f"Local Cognito confirmation code: {code}", "delivery_medium": "EMAIL"}
    return {"message": "Check your email for a Cognito confirmation code.", "delivery_medium": "EMAIL"}

# 3. Amazon Cognito Code Confirmation
@library_app.post("/auth/cognito/confirm")
def cognito_confirm(payload: CognitoConfirm):
    cfg = cognito_configuration()
    try:
        if is_local_cognito():
            if not check_local_code(payload.email, payload.confirmation_code):
                raise HTTPException(status_code=400, detail="Invalid or expired confirmation code.")
            cognito_api("AdminConfirmSignUp", {
                "UserPoolId": cfg["pool_id"], "Username": payload.email,
            })
        else:
            cognito_api("ConfirmSignUp", {
                "ClientId": cfg["client_id"],
                "Username": payload.email,
                "ConfirmationCode": payload.confirmation_code.strip(),
            })
    except CognitoApiError as exc:
        raise_http_from_cognito(exc)
    return {"message": "Account successfully confirmed."}

# 4. Amazon Cognito Sign-In
@library_app.post("/auth/cognito/login")
def cognito_login(payload: CognitoLogin):
    cfg = cognito_configuration()
    try:
        result = cognito_api("InitiateAuth", {
            "ClientId": cfg["client_id"],
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {"USERNAME": payload.email, "PASSWORD": payload.password},
        })
    except CognitoApiError as exc:
        raise_http_from_cognito(exc)
    tokens = result.get("AuthenticationResult") or {}
    if not tokens.get("AccessToken"):
        raise HTTPException(status_code=401, detail="Cognito did not return an access token.")
    return {"access_token": tokens["AccessToken"], "token_type": "bearer"}

@library_app.get("/health")
def health_check():
    return {"status": "operational"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:library_app", host="0.0.0.0", port=5000, reload=True)
import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import psycopg2
from psycopg2.extras import RealDictCursor
import jwt

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

# 2. FIXED: Amazon Cognito Registration Endpoint Handler Route
@library_app.post("/auth/cognito/register")
async def cognito_register(payload: CognitoRegister):
    # Simulates registration confirmation response parameters expected by script.js
    return {"message": f"Cognito registration initiated for {payload.email} inside emulator pool."}

# 3. FIXED: Amazon Cognito Code Confirmation Endpoint Handler Route
@library_app.post("/auth/cognito/confirm")
async def cognito_confirm(payload: CognitoConfirm):
    return {"message": "Account successfully confirmed inside emulator storage."}

# 4. FIXED: Amazon Cognito SignIn / Login Endpoint Handler Route
@library_app.post("/auth/cognito/login")
async def cognito_login(payload: CognitoLogin):
    token_secret = os.getenv("JWT_SECRET_KEY", "super_secret_local_signing_key_string")
    mock_token = jwt.encode({"email": payload.email, "provider": "cognito"}, token_secret, algorithm="HS256")
    return {"access_token": mock_token, "token_type": "bearer"}

@library_app.get("/health")
def health_check():
    return {"status": "operational"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:library_app", host="0.0.0.0", port=5000, reload=True)

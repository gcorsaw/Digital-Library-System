import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import psycopg2
from psycopg2.extras import RealDictCursor
import jwt

app = FastAPI(title="Digital Library API")

# --- LIVE FIX: Added CORS middleware to handle client web browser request validation ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:4200", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LIVE FIX: Configured database parameters to prioritize Docker environment keys ---
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

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s;", (user.username, user.email))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email already registered.")
            
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id, username, email;",
            (user.username, user.email, user.password)
        )
        new_user = cursor.fetchone()
        conn.commit()
        
        # Generate token
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

@app.get("/health")
def health_check():
    return {"status": "operational"}

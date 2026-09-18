import os

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv


# --------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY is missing")


# --------------------------------------------------
# SUPABASE CLIENT
# --------------------------------------------------

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

app = FastAPI(
    title="SnapFix User API",
    description="User creation and role management API",
    version="1.0.0"
)


# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------

class CreateUserRequest(BaseModel):
    email: EmailStr


# --------------------------------------------------
# ROOT
# --------------------------------------------------

@app.get("/")
def root():

    return {
        "status": "online",
        "service": "SnapFix User API"
    }


# ==================================================
# ROUTE 1
# FETCH USER ROLE BY EMAIL
# ==================================================

@app.get("/user-role")
def get_user_role(
    email: EmailStr = Query(...)
):

    email = str(email).strip().lower()

    try:

        response = (
            supabase
            .table("users")
            .select("email, role")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if not response.data:

            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        user = response.data[0]

        return {
            "success": True,
            "email": user["email"],
            "role": user["role"]
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user role: {str(e)}"
        )


# ==================================================
# ROUTE 2
# CREATE USER
# ==================================================

@app.post("/create-user")
def create_user(
    user: CreateUserRequest
):

    email = str(user.email).strip().lower()

    try:

        # ------------------------------------------
        # CHECK IF USER ALREADY EXISTS
        # ------------------------------------------

        existing_user = (
            supabase
            .table("users")
            .select("email, role")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if existing_user.data:

            return {
                "success": True,
                "message": "User already exists",
                "email": existing_user.data[0]["email"],
                "role": existing_user.data[0]["role"]
            }

        # ------------------------------------------
        # CREATE USER
        # ------------------------------------------

        new_user = {
            "email": email,
            "role": "user"
        }

        response = (
            supabase
            .table("users")
            .insert(new_user)
            .execute()
        )

        if not response.data:

            raise HTTPException(
                status_code=500,
                detail="User could not be created"
            )

        created_user = response.data[0]

        return {
            "success": True,
            "message": "User created successfully",
            "email": created_user["email"],
            "role": created_user["role"]
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )
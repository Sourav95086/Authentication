import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY is missing")


# ============================================================
# SUPABASE CLIENT
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="SnapFix User API",
    description="User management, issue history and reward points API",
    version="2.0.0"
)


# ============================================================
# REQUEST MODELS
# ============================================================

class CreateUserRequest(BaseModel):
    email: EmailStr


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "SnapFix User API",
        "version": "2.0.0"
    }


# ============================================================
# ROUTE 1
# FETCH USER ROLE BY EMAIL
# ============================================================

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


# ============================================================
# ROUTE 2
# CREATE USER
# ============================================================

@app.post("/create-user")
def create_user(
    user: CreateUserRequest
):

    email = str(user.email).strip().lower()

    try:

        # ----------------------------------------------------
        # CHECK IF USER ALREADY EXISTS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

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


# ============================================================
# ROUTE 3
# FETCH ALL ISSUES REPORTED BY EMAIL
# ============================================================

@app.get("/user-issues")
def get_user_issues(
    email: EmailStr = Query(...)
):

    email = str(email).strip().lower()

    try:

        response = (
            supabase
            .table("issue_reports")
            .select(
                """
                report_id,
                issue_id,
                issue_description,
                reported_by_name,
                reported_by_phone,
                reported_by_email,
                reported_on,
                evidence,
                issue_location,
                latitude,
                longitude
                """
            )
            .eq("reported_by_email", email)
            .order("reported_on", desc=True)
            .execute()
        )

        issues = response.data or []

        return {
            "success": True,
            "email": email,
            "total_reports": len(issues),
            "issues": issues
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user issues: {str(e)}"
        )


# ============================================================
# ROUTE 4
# PROCESS USER POINTS
#
# Points = Number of reports × 10
#
# If email is provided:
#     Process only that user.
#
# If email is not provided:
#     Process all users.
# ============================================================

@app.post("/process-user-points")
def process_user_points(
    email: Optional[EmailStr] = Query(None)
):

    try:

        # ====================================================
        # PROCESS ONE USER
        # ====================================================

        if email:

            normalized_email = str(email).strip().lower()

            response = (
                supabase
                .table("issue_reports")
                .select(
                    "reported_by_name, reported_by_email"
                )
                .eq(
                    "reported_by_email",
                    normalized_email
                )
                .execute()
            )

            reports = response.data or []

            if not reports:

                raise HTTPException(
                    status_code=404,
                    detail="No reports found for this email"
                )

            number_of_reports = len(reports)

            # Use the name from the first report
            name = reports[0].get("reported_by_name")

            if not name:
                name = "Unknown User"

            points = number_of_reports * 10

            user_points = {
                "name": name,
                "email": normalized_email,
                "number_of_reports": number_of_reports,
                "points": points
            }

            # ------------------------------------------------
            # UPSERT
            # ------------------------------------------------

            saved = (
                supabase
                .table("user_points")
                .upsert(
                    user_points,
                    on_conflict="email"
                )
                .execute()
            )

            if not saved.data:

                raise HTTPException(
                    status_code=500,
                    detail="Failed to save user points"
                )

            result = saved.data[0]

            return {
                "success": True,
                "message": "User points processed successfully",
                "user": {
                    "name": result["name"],
                    "email": result["email"],
                    "number_of_reports": result["number_of_reports"],
                    "points": result["points"]
                }
            }

        # ====================================================
        # PROCESS ALL USERS
        # ====================================================

        response = (
            supabase
            .table("issue_reports")
            .select(
                "reported_by_name, reported_by_email"
            )
            .not_.is_("reported_by_email", "null")
            .execute()
        )

        reports = response.data or []

        if not reports:

            return {
                "success": True,
                "message": "No reports found",
                "processed_users": 0,
                "users": []
            }

        # ----------------------------------------------------
        # GROUP REPORTS BY EMAIL
        # ----------------------------------------------------

        users = {}

        for report in reports:

            user_email = report.get("reported_by_email")

            if not user_email:
                continue

            user_email = user_email.strip().lower()

            if user_email not in users:

                users[user_email] = {
                    "name": report.get(
                        "reported_by_name",
                        "Unknown User"
                    ),
                    "email": user_email,
                    "number_of_reports": 0
                }

            users[user_email]["number_of_reports"] += 1

        # ----------------------------------------------------
        # CALCULATE POINTS
        # ----------------------------------------------------

        processed_users = []

        for user_email, user_data in users.items():

            number_of_reports = user_data[
                "number_of_reports"
            ]

            points = number_of_reports * 10

            user_points = {
                "name": user_data["name"],
                "email": user_email,
                "number_of_reports": number_of_reports,
                "points": points
            }

            saved = (
                supabase
                .table("user_points")
                .upsert(
                    user_points,
                    on_conflict="email"
                )
                .execute()
            )

            if saved.data:

                result = saved.data[0]

                processed_users.append({
                    "name": result["name"],
                    "email": result["email"],
                    "number_of_reports": result[
                        "number_of_reports"
                    ],
                    "points": result["points"]
                })

        return {
            "success": True,
            "message": "All user points processed successfully",
            "processed_users": len(processed_users),
            "users": processed_users
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process user points: {str(e)}"
        )


# ============================================================
# ROUTE 5
# FETCH USER POINT DETAILS
#
# Optional email:
#     /user-points?email=test@gmail.com
#
# Without email:
#     /user-points
#     returns all users
# ============================================================

@app.get("/user-points")
def get_user_points(
    email: Optional[EmailStr] = Query(None)
):

    try:

        # ====================================================
        # FETCH ONE USER
        # ====================================================

        if email:

            normalized_email = str(email).strip().lower()

            response = (
                supabase
                .table("user_points")
                .select(
                    "name, email, number_of_reports, points, updated_at"
                )
                .eq("email", normalized_email)
                .limit(1)
                .execute()
            )

            if not response.data:

                raise HTTPException(
                    status_code=404,
                    detail="User points not found"
                )

            user = response.data[0]

            return {
                "success": True,
                "user": user
            }

        # ====================================================
        # FETCH ALL USERS
        # ====================================================

        response = (
            supabase
            .table("user_points")
            .select(
                "name, email, number_of_reports, points, updated_at"
            )
            .order(
                "points",
                desc=True
            )
            .execute()
        )

        users = response.data or []

        return {
            "success": True,
            "total_users": len(users),
            "users": users
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user points: {str(e)}"
        )
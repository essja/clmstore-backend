"""
CLMStore — Authentication Router
Handles registration, login, logout, token refresh, password reset, OTP, OAuth.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.auth.jwt import create_access_token, create_refresh_token
from app.schemas.common import AuthResponse, AuthTokenData, MessageResponse, Token
from app.schemas.user import (
    EmailVerifyRequest,
    ForgotPasswordRequest,
    PhoneVerifyRequest,
    ResetPasswordRequest,
    TokenRefreshRequest,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


# ── POST /api/v1/auth/register ────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    service = AuthService(db)
    user = await service.register_user(body)

    # Auto-login: generate tokens so the frontend can sign in immediately
    access_token = create_access_token({"sub": str(user.id), "role": user.role.value, "email": user.email})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Persist refresh token so /auth/refresh works after registration
    from hashlib import sha256
    from datetime import datetime, timezone, timedelta
    from app.models.user import RefreshToken
    from app.repositories.user_repository import RefreshTokenRepository
    ref_hash = sha256(refresh_token.encode()).hexdigest()
    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=ref_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    refresh_repo = RefreshTokenRepository(db)
    await refresh_repo.create_or_replace(db_refresh)

    user_data = UserProfileResponse.model_validate(user).model_dump()
    return AuthResponse(data=AuthTokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_data,
    ))


# ── POST /api/v1/auth/login ───────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login and obtain JWT tokens",
)
async def login(
    body: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    service = AuthService(db)
    user, access_token, refresh_token = await service.authenticate_user(body)
    user_data = UserProfileResponse.model_validate(user).model_dump()
    return AuthResponse(data=AuthTokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_data,
    ))


# ── POST /api/v1/auth/login/oauth2 ───────────────────────────────────────────
@router.post(
    "/login/oauth2",
    response_model=Token,
    summary="OAuth2 form-based login (Swagger UI)",
    include_in_schema=False,
)
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    body = UserLoginRequest(email=form_data.username, password=form_data.password)
    service = AuthService(db)
    user, access_token, refresh_token = await service.authenticate_user(body)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role.value,
        email=user.email,
    )


# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh JWT access token",
    description="Rotates the refresh token and returns a new access token.",
)
async def refresh_token(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    **Request Body:**
    ```json
    {"refresh_token": "eyJ..."}
    ```
    """
    service = AuthService(db)
    new_access, new_refresh = await service.refresh_tokens(body.refresh_token)
    # Decode to get email/role for response
    from app.auth.jwt import decode_token
    payload = decode_token(new_access, expected_type="access")
    return Token(
        access_token=new_access,
        refresh_token=new_refresh,
        role=payload.get("role", "customer"),
        email=payload.get("email", ""),
    )


# ── POST /api/v1/auth/logout ──────────────────────────────────────────────────
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout — revoke refresh token",
    description="Revokes the user's current refresh token.",
)
async def logout(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MessageResponse:
    service = AuthService(db)
    await service.logout_user(body.refresh_token)
    return MessageResponse(message="Logged out successfully.")


# ── GET /api/v1/auth/me ───────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(current_user: User = Depends(get_current_active_user)) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user)


# ── POST /api/v1/auth/verify/phone ───────────────────────────────────────────
@router.post(
    "/verify/phone",
    response_model=MessageResponse,
    summary="Verify phone number via OTP",
    description="Validates a 6-digit OTP sent to the user's phone number.",
)
async def verify_phone(
    body: PhoneVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Request Body:**
    ```json
    {"phone": "+23276123456", "otp_code": "123456"}
    ```
    """
    service = AuthService(db)
    await service.verify_phone_otp(body.phone, body.otp_code)
    return MessageResponse(message="Phone number verified successfully.")


# ── POST /api/v1/auth/verify/phone/resend ────────────────────────────────────
@router.post(
    "/verify/phone/resend",
    response_model=MessageResponse,
    summary="Resend phone OTP",
    description="Re-sends the verification OTP to the user's phone number.",
)
async def resend_phone_otp(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = AuthService(db)
    await service.send_phone_verification_otp(current_user)
    return MessageResponse(message="Verification code sent to your phone.")


# ── POST /api/v1/auth/verify/email ───────────────────────────────────────────
@router.post(
    "/verify/email",
    response_model=MessageResponse,
    summary="Verify email address via token",
    description="Validates the email verification token sent to the user's inbox.",
)
async def verify_email(
    body: EmailVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Request Body:**
    ```json
    {"token": "eyJ..."}
    ```
    """
    from app.auth.jwt import decode_token
    from app.repositories.user_repository import UserRepository
    payload = decode_token(body.token, expected_type="email_verify")
    user_id = int(payload["sub"])
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        from app.exceptions.custom import NotFoundException
        raise NotFoundException("User")
    user.is_email_verified = True
    db.add(user)
    return MessageResponse(message="Email verified successfully.")


# ── POST /api/v1/auth/forgot-password ────────────────────────────────────────
@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset OTP",
    description=(
        "Sends a password reset OTP to the user's registered email. "
        "Returns 200 even if the email is not found to prevent email enumeration."
    ),
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Request Body:**
    ```json
    {"email": "john@example.com"}
    ```
    """
    service = AuthService(db)
    await service.request_password_reset(body.email)
    return MessageResponse(message="If your email is registered, a reset code has been sent.")


# ── POST /api/v1/auth/reset-password ─────────────────────────────────────────
@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with OTP",
    description="Resets user password using a valid OTP code received via email/SMS.",
)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Request Body:**
    ```json
    {
        "token": "123456",
        "new_password": "NewSecurePass@2024"
    }
    ```
    Note: `token` here is the OTP sent via email, combined with the email.
    For full OTP flow see /api/v1/auth/reset-password/otp.
    """
    from app.auth.jwt import decode_token
    from app.repositories.user_repository import UserRepository
    from app.auth.password import hash_password
    payload = decode_token(body.token, expected_type="password_reset")
    user_id = int(payload["sub"])
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        from app.exceptions.custom import NotFoundException
        raise NotFoundException("User")
    user.password_hash = hash_password(body.new_password)
    db.add(user)
    return MessageResponse(message="Password reset successfully. Please login with your new password.")


# ── POST /api/v1/auth/reset-password/otp ─────────────────────────────────────
@router.post(
    "/reset-password/otp",
    response_model=MessageResponse,
    summary="Reset password with OTP code (SMS flow)",
)
async def reset_password_with_otp(
    email: str,
    otp_code: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = AuthService(db)
    await service.reset_password_with_otp(email, otp_code, new_password)
    return MessageResponse(message="Password reset successfully.")

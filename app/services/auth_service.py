"""
CLMStore — Authentication and Session Service
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_refresh_token, decode_token, generate_otp
from app.auth.password import hash_password, verify_password
from app.exceptions.custom import (
    ConflictException,
    UnauthorizedException,
    NotFoundException,
    BusinessRuleException,
)
from app.models.user import User, RefreshToken, OTPVerification
from app.repositories.user_repository import UserRepository, RefreshTokenRepository, OTPVerificationRepository
from app.schemas.user import UserRegisterRequest, UserLoginRequest
from app.services.notification_service import NotificationService

logger = structlog.get_logger()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.refresh_repo = RefreshTokenRepository(db)
        self.otp_repo = OTPVerificationRepository(db)
        self.notif_service = NotificationService(db)

    async def register_user(self, schema: UserRegisterRequest) -> User:
        """Register a new user (default customer)."""
        existing_email = await self.user_repo.get_by_email(schema.email)
        if existing_email:
            raise ConflictException("Email address is already registered")

        phone = getattr(schema, 'phone_number', None) or schema.phone or None
        if phone:
            existing_phone = await self.user_repo.get_by_phone(phone)
            if existing_phone:
                raise ConflictException("Phone number is already registered")

        hashed = hash_password(schema.password)
        user = User(
            email=schema.email,
            phone=phone,
            password_hash=hashed,
            first_name=schema.first_name,
            last_name=schema.last_name,
            role=schema.role,
            is_active=True,
            is_email_verified=False,
            is_phone_verified=False,
        )
        await self.user_repo.create(user)
        await self.db.flush()

        # Send welcome email and verification OTP
        await self.send_phone_verification_otp(user)

        return user

    async def authenticate_user(self, schema: UserLoginRequest) -> Tuple[User, str, str]:
        """Authenticate user and return user object along with access & refresh tokens."""
        user = await self.user_repo.get_by_email(schema.email)
        if not user or user.is_deleted:
            raise UnauthorizedException("Invalid email or password")

        if not verify_password(schema.password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedException("Your account has been suspended")

        # Update last login time
        user.last_login_at = datetime.now(timezone.utc)
        if schema.onesignal_player_id:
            user.onesignal_player_id = schema.onesignal_player_id
        self.db.add(user)

        # Generate tokens
        access_token = create_access_token({"sub": str(user.id), "role": user.role.value, "email": user.email})
        refresh_token_str = create_refresh_token({"sub": str(user.id)})

        # Persist refresh token hash
        # Standard hash or simple rotation logic
        from hashlib import sha256
        ref_hash = sha256(refresh_token_str.encode()).hexdigest()
        db_refresh = RefreshToken(
            user_id=user.id,
            token_hash=ref_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await self.refresh_repo.create_or_replace(db_refresh)

        return user, access_token, refresh_token_str

    async def refresh_tokens(self, refresh_token_str: str) -> Tuple[str, str]:
        """Validate refresh token, rotate it, and return new access & refresh tokens."""
        from hashlib import sha256
        ref_hash = sha256(refresh_token_str.encode()).hexdigest()

        db_token = await self.refresh_repo.get_by_hash(ref_hash)
        if not db_token:
            raise UnauthorizedException("Invalid or expired refresh token")

        # Revoke current refresh token
        db_token.is_revoked = True
        self.db.add(db_token)

        user = await self.user_repo.get(db_token.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User is inactive or suspended")

        # Generate new tokens
        access_token = create_access_token({"sub": str(user.id), "role": user.role.value, "email": user.email})
        new_refresh_token = create_refresh_token({"sub": str(user.id)})

        # Save new refresh token
        new_ref_hash = sha256(new_refresh_token.encode()).hexdigest()
        new_db_token = RefreshToken(
            user_id=user.id,
            token_hash=new_ref_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await self.refresh_repo.create_or_replace(new_db_token)

        return access_token, new_refresh_token

    async def logout_user(self, refresh_token_str: str) -> None:
        """Revoke the current refresh token."""
        from hashlib import sha256
        ref_hash = sha256(refresh_token_str.encode()).hexdigest()
        db_token = await self.refresh_repo.get_by_hash(ref_hash)
        if db_token:
            db_token.is_revoked = True
            self.db.add(db_token)

    async def send_phone_verification_otp(self, user: User) -> None:
        """Generate and send SMS verification code."""
        if not user.phone:
            return

        otp_code = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

        # Invalidate old OTPs for phone_verify
        # Simple update:
        db_otp = OTPVerification(
            user_id=user.id,
            otp_code=otp_code,
            purpose="phone_verify",
            expires_at=expiry,
        )
        await self.otp_repo.create(db_otp)

        # Dispatch via Africa's talking
        from app.utils.constants import NotificationType
        await self.notif_service.dispatch_notification(
            user_id=user.id,
            title="Verification Code",
            body=f"Your verification code is: {otp_code}. Valid for 10 minutes.",
            notif_type=NotificationType.ACCOUNT_VERIFIED,
            recipient_phone=user.phone,
        )

    async def verify_phone_otp(self, phone: str, otp_code: str) -> User:
        """Verify OTP code and mark user's phone as verified."""
        user = await self.user_repo.get_by_phone(phone)
        if not user:
            raise NotFoundException("User")

        valid_otp = await self.otp_repo.get_valid_otp(user.id, otp_code, "phone_verify")
        if not valid_otp:
            raise BusinessRuleException("Invalid or expired OTP code")

        valid_otp.is_used = True
        user.is_phone_verified = True
        self.db.add(valid_otp)
        self.db.add(user)

        return user

    async def request_password_reset(self, email: str) -> None:
        """Initiate forgot password workflow."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Silent return to avoid email enumeration security vulnerability
            return

        otp_code = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

        db_otp = OTPVerification(
            user_id=user.id,
            otp_code=otp_code,
            purpose="password_reset",
            expires_at=expiry,
        )
        await self.otp_repo.create(db_otp)

        # Dispatch email or SMS depending on details
        from app.utils.constants import NotificationType
        await self.notif_service.dispatch_notification(
            user_id=user.id,
            title="Password Reset Code",
            body=f"Use OTP code {otp_code} to reset your password.",
            notif_type=NotificationType.SYSTEM,
            recipient_email=user.email,
        )

    async def reset_password_with_otp(self, email: str, otp_code: str, new_password: str) -> None:
        """Reset password using verified OTP code."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise NotFoundException("User")

        valid_otp = await self.otp_repo.get_valid_otp(user.id, otp_code, "password_reset")
        if not valid_otp:
            raise BusinessRuleException("Invalid or expired OTP code")

        valid_otp.is_used = True
        user.password_hash = hash_password(new_password)
        self.db.add(valid_otp)
        self.db.add(user)

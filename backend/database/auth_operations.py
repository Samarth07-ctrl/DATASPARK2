from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import secrets
import bcrypt
import logging

from .models import User, UserSession, PasswordResetToken, UserPreferences

logger = logging.getLogger(__name__)

class AuthOperations:
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_user(db: Session, username: str, email: str, password: str,
                   first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        """Create a new user account"""
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(
                or_(User.username == username, User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    raise ValueError("Username already exists")
                if existing_user.email == email:
                    raise ValueError("Email already exists")
            
            # Hash password
            password_hash = AuthOperations.hash_password(password)
            
            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name
            )
            
            db.add(user)
            db.flush()  # Get user ID
            
            # Create default preferences
            preferences = UserPreferences(
                user_id=user.id,
                theme="dark",
                notifications_enabled=True,
                auto_save_analyses=True
            )
            db.add(preferences)
            
            db.commit()
            db.refresh(user)
            
            logger.info(f"Created new user: {username} ({email})")
            return user
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            db.rollback()
            raise ValueError(f"Failed to create user: {str(e)}")
    
    @staticmethod
    def authenticate_user(db: Session, username_or_email: str, password: str) -> Optional[User]:
        """Authenticate user with username/email and password"""
        try:
            # Find user by username or email
            user = db.query(User).filter(
                or_(User.username == username_or_email, User.email == username_or_email)
            ).first()
            
            if not user:
                return None
            
            if not user.is_active:
                return None
            
            # Verify password
            if not AuthOperations.verify_password(password, user.password_hash):
                return None
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()
            
            logger.info(f"User authenticated: {user.username}")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    @staticmethod
    def create_session(db: Session, user_id: int, user_agent: Optional[str] = None,
                      ip_address: Optional[str] = None) -> UserSession:
        """Create a new user session"""
        try:
            # Generate tokens
            session_token = AuthOperations.generate_session_token()
            refresh_token = AuthOperations.generate_session_token()
            
            # Set expiration (24 hours for session, 7 days for refresh)
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
            session = UserSession(
                user_id=user_id,
                session_token=session_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            logger.info(f"Created session for user {user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_user_by_session_token(db: Session, session_token: str) -> Optional[User]:
        """Get user by session token"""
        try:
            session = db.query(UserSession).filter(
                and_(
                    UserSession.session_token == session_token,
                    UserSession.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not session:
                return None
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            db.commit()
            
            return session.user
            
        except Exception as e:
            logger.error(f"Error getting user by session token: {e}")
            return None
    
    @staticmethod
    def logout_user(db: Session, session_token: str) -> bool:
        """Logout user by invalidating session"""
        try:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token
            ).first()
            
            if session:
                db.delete(session)
                db.commit()
                logger.info(f"User logged out: {session.user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            return False
    
    @staticmethod
    def refresh_session(db: Session, refresh_token: str) -> Optional[UserSession]:
        """Refresh user session with refresh token"""
        try:
            session = db.query(UserSession).filter(
                UserSession.refresh_token == refresh_token
            ).first()
            
            if not session:
                return None
            
            # Generate new tokens
            session.session_token = AuthOperations.generate_session_token()
            session.refresh_token = AuthOperations.generate_session_token()
            session.expires_at = datetime.utcnow() + timedelta(hours=24)
            session.last_activity = datetime.utcnow()
            
            db.commit()
            db.refresh(session)
            
            logger.info(f"Session refreshed for user {session.user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error refreshing session: {e}")
            return None
    
    @staticmethod
    def create_password_reset_token(db: Session, email: str) -> Optional[PasswordResetToken]:
        """Create password reset token"""
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return None
            
            # Invalidate existing tokens
            db.query(PasswordResetToken).filter(
                and_(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used == False
                )
            ).update({"used": True})
            
            # Create new token
            token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
            )
            
            db.add(reset_token)
            db.commit()
            db.refresh(reset_token)
            
            logger.info(f"Password reset token created for user {user.id}")
            return reset_token
            
        except Exception as e:
            logger.error(f"Error creating password reset token: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> bool:
        """Reset password using reset token"""
        try:
            reset_token = db.query(PasswordResetToken).filter(
                and_(
                    PasswordResetToken.token == token,
                    PasswordResetToken.used == False,
                    PasswordResetToken.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not reset_token:
                return False
            
            # Update password
            user = reset_token.user
            user.password_hash = AuthOperations.hash_password(new_password)
            
            # Mark token as used
            reset_token.used = True
            
            # Invalidate all sessions
            db.query(UserSession).filter(
                UserSession.user_id == user.id
            ).delete()
            
            db.commit()
            
            logger.info(f"Password reset for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def update_user_profile(db: Session, user_id: int, **kwargs) -> Optional[User]:
        """Update user profile"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            # Update allowed fields
            allowed_fields = ['first_name', 'last_name', 'email']
            for field, value in kwargs.items():
                if field in allowed_fields and value is not None:
                    setattr(user, field, value)
            
            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)
            
            logger.info(f"Profile updated for user {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def cleanup_expired_sessions(db: Session):
        """Clean up expired sessions"""
        try:
            expired_count = db.query(UserSession).filter(
                UserSession.expires_at < datetime.utcnow()
            ).delete()
            
            db.commit()
            
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired sessions")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            db.rollback()

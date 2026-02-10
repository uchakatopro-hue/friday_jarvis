"""
Authentication and CORS middleware for FastAPI.
Provides secure token validation and cross-origin resource sharing.
"""

import logging
import os
from typing import Optional
from datetime import datetime, timedelta
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from fastapi.middleware.cors import CORSMiddleware
import hmac
import hashlib

logger = logging.getLogger(__name__)

# Security configuration from environment
AGENT_AUTH_TOKEN = os.getenv("INTERNAL_API_TOKEN", secrets.token_urlsafe(32))
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:7860",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:7860",
    "http://127.0.0.1:8000",
]

# Add Render and custom domains from env
if custom_origin := os.getenv("ALLOWED_ORIGINS"):
    ALLOWED_ORIGINS.extend(custom_origin.split(","))

# Remove duplicates
ALLOWED_ORIGINS = list(set(ALLOWED_ORIGINS))

security = HTTPBearer()


def configure_cors(app: FastAPI):
    """Configure CORS middleware for the FastAPI app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page-Count"],
        max_age=3600,
    )
    logger.info(f"CORS configured for origins: {ALLOWED_ORIGINS}")


async def verify_agent_token(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    """
    Verify agent authentication token.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        Validated token
        
    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    
    if token != AGENT_AUTH_TOKEN:
        logger.warning(f"Invalid agent token attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Invalid or expired token",
        )
    
    logger.debug("Agent token verified successfully")
    return token


async def verify_optional_agent_token(
    credentials: Optional[HTTPAuthCredentials] = Depends(security)
) -> Optional[str]:
    """
    Verify agent token, but allow requests without it for public endpoints.
    
    Args:
        credentials: HTTP Bearer credentials (optional)
        
    Returns:
        Token if provided and valid, None otherwise
        
    Raises:
        HTTPException: If token is provided but invalid
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    if token != AGENT_AUTH_TOKEN:
        logger.warning(f"Invalid token attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Invalid or expired token",
        )
    
    return token


async def verify_request_signature(
    headers: dict,
    body: bytes,
    secret: Optional[str] = None,
) -> bool:
    """
    Verify webhook request signature (for external integrations).
    
    Args:
        headers: Request headers
        body: Request body
        secret: Secret key for verification
        
    Returns:
        True if signature is valid
        
    Raises:
        HTTPException: If signature is missing or invalid
    """
    webhook_secret = secret or os.getenv("WEBHOOK_SECRET", "")
    signature = headers.get("X-Signature")
    
    if not webhook_secret or not signature:
        logger.warning("Webhook signature verification failed: missing secret or signature")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook signature verification failed",
        )
    
    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )
    
    return True


class TokenBucket:
    """Rate limiting using token bucket algorithm."""
    
    def __init__(self, capacity: int = 100, refill_rate: float = 10.0):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = datetime.now()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if insufficient
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = datetime.now()
        elapsed = (now - self.last_refill).total_seconds()
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now


class RateLimiter:
    """Simple rate limiter for API endpoints."""
    
    def __init__(self):
        self.buckets: dict[str, TokenBucket] = {}
    
    def get_bucket(self, key: str) -> TokenBucket:
        """Get or create token bucket for key."""
        if key not in self.buckets:
            self.buckets[key] = TokenBucket()
        return self.buckets[key]
    
    def is_allowed(self, key: str, tokens: int = 1) -> bool:
        """Check if request is allowed under rate limit."""
        return self.get_bucket(key).consume(tokens)
    
    def cleanup(self):
        """Remove old buckets to free memory."""
        # Keep only recently used buckets
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        self.buckets = {
            key: bucket
            for key, bucket in self.buckets.items()
            if bucket.last_refill > cutoff
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


class RequestLogger:
    """Log HTTP requests for debugging and monitoring."""
    
    @staticmethod
    async def log_request(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str] = None,
    ):
        """Log request details."""
        logger.info(
            f"{method} {path} - {status_code} ({duration_ms:.2f}ms)" +
            (f" [user: {user_id}]" if user_id else "")
        )


# Export main functions and classes
__all__ = [
    "configure_cors",
    "verify_agent_token",
    "verify_optional_agent_token",
    "verify_request_signature",
    "TokenBucket",
    "RateLimiter",
    "RequestLogger",
    "rate_limiter",
    "AGENT_AUTH_TOKEN",
    "ALLOWED_ORIGINS",
]

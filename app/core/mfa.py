"""
MFA (Multi-Factor Authentication) utilities using TOTP.
"""

import io
from base64 import b64encode

import pyotp
import qrcode


class MFAService:
    """Service for handling TOTP-based MFA."""

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(secret: str, email: str, issuer: str = "FastAPI App") -> str:
        """Generate provisioning URI for QR code."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)

    @staticmethod
    def generate_qr_code(provisioning_uri: str) -> str:
        """Generate QR code as base64 image."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return b64encode(buffer.getvalue()).decode()

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """Verify TOTP code."""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)  # Allow 30s window

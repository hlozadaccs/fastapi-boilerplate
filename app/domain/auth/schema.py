from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str  # base64 encoded image
    provisioning_uri: str


class MFAEnableRequest(BaseModel):
    code: str


class MFAVerifyRequest(BaseModel):
    code: str

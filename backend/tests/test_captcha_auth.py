"""Unit tests for CAPTCHA authentication verification logic."""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException

from app.api.auth_routes import LoginRequest, verify_captcha_token
from app.config import Settings


def test_login_request_captcha_fields():
    # Both None
    req1 = LoginRequest(email="test@lmcs.gov.in", password="secretpassword")
    assert req1.token_value is None

    # snake_case
    req2 = LoginRequest(
        email="test@lmcs.gov.in",
        password="secretpassword",
        captcha_token="jwt_token_123",
    )
    assert req2.token_value == "jwt_token_123"

    # camelCase
    req3 = LoginRequest(
        email="test@lmcs.gov.in",
        password="secretpassword",
        captchaToken="jwt_token_456",
    )
    assert req3.token_value == "jwt_token_456"


def test_settings_is_captcha_active():
    s_disabled = Settings(captcha_enabled=False, captcha_secret_key="")
    assert not s_disabled.is_captcha_active

    s_secret = Settings(captcha_enabled=False, captcha_secret_key="secret-key-32-chars")
    assert s_secret.is_captcha_active

    s_enabled = Settings(captcha_enabled=True, captcha_secret_key="")
    assert s_enabled.is_captcha_active


@pytest.mark.asyncio
async def test_verify_captcha_token_success():
    settings = Settings(
        captcha_api_url="http://captcha.test",
        captcha_secret_key="test_secret",
        captcha_enabled=True,
    )

    mock_resp = AsyncMock()
    mock_resp.json.return_value = {
        "success": True,
        "challengeTimestamp": 1789849397,
        "hostname": "localhost",
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
        result = await verify_captcha_token("valid_token_abc", settings)
        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://captcha.test/api/v1/siteverify"


@pytest.mark.asyncio
async def test_verify_captcha_token_failure():
    settings = Settings(
        captcha_api_url="http://captcha.test",
        captcha_secret_key="test_secret",
        captcha_enabled=True,
    )

    mock_resp = AsyncMock()
    mock_resp.json.return_value = {
        "success": False,
        "errorCodes": ["timeout-or-duplicate"],
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        result = await verify_captcha_token("replayed_token", settings)
        assert result is False


@pytest.mark.asyncio
async def test_verify_captcha_token_service_unavailable():
    settings = Settings(
        captcha_api_url="http://captcha.test",
        captcha_secret_key="test_secret",
        captcha_enabled=True,
    )

    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        result = await verify_captcha_token("some_token", settings)
        assert result is False


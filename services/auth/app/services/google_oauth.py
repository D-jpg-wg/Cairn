from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from starlette import status

from app.core.config import setting

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPE = "openid email profile"


class GoogleOAuthClient:
    """Инкапсулирует взаимодействие с Google по протоколу OAuth 2.0.

    Знает только про Google: строит ссылку авторизации, меняет code на токены
    и достаёт email. Доменной логики (пользователи, JWT) здесь нет.
    """

    def __init__(self) -> None:
        self._client_id = setting.google_client_id
        self._client_secret = setting.google_client_secret
        self._redirect_uri = setting.google_redirect_url

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": _SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def fetch_email(self, code: str) -> str:
        """Меняет authorization code на access token и возвращает email."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                token_res = await client.post(
                    _TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": self._redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                token_res.raise_for_status()
                access_token = token_res.json().get("access_token")
                if not access_token:
                    raise ValueError("no access_token in response")

                userinfo_res = await client.get(
                    _USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                userinfo_res.raise_for_status()
                email = userinfo_res.json().get("email")
                if not email:
                    raise ValueError("no email in userinfo")
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Google authentication failed",
                ) from exc

        return email

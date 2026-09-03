import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from livecomment.errors import OAuthError
from livecomment.oauth import (
    OAuthClient,
    TokenStore,
    _build_authorization_url,
    _open_browser,
    refresh_access_token,
)


class RefreshAccessTokenTests(unittest.TestCase):
    def test_reauthorizes_when_refresh_token_is_invalid_grant(self):
        client = OAuthClient(
            client_id="client-id",
            client_secret="client-secret",
            auth_uri="https://example.test/auth",
            token_uri="https://example.test/token",
        )
        with TemporaryDirectory() as directory:
            token_path = Path(directory) / "token.json"
            token_path.write_text(
                json.dumps(
                    {
                        "access_token": "old-access-token",
                        "expires_at": 0,
                        "refresh_token": "revoked-refresh-token",
                        "scope": "scope-a",
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch(
                    "livecomment.oauth.post_form",
                    side_effect=OAuthError(
                        "OAuth request failed: invalid_grant: Token has been expired or revoked.",
                        error="invalid_grant",
                        description="Token has been expired or revoked.",
                    ),
                ),
                patch(
                    "livecomment.oauth.authorize",
                    return_value={"access_token": "new-access-token"},
                ) as authorize,
                patch("sys.stdout"),
            ):
                access_token = refresh_access_token(client, TokenStore(token_path), scope="scope-a")

        self.assertEqual(access_token, "new-access-token")
        authorize.assert_called_once()
        self.assertTrue(authorize.call_args.kwargs["force"])

    def test_raises_other_oauth_refresh_errors(self):
        client = OAuthClient(
            client_id="client-id",
            client_secret=None,
            auth_uri="https://example.test/auth",
            token_uri="https://example.test/token",
        )
        with TemporaryDirectory() as directory:
            token_path = Path(directory) / "token.json"
            token_path.write_text(
                json.dumps(
                    {
                        "access_token": "old-access-token",
                        "expires_at": 0,
                        "refresh_token": "refresh-token",
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "livecomment.oauth.post_form",
                side_effect=OAuthError("OAuth request failed: temporarily_unavailable"),
            ):
                with self.assertRaises(OAuthError):
                    refresh_access_token(client, TokenStore(token_path))


class OpenBrowserTests(unittest.TestCase):
    def test_authorization_url_contains_required_response_type(self):
        client = OAuthClient(
            client_id="client-id",
            client_secret="client-secret",
            auth_uri="https://example.test/auth",
            token_uri="https://example.test/token",
        )

        url = _build_authorization_url(
            client,
            redirect_uri="http://127.0.0.1:12345/callback",
            scope="scope-a",
            state="state-a",
            challenge="challenge-a",
        )
        params = parse_qs(urlparse(url).query)

        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["client_id"], ["client-id"])

    def test_opens_windows_browser_on_wsl_without_shell_parsing(self):
        url = "https://example.test/auth?client_id=test&response_type=code"
        with (
            patch("livecomment.oauth._is_wsl", return_value=True),
            patch("livecomment.oauth.subprocess.run") as run,
        ):
            run.return_value.returncode = 0

            self.assertTrue(_open_browser(url))

        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["explorer.exe", url])

    def test_skips_webbrowser_without_display(self):
        with (
            patch("livecomment.oauth._is_wsl", return_value=False),
            patch.dict("livecomment.oauth.os.environ", {}, clear=True),
            patch("livecomment.oauth.webbrowser.open") as open_browser,
        ):
            self.assertFalse(_open_browser("https://example.test/auth"))

        open_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()

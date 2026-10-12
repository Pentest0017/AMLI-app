"""
Custom Email Backends for CISO Assistant
Provides Microsoft 365 / Exchange Online OAuth 2.0 (XOAUTH2) SMTP Backend using Entra ID Client Credentials.
"""

import base64
import json
import urllib.parse
import urllib.request
from django.core.mail.backends.smtp import EmailBackend
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
import structlog

logger = structlog.getLogger(__name__)


class M365OAuthEmailBackend(EmailBackend):
    """
    Custom Django Email Backend for Microsoft 365 / Exchange Online Modern Auth (XOAUTH2).
    Acquires an OAuth 2.0 Access Token from Microsoft Entra ID via Client Credentials Grant Flow,
    then authenticates to smtp.office365.com using XOAUTH2 over TLS.
    """

    def __init__(
        self,
        tenant_id=None,
        client_id=None,
        client_secret=None,
        from_email=None,
        *args,
        **kwargs,
    ):
        self.tenant_id = tenant_id or getattr(settings, "MICROSOFT_TENANT_ID", None)
        self.client_id = client_id or getattr(settings, "MICROSOFT_CLIENT_ID", None)
        self.client_secret = client_secret or getattr(settings, "MICROSOFT_CLIENT_SECRET", None)
        self.from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)

        kwargs.setdefault("host", getattr(settings, "EMAIL_HOST", "smtp.office365.com"))
        kwargs.setdefault("port", int(getattr(settings, "EMAIL_PORT", 587)))
        kwargs.setdefault("use_tls", getattr(settings, "EMAIL_USE_TLS", True))
        kwargs.setdefault("use_ssl", getattr(settings, "EMAIL_USE_SSL", False))
        kwargs.setdefault("timeout", getattr(settings, "EMAIL_TIMEOUT", 10))

        super().__init__(*args, **kwargs)

    def _get_oauth_access_token(self) -> str:
        """
        Fetch an OAuth 2.0 Access Token from Entra ID token endpoint using Client Credentials flow.
        """
        if not self.tenant_id or not self.client_id or not self.client_secret:
            raise ImproperlyConfigured(
                "Microsoft 365 OAuth authentication requires MICROSOFT_TENANT_ID, "
                "MICROSOFT_CLIENT_ID, and MICROSOFT_CLIENT_SECRET to be configured."
            )

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://outlook.office365.com/.default",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            timeout_val = self.timeout if self.timeout else 10
            with urllib.request.urlopen(req, timeout=timeout_val) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                return res_body["access_token"]
        except Exception as e:
            logger.error(
                "Failed to acquire OAuth 2.0 token from Microsoft Entra ID",
                error_type=type(e).__name__,
            )
            raise RuntimeError(
                f"Microsoft 365 OAuth token acquisition failed: {e}"
            ) from e

    def open(self):
        """
        Open SMTP connection and authenticate via XOAUTH2 mechanism.
        """
        if self.connection:
            return False

        connection_created = super().open()
        if not connection_created or not self.connection:
            return False

        if self.tenant_id and self.client_id and self.client_secret:
            try:
                access_token = self._get_oauth_access_token()
                auth_string = (
                    f"user={self.from_email}\x01auth=Bearer {access_token}\x01\x01"
                )
                auth_b64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
                code, resp = self.connection.docmd("AUTH", f"XOAUTH2 {auth_b64}")
                if code not in (235, 250):
                    raise RuntimeError(
                        f"SMTP XOAUTH2 authentication failed with status code {code}: {resp}"
                    )
            except Exception as e:
                self.close()
                raise e

        return True

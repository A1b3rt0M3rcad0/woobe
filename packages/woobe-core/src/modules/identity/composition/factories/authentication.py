from modules.identity.composition.resources import SETTINGS
from modules.identity.presentation.authentication_response import AuthenticationCookiePolicy
from shared.security.access_tokens import AccessTokenCodec


def build_access_token_issuer() -> AccessTokenCodec:
    return AccessTokenCodec(
        signing_key=SETTINGS.secret_key,
        issuer=SETTINGS.auth_issuer,
        audience=SETTINGS.auth_audience,
        ttl_seconds=SETTINGS.access_token_ttl_seconds,
        leeway_seconds=SETTINGS.auth_clock_skew_seconds,
    )


def build_authentication_cookie_policy() -> AuthenticationCookiePolicy:
    return AuthenticationCookiePolicy(
        access_cookie_name=SETTINGS.access_cookie_name,
        access_cookie_secure=SETTINGS.access_cookie_secure,
        access_cookie_same_site=SETTINGS.access_cookie_same_site,
        refresh_cookie_name=SETTINGS.refresh_cookie_name,
        refresh_cookie_secure=SETTINGS.refresh_cookie_secure,
        refresh_cookie_same_site=SETTINGS.refresh_cookie_same_site,
        csrf_cookie_name=SETTINGS.csrf_cookie_name,
        refresh_token_ttl_days=SETTINGS.refresh_token_ttl_days,
        access_token_ttl_seconds=SETTINGS.access_token_ttl_seconds,
    )

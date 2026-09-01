from http.cookies import SimpleCookie


def build_refresh_cookie(
    *,
    name: str,
    value: str,
    max_age_seconds: int,
    secure: bool,
    same_site: str,
) -> str:
    cookie = SimpleCookie()
    cookie[name] = value
    morsel = cookie[name]
    morsel["path"] = "/identity/auth"
    morsel["httponly"] = True
    morsel["secure"] = secure
    morsel["samesite"] = same_site
    morsel["max-age"] = str(max_age_seconds)
    return morsel.OutputString()


def clear_refresh_cookie(
    *,
    name: str,
    secure: bool,
    same_site: str,
) -> str:
    return build_refresh_cookie(
        name=name,
        value="",
        max_age_seconds=0,
        secure=secure,
        same_site=same_site,
    )

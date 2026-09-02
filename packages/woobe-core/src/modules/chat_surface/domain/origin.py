from urllib.parse import urlsplit

from shared.contracts.errors import ValidationError


def normalize_origin(value: str, *, allow_insecure: bool = False) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if (
        not parsed.scheme
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValidationError("ChatSurface origins must be exact origins")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if "*" in hostname:
        raise ValidationError("ChatSurface origins cannot contain wildcards")
    if scheme not in {"http", "https"}:
        raise ValidationError("ChatSurface origins must use HTTP(S)")
    if scheme != "https" and not allow_insecure:
        raise ValidationError("ChatSurface origins must use HTTPS")
    default_port = 443 if scheme == "https" else 80
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("ChatSurface origin port is invalid") from exc
    display_hostname = f"[{hostname}]" if ":" in hostname else hostname
    authority = (
        display_hostname
        if port in {None, default_port}
        else f"{display_hostname}:{port}"
    )
    return f"{scheme}://{authority}"


__all__ = ["normalize_origin"]

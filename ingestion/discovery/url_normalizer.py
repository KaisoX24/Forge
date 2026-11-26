from urllib.parse import urlsplit,urlunsplit

def normalize_url(url:str) -> str:
    "Normalizes HTTP url for dedeuplication"

    parsed=urlsplit(url.strip())

    if parsed.scheme.lower() not in {'http','https'}:
        raise ValueError(f"Unsupported URL scheme: {url}")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Invalid URL: {url}")

    try:
        port=parsed.port

    except ValueError as exc:
        raise ValueError(f"Invalid URL port: {url}") from exc

    scheme=parsed.scheme.lower()
    hostname=parsed.hostname.lower()

    # IPv6 formatiing
    if ':' in hostname:
        hostname=f'[{hostname}]'

    if port and not(
        (scheme=='http' and port==80)
        or (scheme=='https' and port==443)
    ):
        netloc=f'{hostname}:{port}'
    else:
        netloc=hostname

    path=parsed.path or '/'

    path=path.rstrip("/") or "/"

    last_segment=path.rsplit("/",1)[-1]

    if path != "/" and "." not in last_segment:
        path += "/"

    return urlunsplit((
        scheme,
        netloc,
        path,
        parsed.query,
        ""
    ))

def normalize_urls(urls: list[str]) -> list[str]:
    """Normalize URLs and remove duplicates while preserving order."""

    normalized = []
    seen = set()

    for url in urls:
        try:
            value = normalize_url(url)
        except ValueError:
            continue

        if value not in seen:
            seen.add(value)
            normalized.append(value)

    return normalized 
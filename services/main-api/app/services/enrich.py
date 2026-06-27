import httpx
from bs4 import BeautifulSoup

_TIMEOUT = 10.0
_MAX_CHARS = 20_000
_HEADERS = {"User-Agent": "CairnBot/0.1"}


def extract_from_url(url: str) -> tuple[str | None, str]:
    """Скачивает страницу → (заголовок, текст).

    Бросает httpx.HTTPError при сетевой проблеме/плохом статусе
    и ValueError, если контент не HTML.
    """
    with httpx.Client(
        timeout=_TIMEOUT,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()

    if "html" not in resp.headers.get("content-type", "").lower():
        raise ValueError("Содержимое не HTML")

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else None

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return title, text[:_MAX_CHARS]

import httpx
import trafilatura
from bs4 import BeautifulSoup

_TIMEOUT = 10.0
_MAX_CHARS = 20_000
_HEADERS = {"User-Agent": "CairnBot/0.1"}


def extract_from_url(url: str) -> tuple[str | None, str]:
    """Скачивает страницу → (заголовок, основной текст).

    Текст извлекается trafilatura — только содержательная часть статьи, без
    навигации, подвалов, баннеров и комментариев. Если trafilatura ничего не
    нашла (нестандартная/слишком короткая страница) — грубый bs4-fallback.

    Бросает httpx.HTTPError при сетевой проблеме/плохом статусе и ValueError,
    если контент не HTML или текст извлечь не удалось.
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

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else None

    text = _extract_main(html, url) or _extract_fallback(soup)
    if not text:
        raise ValueError("Не удалось извлечь текст")
    return title, text[:_MAX_CHARS]


def _extract_main(html: str, url: str) -> str:
    """Основной текст статьи через trafilatura — без обвязки страницы."""
    return (
        trafilatura.extract(
            html,
            url=url,
            favor_precision=True,  # лучше отбросить сомнительное, чем притащить мусор
            include_comments=False,
            include_tables=False,
        )
        or ""
    )


def _extract_fallback(soup: BeautifulSoup) -> str:
    """Запасной путь: выкинуть явную обвязку и собрать оставшийся текст."""
    for tag in soup(
        ["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]
    ):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())

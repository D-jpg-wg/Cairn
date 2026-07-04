"""Мелочи, общие для хендлеров, ходящих в main-api."""

ENTRIES_PATH = "/api/v1/entries/"  # слэш обязателен: без него запрос уйдёт в статику


def bearer(access: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access}"}

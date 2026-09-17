from text_unidecode import unidecode


def transliterate(text: str) -> str:
    return " ".join(unidecode(text).split())

import unicodedata


def detect_script(value: str) -> str:
    scripts = set()
    for char in value:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        for term, code in (
            ("LATIN", "Latn"),
            ("CYRILLIC", "Cyrl"),
            ("ARABIC", "Arab"),
            ("HEBREW", "Hebr"),
            ("CJK", "Hani"),
            ("HIRAGANA", "Hira"),
            ("KATAKANA", "Kana"),
            ("HANGUL", "Hang"),
            ("GREEK", "Grek"),
            ("DEVANAGARI", "Deva"),
            ("BENGALI", "Beng"),
            ("THAI", "Thai"),
        ):
            if term in name:
                scripts.add(code)
                break
    if scripts and scripts <= {"Hani", "Hira", "Kana"} and scripts & {"Hira", "Kana"}:
        return "Jpan"
    return next(iter(scripts)) if len(scripts) == 1 else "Zyyy"

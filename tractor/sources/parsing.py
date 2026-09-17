from html.parser import HTMLParser


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "iframe", "object"}:
            self.blocked += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "iframe", "object"}:
            self.blocked = max(0, self.blocked - 1)

    def handle_data(self, data: str) -> None:
        if not self.blocked:
            self.parts.append(data)


def plain_text(value: str) -> str:
    parser = TextParser()
    parser.feed(value[:500_000])
    return " ".join(" ".join(parser.parts).split())


def string_value(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(map(str, value))
    return str(value) if value is not None else ""

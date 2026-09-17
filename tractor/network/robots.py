from urllib.robotparser import RobotFileParser


def allows_crawl(robots_text: str, url: str, user_agent: str = "TRACTOR") -> bool:
    """For future page adapters; current adapters use official metadata APIs only.

    The caller must obtain robots.txt through its policy-controlled network context.
    A retrieval failure should be treated as unavailable, never as blanket permission.
    """
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(user_agent, url)

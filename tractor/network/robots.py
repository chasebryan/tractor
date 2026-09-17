from protego import Protego


def allows_crawl(robots_text: str, url: str, user_agent: str = "TRACTOR") -> bool:
    """The caller must retrieve the policy through the source's network context.

    An unreachable policy must not be replaced with an empty, permissive policy.
    """
    return Protego.parse(robots_text).can_fetch(url, user_agent)

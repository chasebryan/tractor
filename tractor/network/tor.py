from tractor.network.client import NetworkClient


class TorClient(NetworkClient):
    """Only explicitly registered public onion hosts; no Tor process is started here."""

    def __init__(self, onion_hosts: frozenset[str], proxy: str = "socks5h://127.0.0.1:9050"):
        if not onion_hosts or any(not host.endswith(".onion") for host in onion_hosts):
            raise ValueError("Register only explicit public onion hostnames.")
        super().__init__(allowed_hosts=onion_hosts, proxy=proxy, tor=True)

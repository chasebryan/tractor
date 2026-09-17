from tractor.sources.archives import InternetArchive
from tractor.sources.base import SourceAdapter
from tractor.sources.code import GitHubRepositories
from tractor.sources.documents import Crossref
from tractor.sources.registries import Wikidata


def default_adapters() -> list[SourceAdapter]:
    return [Wikidata(), Crossref(), InternetArchive(), GitHubRepositories()]

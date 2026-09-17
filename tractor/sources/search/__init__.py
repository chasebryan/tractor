from tractor.sources.search.brave import BraveSearch
from tractor.sources.search.kagi import KagiSearch
from tractor.sources.search.marginalia import MarginaliaSearch
from tractor.sources.search.mojeek import MojeekSearch


def search_adapters(options=None, credentials=None):
    return [
        provider(options, credentials)
        for provider in (BraveSearch, MojeekSearch, KagiSearch, MarginaliaSearch)
    ]

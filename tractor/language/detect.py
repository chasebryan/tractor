from functools import lru_cache

from langdetect import DetectorFactory, LangDetectException
from langdetect.detector_factory import PROFILES_DIRECTORY


@lru_cache(maxsize=1)
def _factory() -> DetectorFactory:
    factory = DetectorFactory()
    factory.load_profile(PROFILES_DIRECTORY)
    factory.set_seed(0)
    return factory


def detect_language(text: str) -> str:
    # Short names and acronyms are not reliable language evidence.
    if len(text.strip()) < 35 or len(text.split()) < 5:
        return "und"
    try:
        detector = _factory().create()
        detector.append(text[:8000])
        guesses = detector.get_probabilities()
        return guesses[0].lang if guesses and guesses[0].prob >= 0.85 else "und"
    except LangDetectException:
        return "und"

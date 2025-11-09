from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0


def detect_language(text: str) -> str:
    snippet = text.strip()
    if not snippet:
        return "unknown"

    snippet = snippet[:2000]
    try:
        return detect(snippet)
    except LangDetectException:
        return "unknown"


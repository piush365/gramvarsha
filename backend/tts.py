"""Voice advisory: text -> MP3 with gTTS (free, supports en / hi / mr). Files are cached."""
from __future__ import annotations

import hashlib
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent / "cache" / "audio"


def synthesize(text: str, lang: str) -> Path:
    """Return the path of an MP3 for this text, generating it once."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIO_DIR / f"{hashlib.sha1(f'{lang}|{text}'.encode()).hexdigest()}.mp3"
    if not path.exists():
        from gtts import gTTS  # imported lazily: needs network, only on a cache miss
        tmp = path.with_suffix(".part")
        gTTS(text=text, lang=lang, tld="co.in" if lang == "en" else "com").save(str(tmp))
        tmp.rename(path)
    return path

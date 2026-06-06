"""Whisper-based transcription + content features.

Implements the Tier 2 content channel: word counts, first-person pronoun rate,
hedging words, disfluencies, words/sec. Pulls grounding from Vrij's Reality
Monitoring and Pennebaker's LIWC work — truthful narratives tend to have more
first-person pronouns and concrete detail, deceptive ones tend to have more
hedging and fewer self-references.

faster-whisper is a lazy import; if it's not installed, transcription is skipped
and the rest of the pipeline still works.
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

# Lexicons (lowercase comparison, word-boundary matched)
FIRST_PERSON = {
    "i", "i'd", "i'll", "i'm", "i've",
    "me", "my", "mine", "myself",
    "we", "we'd", "we'll", "we're", "we've",
    "us", "our", "ours", "ourselves",
}

HEDGE_WORDS = {
    "maybe", "perhaps", "possibly", "probably", "kinda", "sorta",
    "kind", "sort", "guess", "guessing", "think", "thinking",
    "suppose", "supposedly", "might", "could", "may", "seem",
    "seems", "seemed", "apparently", "supposedly", "allegedly",
    "somewhat", "fairly", "roughly", "approximately", "around",
    "about", "more-or-less", "ish",
}

DISFLUENCIES = {
    "uh", "uhh", "uhm", "um", "umm", "uhhh", "er", "erm", "ah",
    "hmm", "mhm", "hm", "like",  # "like" only when filler
    "yknow", "ya-know",
}

# Past-tense -ed regex (very rough); will miss irregulars but useful as proxy
PAST_TENSE_RE = re.compile(r"\b\w+ed\b", re.IGNORECASE)
PRESENT_TENSE_RE = re.compile(r"\b\w+(s|ing)\b", re.IGNORECASE)


_WHISPER_MODEL = None
_WHISPER_TRIED = False


def _load_whisper(model_name: str = "tiny"):
    """Lazy-load a faster-whisper model. Returns model or None if unavailable."""
    global _WHISPER_MODEL, _WHISPER_TRIED
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    if _WHISPER_TRIED:
        return None
    _WHISPER_TRIED = True
    try:
        from faster_whisper import WhisperModel
        _WHISPER_MODEL = WhisperModel(model_name, device="cpu",
                                      compute_type="int8")
        return _WHISPER_MODEL
    except Exception as e:
        print(f"[secret-squirrel] whisper unavailable ({e}); "
              f"content features disabled. pip install faster-whisper")
        return None


def transcribe(audio: np.ndarray, fs: int,
               model_name: str = "tiny") -> Optional[dict]:
    """Transcribe a mono float64 audio array. Returns:
       {"text": str, "words": [(start, end, word), ...]} or None if unavailable.
    """
    model = _load_whisper(model_name)
    if model is None:
        return None
    try:
        # faster-whisper expects 16 kHz mono float32
        audio_f32 = audio.astype(np.float32)
        if fs != 16000:
            # very rough resample — for real use, callers should already be 16k
            ratio = 16000 / fs
            n_new = int(len(audio_f32) * ratio)
            audio_f32 = np.interp(
                np.linspace(0, len(audio_f32) - 1, n_new),
                np.arange(len(audio_f32)), audio_f32
            ).astype(np.float32)
        segments, _info = model.transcribe(audio_f32, word_timestamps=True,
                                            vad_filter=True)
        text_parts = []
        words = []
        for seg in segments:
            text_parts.append(seg.text)
            if seg.words:
                for w in seg.words:
                    words.append((float(w.start), float(w.end), w.word.strip()))
        return {"text": " ".join(text_parts).strip(), "words": words}
    except Exception as e:
        print(f"[secret-squirrel] transcription failed: {e}")
        return None


def content_features(transcript: dict, duration_sec: float) -> dict:
    """Extract content-level features from a Whisper transcript dict.

    Returns a dict with:
      word_count, words_per_sec, first_person_rate, hedge_rate,
      disfluency_rate, past_tense_count, present_tense_count, text
    """
    if not transcript or not transcript.get("text"):
        return {}

    text = transcript["text"]
    # Lowercase, strip punctuation for word-set matching
    raw_words = re.findall(r"[a-zA-Z']+", text.lower())
    n = len(raw_words)
    if n == 0:
        return {"text": text, "word_count": 0}

    first_p = sum(1 for w in raw_words if w in FIRST_PERSON)
    hedges = sum(1 for w in raw_words if w in HEDGE_WORDS)
    disfl = sum(1 for w in raw_words if w in DISFLUENCIES)
    past = len(PAST_TENSE_RE.findall(text))
    pres = len(PRESENT_TENSE_RE.findall(text))

    return {
        "text": text,
        "word_count": n,
        "words_per_sec": float(n / max(duration_sec, 0.5)),
        "first_person_rate": float(first_p / n),
        "hedge_rate": float(hedges / n),
        "disfluency_rate": float(disfl / n),
        "past_tense_count": past,
        "present_tense_count": pres,
    }

import re
import unicodedata

from clipforge_worker.config import worker_settings
from clipforge_worker.highlights.candidates import finished, unresolved_ending
from clipforge_worker.highlights.models import Candidate

ENGINE_VERSION = "local-editorial-v3"
DEFAULT_WEIGHTS = {
    "hook": 25,
    "completeness": 20,
    "insight": 20,
    "emphasis": 10,
    "visual": 10,
    "novelty": 10,
    "boundaries": 5,
}
STOPWORDS = set(
    "a an the and or to of in on with at for is are was were be been it this that they we you i my your our as from by so but just really very have has had do did not one can will would about there then".split()
)
FILLERS = {"um", "uh", "erm", "hmm", "okay", "yeah", "আচ্ছা", "মানে", "मतलब"}
CUES = {
    "question": (
        "why",
        "how",
        "what if",
        "did you know",
        "কেন",
        "কীভাবে",
        "কিভাবে",
        "কেন",
        "कैसे",
        "क्यों",
        "por qué",
        "cómo",
    ),
    "contrast": (
        "mistake",
        "wrong",
        "instead",
        "actually",
        "nobody",
        "never",
        "stop",
        "but",
        "ভুল",
        "অথচ",
        "কিন্তু",
        "আসলে",
        "गलती",
        "लेकिन",
        "error",
        "pero",
    ),
    "stakes": (
        "lost",
        "risk",
        "failed",
        "failure",
        "waste",
        "afraid",
        "danger",
        "cost",
        "saved",
        "হার",
        "ঝুঁকি",
        "ভয়",
        "ব্যর্থ",
        "बर्बाद",
        "डर",
        "perdí",
        "riesgo",
    ),
    "explanation": (
        "because",
        "reason",
        "means",
        "therefore",
        "that's why",
        "কারণ",
        "তাই",
        "অর্থ",
        "क्योंकि",
        "इसलिए",
        "porque",
        "significa",
    ),
    "example": (
        "for example",
        "for instance",
        "imagine",
        "when i",
        "i used",
        "i tried",
        "উদাহরণ",
        "ধরুন",
        "যখন আমি",
        "যেমন",
        "उदाहरण",
        "por ejemplo",
        "cuando",
    ),
    "action": (
        "try",
        "test",
        "choose",
        "start",
        "write",
        "ask",
        "change",
        "replace",
        "step",
        "প্রথমে",
        "করুন",
        "বেছে",
        "লিখুন",
        "বদলে",
        "करे",
        "करें",
        "पहले",
        "prueba",
        "cambia",
    ),
    "payoff": (
        "result",
        "finally",
        "learned",
        "realized",
        "solved",
        "works",
        "improved",
        "won",
        "saved",
        "now",
        "turned out",
        "lesson",
        "ফলে",
        "শিখ",
        "বুঝ",
        "সমাধান",
        "এখন",
        "শেষে",
        "सीखा",
        "नतीजा",
        "आखिर",
        "resultado",
        "aprendí",
    ),
    "emotion": (
        "love",
        "hate",
        "fear",
        "afraid",
        "laugh",
        "cried",
        "shocked",
        "surprised",
        "angry",
        "couldn't believe",
        "ভালোবাস",
        "ভয়",
        "হাস",
        "অবাক",
        "কাঁদ",
        "हंसी",
        "डर",
        "lloré",
        "sorpresa",
    ),
    "promo": (
        "sponsor",
        "promo code",
        "discount code",
        "subscribe to",
        "like and subscribe",
        "link in the description",
        "thanks for watching",
        "welcome back to",
        "স্পনসর",
        "সাবস্ক্রাইব",
        "প্রোমো",
        "suscríbete",
        "patrocinador",
    ),
    "open_loop": (
        "i'll tell you later",
        "we'll get to",
        "in the next video",
        "more on that later",
        "let me explain why",
        "here's why",
        "দেখাব পরের",
        "পরে বলব",
        "পরের ভিডিও",
    ),
}


def word_list(text: str) -> list[str]:
    # Keep combining marks with their letters (important for Bengali/Hindi).
    words: list[str] = []
    current: list[str] = []
    for char in text.casefold():
        if unicodedata.category(char)[0] in {"L", "M", "N"} or (char in "'’" and current):
            current.append(char)
        elif current:
            words.append("".join(current).strip("'’"))
            current = []
    if current:
        words.append("".join(current).strip("'’"))
    return [word for word in words if word]


def tokens(text: str) -> set[str]:
    return set(word_list(text))


def cue(text: str, kind: str) -> bool:
    # Latin single-word cues match full words, not incidental substrings.
    for term in CUES[kind]:
        if term.isascii() and " " not in term:
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text):
                return True
        elif term in text:
            return True
    return False


def content_profile(text: str, content_type: str = "Auto") -> str:
    if content_type in {"Tutorial", "Webinar", "Presentation"}:
        return "educational"
    if content_type == "Gaming":
        return "entertainment"
    if cue(text, "example") and (cue(text, "stakes") or cue(text, "emotion")):
        return "story"
    if cue(text, "action") and cue(text, "explanation"):
        return "educational"
    if cue(text, "emotion"):
        return "entertainment"
    return "conversation" if content_type in {"Podcast", "Interview", "Talking Head"} else "general"


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class HeuristicHighlightRanker:
    """Local editorial features; scores compare clips, not view probabilities."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or worker_settings().highlight_weights

    def score_candidates(
        self,
        candidates: list[Candidate],
        keywords: list[str],
        *,
        content_type: str = "Auto",
        language: str = "auto",
    ) -> list[Candidate]:
        result = []
        for candidate in candidates:
            text = candidate.text.casefold().strip()
            words = word_list(text)
            opening = " ".join(words[:20])
            # Preserve question marks from the opening utterance.
            first_sentence = re.split(r"[.!。！।]", text, maxsplit=1)[0][:180]
            question = "?" in first_sentence or "？" in first_sentence or cue(opening, "question")
            contrast, stakes = cue(opening, "contrast"), cue(opening, "stakes")
            explanation, example = cue(text, "explanation"), cue(text, "example")
            action, payoff, emotion = cue(text, "action"), cue(text, "payoff"), cue(text, "emotion")
            promo = cue(text, "promo")
            count = len(words)
            filler_ratio = sum(w in FILLERS for w in words) / max(1, count)
            trigrams = list(zip(words, words[1:], words[2:], strict=False))
            repetition = 1 - len(set(trigrams)) / max(1, len(trigrams)) if trigrams else 0
            content_words = [w for w in words if w not in STOPWORDS and w not in FILLERS]
            lexical_spam = 1 - len(set(content_words)) / max(1, len(content_words))
            repetition = max(repetition, max(0, lexical_spam - 0.35))
            complete = finished(candidate.text)
            start_quality = (
                candidate.start_boundary_quality
                if candidate.start_boundary_quality is not None
                else 0.9
            )
            end_quality = (
                candidate.end_boundary_quality
                if candidate.end_boundary_quality is not None
                else (1 if complete else 0.4)
            )
            # Pronouns are allowed in standalone declarations ('This is a...').
            dependent = bool(
                re.match(
                    r"^(?:and then|which is|that's why|as i said|like i said|because of that|he did|she did|they did|it was)\b",
                    text,
                )
            )
            dangling_end = bool(
                words
                and words[-1]
                in {"because", "and", "but", "if", "when", "the", "to", "কারণ", "কিন্তু", "যদি"}
            )
            sentence_parts = [s.strip() for s in re.split(r"[.!?。！？।]+", text) if s.strip()]
            open_loop = cue(sentence_parts[-1] if sentence_parts else text, "open_loop")
            if unresolved_ending(candidate.text):
                open_loop = True
            needs_answer = question and len(sentence_parts) < 2 and not (explanation or payoff)
            specific = bool(re.search(r"\d", text)) or example
            profile = content_profile(text, content_type)
            keyword_match = any(k.strip().casefold() in text for k in keywords if k.strip())
            signal_count = sum((explanation, example, action, payoff, emotion, specific))
            hook = (
                0.18
                + 0.26 * question
                + 0.24 * contrast
                + 0.2 * stakes
                + 0.12 * (emotion or specific)
            )
            # A lesson may start calmly; useful concrete advice still has a hook.
            if action and specific:
                hook = max(hook, 0.58)
            insight = (
                0.12
                + 0.2 * explanation
                + 0.18 * example
                + 0.18 * action
                + 0.22 * payoff
                + 0.08 * specific
                + 0.04 * keyword_match
            )
            if profile in {"story", "entertainment"}:
                insight = max(insight, 0.16 + 0.24 * emotion + 0.24 * stakes + 0.24 * payoff)
            closure = (
                0.4
                + 0.3 * complete
                + 0.15 * (explanation or payoff)
                + 0.1 * (len(sentence_parts) > 1)
            )
            closure -= 0.3 * dependent + 0.35 * (open_loop or needs_answer) + 0.35 * dangling_end
            closure *= 0.6 + 0.4 * min(start_quality, end_quality)
            density = count / max(1, candidate.end - candidate.start)
            # Pace has a useful band. Racing/adding words never increases it forever.
            pace = min(1, density / 1.5) if density <= 3.5 else max(0.35, 1 - (density - 3.5) / 4)
            speech = (
                candidate.speech_ratio
                if candidate.speech_ratio is not None
                else min(1, density / 1.7)
            )
            quality = clamp(1 - filler_ratio * 2.5 - repetition * 1.2)
            if candidate.transcript_confidence is not None:
                quality *= 0.5 + 0.5 * candidate.transcript_confidence
            if promo:
                quality *= 0.48
            if count < 5 or not content_words:
                quality *= 0.25
            if dangling_end:
                quality *= 0.65
            if open_loop or needs_answer:
                quality *= 0.65
            if min(start_quality, end_quality) < 0.35:
                quality *= 0.75
            features = {
                "hook": clamp(hook) * quality,
                "completeness": clamp(closure) * quality,
                "insight": clamp(insight) * quality,
                "emphasis": clamp(0.35 * pace + 0.35 * speech + 0.3 * candidate.audio_emphasis)
                * quality,
                # Face detection is framing information, never a value judgement.
                "visual": clamp(0.6 + 0.4 * candidate.visual_stability) * quality,
                "novelty": clamp(
                    0.25
                    + 0.4 * (len(set(content_words)) / max(1, len(content_words)))
                    + 0.2 * specific
                    + 0.15 * (signal_count >= 3)
                )
                * quality,
                "boundaries": clamp((start_quality + end_quality) / 2 - 0.3 * dangling_end)
                * quality,
            }
            breakdown = {k: round(features[k] * self.weights[k], 2) for k in self.weights}
            evidence = []
            if question:
                evidence.append("opening question")
            if contrast or stakes:
                evidence.append("contrast or stakes")
            if explanation or action:
                evidence.append("explanation or practical action")
            if example:
                evidence.append("concrete example")
            if payoff:
                evidence.append("outcome cues")
            risks = []
            if dependent:
                risks.append("opening needs earlier context")
            if open_loop or needs_answer or dangling_end:
                risks.append("unresolved ending")
            if min(start_quality, end_quality) < 0.6:
                risks.append("uncertain sentence boundary")
            if promo:
                risks.append("promotion or housekeeping")
            if repetition > 0.2 or filler_ratio > 0.12:
                risks.append("repetition or fillers")
            if (
                candidate.transcript_confidence is not None
                and candidate.transcript_confidence < 0.6
            ):
                risks.append("uncertain transcription")
            reason = (
                f"Local {profile} review: {', '.join(evidence) or 'limited editorial signals'}. "
            )
            reason += (
                ("Watch for " + "; ".join(risks) + ". ") if risks else "Clean setup/end cues. "
            )
            reason += "Editorial score, not predicted views."
            result.append(
                candidate.model_copy(
                    update={
                        "score": round(sum(breakdown.values()), 2),
                        "breakdown": breakdown,
                        "features": features,
                        "content_profile": profile,
                        "reason": reason,
                        "title": " ".join(candidate.text.split()[:10]).strip(" ,;:")[:100],
                    }
                )
            )
        return result

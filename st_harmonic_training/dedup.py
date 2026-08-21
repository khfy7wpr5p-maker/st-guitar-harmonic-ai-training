from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
import unicodedata

from .identity import WorkIdentity

SPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


def normalize_metadata_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    text = NON_WORD_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def metadata_fingerprint(composer: str, title: str, catalog: str = "") -> str:
    canonical = "|".join(
        normalize_metadata_text(part) for part in (composer, title, catalog)
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def symbolic_fingerprint(tokens: tuple[str, ...] | list[str]) -> str:
    canonical = "\x1f".join(unicodedata.normalize("NFKC", token).strip() for token in tokens)
    return sha256(canonical.encode("utf-8")).hexdigest()


def transposition_invariant_pitch_tokens(pitches: tuple[int, ...] | list[int]) -> tuple[str, ...]:
    if not pitches:
        return ()
    return tuple(str((b - a) % 12) for a, b in zip(pitches, pitches[1:]))


def _shingles(tokens: tuple[str, ...], width: int = 3) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens} if tokens else set()
    return {tokens[index:index + width] for index in range(len(tokens) - width + 1)}


def symbolic_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a = _shingles(left)
    b = _shingles(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class DedupRecord:
    identity: WorkIdentity
    composer: str
    title: str
    catalog: str
    symbolic_tokens: tuple[str, ...]

    @property
    def metadata_hash(self) -> str:
        return metadata_fingerprint(self.composer, self.title, self.catalog)

    @property
    def symbolic_hash(self) -> str:
        return symbolic_fingerprint(self.symbolic_tokens)


@dataclass(frozen=True)
class DuplicateEvidence:
    left_record_id: str
    right_record_id: str
    exact_symbolic_match: bool
    metadata_match: bool
    symbolic_similarity: float
    cross_corpus: bool


def detect_duplicate_pairs(
    records: list[DedupRecord], *, near_threshold: float = 0.90
) -> list[DuplicateEvidence]:
    if not 0.0 <= near_threshold <= 1.0:
        raise ValueError("near_threshold must be between 0 and 1")
    found: list[DuplicateEvidence] = []
    ordered = sorted(records, key=lambda item: item.identity.record_id)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            exact = left.symbolic_hash == right.symbolic_hash
            meta = left.metadata_hash == right.metadata_hash
            similarity = symbolic_similarity(left.symbolic_tokens, right.symbolic_tokens)
            if exact or (meta and similarity >= near_threshold):
                found.append(
                    DuplicateEvidence(
                        left.identity.record_id,
                        right.identity.record_id,
                        exact,
                        meta,
                        similarity,
                        left.identity.source_corpus != right.identity.source_corpus,
                    )
                )
    return found

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata
from typing import Mapping

from .contracts import ContractError

NORMALIZATION_VERSION = "st-harmony-normalization-v1"
SPACE_RE = re.compile(r"\s+")
NORMALIZED_FIELDS = (
    "key",
    "local_key",
    "roman_numeral",
    "bass",
    "inversion",
    "chord_family",
    "extension",
    "suspension",
    "alteration",
    "phrase",
    "cadence",
)


def normalize_component(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractError("normalized label components must be strings or null")
    normalized = SPACE_RE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    return normalized or None


@dataclass(frozen=True)
class NormalizedSTLabel:
    key: str | None = None
    local_key: str | None = None
    roman_numeral: str | None = None
    bass: str | None = None
    inversion: str | None = None
    chord_family: str | None = None
    extension: str | None = None
    suspension: str | None = None
    alteration: str | None = None
    phrase: str | None = None
    cadence: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizationRecord:
    raw_source_label: str
    normalized_st_label: NormalizedSTLabel
    normalization_version: str = NORMALIZATION_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.raw_source_label, str):
            raise ContractError("raw_source_label must be a string")
        if self.normalization_version != NORMALIZATION_VERSION:
            raise ContractError(
                f"unsupported normalization_version: {self.normalization_version}"
            )


def build_normalization_record(
    raw_source_label: str,
    deterministic_mapping: Mapping[str, str | None],
    *,
    normalization_version: str = NORMALIZATION_VERSION,
) -> NormalizationRecord:
    """Build a versioned normalized record without inferring musical meaning.

    Corpus adapters must supply semantic fields using their own reviewed,
    deterministic mapping rules. This function canonicalizes representation only.
    The raw source label is preserved byte-for-byte as the authoritative source
    evidence string supplied by the caller.
    """
    unknown = sorted(set(deterministic_mapping) - set(NORMALIZED_FIELDS))
    if unknown:
        raise ContractError("unknown normalized fields: " + ", ".join(unknown))
    values = {
        field: normalize_component(deterministic_mapping.get(field))
        for field in NORMALIZED_FIELDS
    }
    return NormalizationRecord(
        raw_source_label=raw_source_label,
        normalized_st_label=NormalizedSTLabel(**values),
        normalization_version=normalization_version,
    )

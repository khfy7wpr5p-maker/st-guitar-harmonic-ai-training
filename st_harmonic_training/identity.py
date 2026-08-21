from __future__ import annotations

from dataclasses import dataclass

from .contracts import ContractError


@dataclass(frozen=True)
class WorkIdentity:
    record_id: str
    source_corpus: str
    source_record_id: str
    canonical_work_id: str
    edition_id: str
    duplicate_cluster_id: str
    derivation_parent_id: str | None
    split_group_id: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "source_corpus",
            "source_record_id",
            "canonical_work_id",
            "edition_id",
            "duplicate_cluster_id",
            "split_group_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"{name} must be a non-empty string")
        if self.derivation_parent_id is not None:
            if not isinstance(self.derivation_parent_id, str) or not self.derivation_parent_id.strip():
                raise ContractError("derivation_parent_id must be null or non-empty string")
        if self.derivation_parent_id == self.record_id:
            raise ContractError("record cannot derive from itself")

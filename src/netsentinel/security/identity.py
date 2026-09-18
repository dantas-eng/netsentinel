"""Contrato de identidade: mitigação só pelo MAC pré-aprovado."""
from typing import Protocol


class SecurityIdentity(Protocol):
    attacker_mac: str

    def trusted_bindings(self) -> dict[str, str]: ...

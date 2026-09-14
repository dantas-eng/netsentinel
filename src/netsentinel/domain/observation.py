"""Contrato de captura: dados observados, nunca veredictos de segurança."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Observation:
    timestamp: float  # Epoch do pacote; não governa a expiração da janela.
    src_mac: str
    dst_mac: str
    size_bytes: int  # Bytes capturados; não inclui overhead físico da rede.
    protocol: str
    src_ip: str | None = None
    dst_ip: str | None = None
    arp_operation: int | None = None
    arp_sender_mac: str | None = None
    arp_sender_ip: str | None = None

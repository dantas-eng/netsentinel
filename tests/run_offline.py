"""Executa testes sem descoberta de interfaces/rotas do host.

Somente o inventário de rede do Scapy é substituído. Dissecção, serialização,
leitura PCAP e agregação continuam reais. Não valida sockets de captura reais.
"""
import unittest
from unittest.mock import patch
from scapy.config import conf

conf.route_autoload = False
conf.route6_autoload = False
with patch('scapy.interfaces.NetworkInterfaceDict.reload'):
    suite = unittest.defaultTestLoader.discover('tests', pattern='test_*.py', top_level_dir='.')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())

"""Mitigação verificável e restauração conservadora, com journal persistente.

O processo deve manter o lock de arquivo durante toda a execução. O RLock
serializa operações HTTP no mesmo processo; o journal sobrevive a reinícios.
"""
import json
import os
from pathlib import Path
from threading import RLock
from time import time
from uuid import uuid4
from netsentinel.security.agent.firewall import TABLE, block, ruleset
from netsentinel.security.system import SystemFailure, preflight


class VictimController:
    def __init__(self, config, system):
        self.config, self.system = config, system
        self.path = Path(config.state_dir) / 'journal.json'
        self.lock = RLock()

    def _save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w') as handle:
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)
        fd = os.open(str(self.path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _journal(self):
        state = json.loads(self.path.read_text())
        if state['fingerprint'] != self.config.fingerprint():
            raise SystemFailure('Configuração alterada: use a configuração original para restaurar.')
        return state

    def _table(self):
        tables = self.system.json(['nft', '-j', 'list', 'tables'])['nftables']
        exists = any(item.get('table', {}).get('name') == TABLE and
                     item['table'].get('family') == 'netdev' for item in tables)
        return self.system.json(['nft', '-j', 'list', 'table', 'netdev', TABLE]) if exists else None

    def _owned(self, state, table):
        if table is None or not any(item.get('table', {}).get('name') == TABLE and
                                    item['table'].get('comment') == state['marker']
                                    for item in table['nftables']):
            raise SystemFailure('Tabela ausente ou sem identificação de propriedade esperada.')

    def _neighbor(self):
        values = self.system.json(['ip', '-j', 'neigh', 'show', 'to',
                                  self.config.gateway_ip, 'dev', self.config.interface])
        return values[0] if values else None

    def _static_correct(self, neighbor):
        return bool(neighbor and neighbor.get('lladdr', '').lower() == self.config.gateway_mac
                    and 'PERMANENT' in neighbor.get('state', []))

    def prepare(self):
        with self.lock:
            preflight(self.config, 'victim', self.system)
            table = self._table()
            if self.path.exists():
                state = self._journal()
                if table is not None:
                    self._owned(state, table)
                    return self.status()
                # Recriar tabela reinicia contadores: gerar nova identidade de medição.
                state['marker'] = 'netsentinel-' + uuid4().hex
                self._save(state)
            else:
                if table is not None:
                    raise SystemFailure('Colisão de tabela: não sobrescrever recursos existentes.')
                neighbor = self._neighbor()
                if neighbor and neighbor.get('lladdr') and neighbor['lladdr'].lower() != self.config.gateway_mac:
                    raise SystemFailure('Prepare o agente antes do envenenamento; ARP inicial divergente.')
                state = dict(fingerprint=self.config.fingerprint(),
                             marker='netsentinel-' + uuid4().hex,
                             previous_static=self._static_correct(neighbor),
                             arp_attempted=False)
                self._save(state)
            self.system.run(['nft', '-f', '-'], ruleset(
                self.config.interface, self.config.attacker_mac,
                self.config.sensor_internal_ip, self.config.agent_port, state['marker']))
            return self.status()

    def status(self):
        with self.lock:
            state, table = self._journal(), self._table()
            self._owned(state, table)
            counters, blocked = {}, False
            for item in table['nftables']:
                if 'counter' in item:
                    counter = item['counter']
                    counters[counter['name']] = dict(packets=counter['packets'], bytes=counter['bytes'])
                if item.get('set', {}).get('name') == 'blocked':
                    blocked = self.config.attacker_mac in item['set'].get('elem', [])
            if not all(name in counters for name in ('seen', 'dropped', 'passed')):
                raise SystemFailure('Contadores de evidência ausentes.')
            neighbor = self._neighbor()
            static = self._static_correct(neighbor)
            return dict(timestamp=time(), run_id=state['marker'], blocked=blocked,
                        arp_static_correct=static, mitigated=blocked and static,
                        attacker_mac=self.config.attacker_mac, gateway_ip=self.config.gateway_ip,
                        neighbor=neighbor, counters=counters)

    def apply(self, attacker_mac):
        # Validar antes de executar qualquer comando, inclusive consultas.
        mac = self.config.require_attacker(attacker_mac)
        with self.lock:
            preflight(self.config, 'victim', self.system)
            state = self._journal()
            self._owned(state, self._table())
            self.system.run(['nft', '-f', '-'], block(mac))
            # Journal antecede mutação: uma queda entre ip e _save não perde autoria.
            state['arp_attempted'] = True
            self._save(state)
            self.system.run(['ip', 'neigh', 'replace', self.config.gateway_ip,
                             'lladdr', self.config.gateway_mac, 'nud', 'permanent',
                             'dev', self.config.interface])
            result = self.status()
            if not result['mitigated']:
                raise SystemFailure('As duas camadas da mitigação não foram confirmadas.')
            return result

    def restore(self):
        with self.lock:
            if not self.path.exists():
                if self._table() is not None:
                    raise SystemFailure('Sem journal: não remover tabela cuja propriedade é desconhecida.')
                return dict(restored=True, already_clean=True)
            state, table = self._journal(), self._table()
            if table is not None:
                self._owned(state, table)
            neighbor = self._neighbor()
            if state['arp_attempted'] and not state['previous_static']:
                if self._static_correct(neighbor):
                    self.system.run(['ip', 'neigh', 'del', self.config.gateway_ip,
                                     'dev', self.config.interface])
                elif neighbor and 'PERMANENT' in neighbor.get('state', []):
                    raise SystemFailure('Entrada estática alterada externamente; restauração interrompida.')
                # Entrada dinâmica não é reproduzida: será reaprendida após parar o ataque.
            if table is not None:
                self.system.run(['nft', 'delete', 'table', 'netdev', TABLE])
            self.path.unlink()
            return dict(restored=True, already_clean=False)

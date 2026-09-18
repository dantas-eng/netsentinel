"""Kernel substituto para testes de contrato; NÃO comprova filtragem Linux real."""
import copy
from netsentinel.security.config import LabConfig
from netsentinel.security.system import SystemFailure


def config(directory, **updates):
    values = dict(interface='enp0s3', internal_cidr='10.77.0.0/24',
                  victim_ip='10.77.0.20', victim_mac='02:00:00:00:00:20',
                  gateway_ip='10.77.0.1', gateway_mac='02:00:00:00:00:10',
                  attacker_ip='10.77.0.30', attacker_mac='02:00:00:00:00:30',
                  sensor_internal_ip='10.77.0.40', sensor_internal_mac='02:00:00:00:00:40',
                  agent_port=8787, token_file=directory + '/token', state_dir=directory,
                  isolated_lab=True)
    values.update(updates)
    return LabConfig(**values)


class FakeLinux:
    def __init__(self, config, role='victim'):
        self.config = config
        prefix = 'sensor_internal' if role == 'sensor' else role
        self.addresses = [dict(ifname=config.interface, address=getattr(config, prefix + '_mac'),
                               addr_info=[dict(family='inet', local=getattr(config, prefix + '_ip'))])]
        if role == 'sensor' and config.hostonly_interface:
            self.addresses.append(dict(ifname=config.hostonly_interface, address='02:00:00:00:01:40',
                                       addr_info=[dict(family='inet', local=config.hostonly_ip)]))
        self.routes = []
        self.forwarding = '0'
        self.table = None
        self.neighbor = None
        self.blocked = False
        self.counters = {key: dict(packets=0, bytes=0) for key in ('seen', 'dropped', 'passed')}
        self.commands = []
        self.fail_replace = False

    def sysctl(self, path):
        return self.forwarding

    def json(self, argv):
        self.commands.append((argv, None))
        if argv == ['ip', '-j', 'address', 'show']:
            return copy.deepcopy(self.addresses)
        if 'route' in argv:
            return copy.deepcopy(self.routes)
        if 'neigh' in argv:
            return [copy.deepcopy(self.neighbor)] if self.neighbor else []
        if argv == ['nft', '-j', 'list', 'tables']:
            return {'nftables': [{'table': {'family': 'netdev', 'name': 'netsentinel_lab'}}]
                    if self.table else []}
        if argv == ['nft', '-j', 'list', 'table', 'netdev', 'netsentinel_lab']:
            return {'nftables': [dict(table=dict(name='netsentinel_lab', comment=self.table)),
                    dict(set=dict(name='blocked', elem=[self.config.attacker_mac] if self.blocked else []))] +
                    [dict(counter=dict(name=name, **copy.deepcopy(value)))
                     for name, value in self.counters.items()]}
        raise AssertionError(argv)

    def run(self, argv, stdin=None):
        self.commands.append((argv, stdin))
        if argv == ['nft', '-f', '-']:
            if stdin.startswith('create table'):
                if self.table:
                    raise SystemFailure('exists')
                self.table = stdin.split('comment "')[1].split('"')[0]
            elif stdin.startswith('flush set'):
                self.blocked = True
            else:
                raise AssertionError(stdin)
        elif argv[:3] == ['ip', 'neigh', 'replace']:
            if self.fail_replace:
                raise SystemFailure('injected failure')
            self.neighbor = dict(dst=self.config.gateway_ip, lladdr=self.config.gateway_mac,
                                 state=['PERMANENT'])
        elif argv[:3] == ['ip', 'neigh', 'del']:
            self.neighbor = None
        elif argv == ['nft', 'delete', 'table', 'netdev', 'netsentinel_lab']:
            self.table = None
            self.blocked = False
        else:
            raise AssertionError(argv)
        return ''

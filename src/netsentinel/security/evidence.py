"""Evidência no intervalo posterior à mitigação, sem confundir contadores totais."""


def verify_interval(before, after):
    if before['run_id'] != after['run_id']:
        return dict(verified=False, reason='agent_run_changed')
    if before['attacker_mac'] != after['attacker_mac']:
        return dict(verified=False, reason='target_changed')
    if after['timestamp'] <= before['timestamp']:
        return dict(verified=False, reason='invalid_interval')
    deltas = {name: after['counters'][name]['packets'] - before['counters'][name]['packets']
              for name in ('seen', 'dropped', 'passed')}
    if any(value < 0 for value in deltas.values()):
        return dict(verified=False, reason='counter_reset', deltas=deltas)
    if not all(s['mitigated'] and s['arp_static_correct'] and s['blocked'] for s in (before, after)):
        return dict(verified=False, reason='mitigation_not_confirmed', deltas=deltas)
    # Tráfego ativo é necessário: zero recebido/zero entregue não prova bloqueio.
    valid = deltas['seen'] > 0 and deltas['dropped'] > 0 and deltas['passed'] == 0
    return dict(verified=valid, reason=None if valid else 'missing_drops_or_traffic_passed',
                deltas=deltas, scope='post_filter_attacker_mac',
                ping_verified=False)  # Ping é evidência independente do ensaio.

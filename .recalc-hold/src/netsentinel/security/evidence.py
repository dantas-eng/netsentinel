"""Evidência no intervalo posterior à mitigação, sem confundir contadores totais."""

from __future__ import annotations

import math


def _packets(reading, name):
    counters = reading.get('counters')
    if not isinstance(counters, dict):
        return None
    counter = counters.get(name)
    if not isinstance(counter, dict):
        return None
    value = counter.get('packets')
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _reject(reason, **extra):
    return dict(verified=False, reason=reason, reason_code=reason, **extra)


def verify_interval(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict):
        return _reject('readings_unavailable')
    if before.get('run_id') != after.get('run_id'):
        return _reject('agent_run_changed')
    if before.get('attacker_mac') != after.get('attacker_mac'):
        return _reject('target_changed')
    if bool(before.get('simulated')) != bool(after.get('simulated')):
        return _reject('environment_changed')
    try:
        if after['timestamp'] <= before['timestamp']:
            return _reject('invalid_interval')
    except (KeyError, TypeError):
        return _reject('invalid_interval')
    packets = {}
    for name in ('seen', 'dropped', 'passed'):
        before_n = _packets(before, name)
        after_n = _packets(after, name)
        if before_n is None or after_n is None:
            return _reject('counter_unavailable')
        packets[name] = (before_n, after_n)
    deltas = {name: after_n - before_n for name, (before_n, after_n) in packets.items()}
    if any(value < 0 for value in deltas.values()):
        return _reject('counter_reset', deltas=deltas)
    if not all(s.get('mitigated') and s.get('arp_static_correct') and s.get('blocked')
               for s in (before, after)):
        return _reject('mitigation_not_confirmed', deltas=deltas)
    # Tráfego ativo é necessário: zero recebido/zero entregue não prova bloqueio.
    valid = deltas['seen'] > 0 and deltas['dropped'] > 0 and deltas['passed'] == 0
    reason = None if valid else 'missing_drops_or_traffic_passed'
    return dict(verified=valid, reason=reason, reason_code=reason, deltas=deltas,
                scope='post_filter_attacker_mac',
                ping_verified=False)  # Ping é evidência independente do ensaio.

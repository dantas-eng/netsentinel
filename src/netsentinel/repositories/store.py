"""Repository: acesso SQL e transações ficam nesta camada, não nas rotas."""
from math import isfinite
from statistics import median
from time import time
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from netsentinel.analysis.contracts import Reputation
from netsentinel.security.config import validate_mac
from netsentinel.repositories.models import Device, Audit, Calibration, Baseline, StoredEvent, LatestSnapshot


class DomainConflict(ValueError):
    pass


def audit(session, mac, action, actor, reason):
    session.add(Audit(mac=mac, action=action, actor=actor, reason=reason, timestamp=time()))


def device_data(device, baseline=None):
    return dict(mac=device.mac, reputation=device.reputation, first_seen=device.first_seen,
                last_seen=device.last_seen, risk=device.risk,
                baseline_bps=baseline.bytes_per_second if baseline and device.reputation == 'known' else None)


class Repository:
    def __init__(self, database):
        self.db = database

    def get_reputation(self, mac):
        try:
            with self.db.transaction() as session:
                device = session.get(Device, mac)
                return Reputation(device.reputation) if device else Reputation.NEW
        except SQLAlchemyError:
            return Reputation.UNKNOWN

    def get_baseline_bps(self, mac):
        try:
            with self.db.transaction() as session:
                device, baseline = session.get(Device, mac), session.get(Baseline, mac)
                if not device or device.reputation != 'known' or not baseline:
                    return None
                return baseline.bytes_per_second
        except SQLAlchemyError:
            return None

    def save_snapshot(self, snapshot):
        with self.db.transaction() as session:
            for raw_mac in snapshot['devices']:
                mac = validate_mac(raw_mac)
                device = session.get(Device, mac)
                if not device:
                    device = Device(mac=mac, reputation='new', first_seen=snapshot['timestamp'])
                    session.add(device)
                if device.first_seen is None:
                    device.first_seen = snapshot['timestamp']
                device.last_seen = snapshot['timestamp']
            row = session.get(LatestSnapshot, 1)
            if row:
                row.payload = snapshot
            else:
                session.add(LatestSnapshot(id=1, payload=snapshot))

    def latest_snapshot(self):
        with self.db.transaction() as session:
            row = session.get(LatestSnapshot, 1)
            return row.payload if row else None

    def devices(self):
        with self.db.transaction() as session:
            rows = session.execute(select(Device, Baseline).outerjoin(Baseline).order_by(Device.mac))
            return [device_data(device, baseline) for device, baseline in rows]

    def change_reputation(self, mac, known, actor, reason):
        mac = validate_mac(mac)
        if not reason.strip() or len(reason) > 500:
            raise ValueError('Informe motivo entre 1 e 500 caracteres.')
        with self.db.transaction() as session:
            device = session.get(Device, mac)
            if not device:
                raise DomainConflict('Dispositivo ainda não observado.')
            desired = 'known' if known else 'new'
            if device.reputation != desired:
                device.reputation = desired
                audit(session, mac, 'confirm' if known else 'revoke', actor, reason)
                if not known:
                    for calibration in session.scalars(select(Calibration).where(
                            Calibration.mac == mac, Calibration.status == 'collecting')):
                        calibration.status = 'cancelled'
                        calibration.completed_at = time()
            return device_data(device, session.get(Baseline, mac))

    def bootstrap(self, macs, actor):
        with self.db.transaction() as session:
            for value in macs:
                mac = validate_mac(value)
                device = session.get(Device, mac)
                # Inventário é importado uma única vez por MAC. Não desfazer revogação.
                if device is None:
                    session.add(Device(mac=mac, reputation='known'))
                    session.flush()
                    audit(session, mac, 'bootstrap', actor, 'Inventário confiável do laboratório')

    def audits(self, limit=100):
        with self.db.transaction() as session:
            return [dict(id=row.id, mac=row.mac, action=row.action, actor=row.actor,
                         reason=row.reason, timestamp=row.timestamp)
                    for row in session.scalars(select(Audit).order_by(Audit.id.desc()).limit(limit))]

    def start_calibration(self, mac, actor, run_id, anchor):
        mac = validate_mac(mac)
        with self.db.transaction() as session:
            device = session.get(Device, mac)
            if device is None or device.reputation != 'known':
                raise DomainConflict('Calibração exige dispositivo KNOWN.')
            if session.scalar(select(Calibration.id).where(
                    Calibration.mac == mac, Calibration.status == 'collecting')):
                raise DomainConflict('Já há uma calibração ativa.')
            row = Calibration(mac=mac, status='collecting', run_id=run_id, last_end=anchor,
                              samples=[], started_at=time())
            session.add(row)
            audit(session, mac, 'calibration_started', actor, 'Cinco janelas de 8 segundos')
            session.flush()
            return row.id

    def calibrations(self, mac):
        with self.db.transaction() as session:
            return [dict(id=row.id, mac=row.mac, status=row.status, samples=row.samples,
                         started_at=row.started_at, completed_at=row.completed_at)
                    for row in session.scalars(select(Calibration).where(Calibration.mac == mac)
                                              .order_by(Calibration.id.desc()))]

    def collect_calibration(self, snapshot):
        """Janela madura e íntegra, sem conflito em qualquer IP e sem sobreposição."""
        run_id = snapshot['capture_run_id']
        end, start = snapshot['window_end_monotonic'], snapshot['window_start_monotonic']
        claims = {}
        for item in snapshot['arp_claims']:
            claims.setdefault(item['ip'], set()).add(item['claimed_mac'])
        clean = (not snapshot['incomplete'] and not snapshot['warming_up'] and
                 snapshot['window_seconds'] == 8 and snapshot['observed_seconds'] == 8 and
                 isfinite(start) and isfinite(end) and abs(end - start - 8) < 1e-6 and
                 all(len(macs) <= 1 for macs in claims.values()))
        completed = []
        with self.db.transaction() as session:
            rows = session.scalars(select(Calibration).where(Calibration.status == 'collecting'))
            for row in rows:
                if row.run_id != run_id:
                    row.status = 'interrupted'
                    row.completed_at = time()
                    continue
                if not clean or start < row.last_end:
                    continue
                device = session.get(Device, row.mac)
                if device.reputation != 'known':
                    row.status = 'cancelled'
                    row.completed_at = time()
                    continue
                # Uma captura íntegra sem quadros dessa origem mede zero bytes.
                count = snapshot['devices'].get(row.mac, {}).get('bytes', 0)
                if not isinstance(count, (int, float)) or not isfinite(count) or count < 0:
                    continue
                # Unidade do contrato: BYTES POR SEGUNDO, não bytes da janela.
                sample = dict(start=start, end=end, bytes=count, bytes_per_second=count / 8.0)
                row.samples = [*row.samples, sample]
                row.last_end = end
                if len(row.samples) == 5:
                    value = median(item['bytes_per_second'] for item in row.samples)
                    baseline = session.get(Baseline, row.mac)
                    if baseline is None:
                        baseline = Baseline(mac=row.mac)
                        session.add(baseline)
                    baseline.bytes_per_second = value if value > 0 else None
                    baseline.calibration_id = row.id
                    baseline.calibrated_at = time()
                    row.status, row.completed_at = 'completed', time()
                    audit(session, row.mac, 'calibration_completed', 'system',
                          'Mediana em bytes/s persistida; zero indisponível')
                    completed.append(dict(mac=row.mac, baseline_bps=baseline.bytes_per_second))
        return completed

    def interrupt_calibrations(self):
        with self.db.transaction() as session:
            for row in session.scalars(select(Calibration).where(Calibration.status == 'collecting')):
                row.status, row.completed_at = 'interrupted', time()

    def append_event(self, payload):
        with self.db.transaction() as session:
            row = StoredEvent(name=payload['event'], timestamp=payload.get('timestamp', time()), payload=payload)
            session.add(row)
            if payload['event'] == 'risk_evaluated':
                for mac, result in payload.get('devices', {}).items():
                    device = session.get(Device, mac)
                    if device:
                        device.risk = result
            session.flush()
            return {**payload, 'event_id': row.id, 'timestamp': row.timestamp}

    def events(self, after_id=0, limit=100):
        with self.db.transaction() as session:
            rows = session.scalars(select(StoredEvent).where(StoredEvent.id > after_id)
                                   .order_by(StoredEvent.id).limit(limit))
            return [{**row.payload, 'event_id': row.id, 'timestamp': row.timestamp} for row in rows]

"""Repository: acesso SQL e transações ficam nesta camada, não nas rotas."""
from math import isfinite
from statistics import median
from time import time
from sqlalchemy import and_, delete, false, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from netsentinel.analysis.contracts import Reputation
from netsentinel.security.config import validate_mac
from netsentinel.repositories.models import (Device, Audit, Calibration, Baseline, StoredEvent, LatestSnapshot,
                                            ArpFrame)
from netsentinel.packets.dissect import dissect, verdict


class DomainConflict(ValueError):
    pass


# Unicast LAA (I/G bit clear, U/L set). Not 00:00:00:00:00:00, not multicast.
# Exists only so Audit.mac (NOT NULL FK) can record operator actions with no host.
SYSTEM_AUDIT_MAC = '02:00:00:00:00:00'


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
            rows = session.execute(
                select(Device, Baseline).outerjoin(Baseline)
                .where(Device.mac != SYSTEM_AUDIT_MAC).order_by(Device.mac))
            return [device_data(device, baseline) for device, baseline in rows]

    def change_reputation(self, mac, known, actor, reason):
        mac = validate_mac(mac)
        if mac == SYSTEM_AUDIT_MAC:
            raise DomainConflict('Dispositivo ainda não observado.')
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

    def risk_history(self, mac, limit=100):
        mac = validate_mac(mac)
        with self.db.transaction() as session:
            rows = session.scalars(select(StoredEvent).where(StoredEvent.name == 'risk_evaluated')
                                   .order_by(StoredEvent.id.desc()).limit(limit))
            points = []
            for row in rows:
                devices = row.payload.get('devices') if isinstance(row.payload, dict) else None
                if not isinstance(devices, dict):
                    continue
                item = devices.get(mac)
                if not isinstance(item, dict) or item.get('score') is None:
                    continue
                points.append(dict(event_id=row.id, timestamp=row.timestamp,
                                   score=item['score'], classification=item.get('classification')))
            return sorted(points, key=lambda item: item['event_id'])

    def prune_events(self, keep_days, actor, confirm=False):
        if type(keep_days) is not int or keep_days < 1:
            raise ValueError('keep_days deve ser inteiro >= 1.')
        if type(confirm) is not bool:
            raise ValueError('confirm deve ser bool.')
        cutoff = time() - keep_days * 86400
        with self.db.transaction() as session:
            matched = session.scalar(
                select(func.count()).select_from(StoredEvent).where(StoredEvent.timestamp < cutoff)
            ) or 0
            removed = 0
            if confirm:
                session.execute(delete(StoredEvent).where(StoredEvent.timestamp < cutoff))
                removed = matched
                mac = SYSTEM_AUDIT_MAC
                if session.get(Device, mac) is None:
                    session.add(Device(mac=mac, reputation='new'))
                    session.flush()
                audit(session, mac, 'events_pruned', actor,
                      f'{removed} eventos anteriores a {int(cutoff)} (keep_days={keep_days})')
            return dict(cutoff=cutoff, matched=matched, removed=removed)

    # ---- quadros ARP (ADR 0014) ----

    @staticmethod
    def _frame_item(row, trusted):
        packet = dissect(row.raw)
        return dict(id=row.id, captured_at=row.captured_at, eth_src=row.eth_src, eth_dst=row.eth_dst,
                    opcode=row.opcode, sender_mac=row.sender_mac, sender_ip=row.sender_ip,
                    target_mac=row.target_mac, target_ip=row.target_ip, length=packet['length'],
                    summary=packet['summary'], spoofed=verdict(packet, trusted or {})['spoofed'])

    def save_arp_frames(self, frames, capture_run_id, source, retention_days, max_rows, now=None):
        rows = []
        for frame in frames:
            packet = dissect(frame['raw'])
            rows.append(ArpFrame(captured_at=frame['timestamp'], capture_run_id=capture_run_id, source=source,
                                 eth_src=packet['eth_src'], eth_dst=packet['eth_dst'], opcode=packet['opcode'],
                                 sender_mac=packet['sender_mac'], sender_ip=packet['sender_ip'],
                                 target_mac=packet['target_mac'], target_ip=packet['target_ip'], raw=frame['raw']))
        with self.db.transaction() as session:
            session.add_all(rows)
            session.flush()
            self._prune_frames(session, retention_days, max_rows, now)
        return len(rows)

    def prune_arp_frames(self, retention_days, max_rows, now=None):
        with self.db.transaction() as session:
            return self._prune_frames(session, retention_days, max_rows, now)

    @staticmethod
    def _prune_frames(session, retention_days, max_rows, now):
        if type(retention_days) is not int or retention_days < 1 or type(max_rows) is not int or max_rows < 1:
            raise ValueError('Retenção de pacotes deve usar inteiros >= 1.')
        cutoff = (time() if now is None else now) - retention_days * 86400
        removed = session.execute(delete(ArpFrame).where(ArpFrame.captured_at < cutoff)).rowcount or 0
        floor = session.scalar(select(ArpFrame.id).order_by(ArpFrame.id.desc()).offset(max_rows - 1).limit(1))
        if floor is not None:
            removed += session.execute(delete(ArpFrame).where(ArpFrame.id < floor)).rowcount or 0
        return removed

    def arp_frames(self, after_id=0, limit=100, spoofed_only=False, query=None, trusted=None, latest=False):
        if type(limit) is not int or not 1 <= limit <= 500 or type(after_id) is not int or after_id < 0:
            raise ValueError('Paginação inválida.')
        statement = select(ArpFrame).where(ArpFrame.id > after_id)
        if spoofed_only:
            pairs = [and_(ArpFrame.sender_ip == ip, ArpFrame.sender_mac != mac.lower())
                     for ip, mac in (trusted or {}).items()]
            statement = statement.where(or_(*pairs) if pairs else false())
        if query:
            columns = (ArpFrame.eth_src, ArpFrame.eth_dst, ArpFrame.sender_mac, ArpFrame.sender_ip,
                       ArpFrame.target_mac, ArpFrame.target_ip)
            statement = statement.where(or_(*(c.contains(query.lower(), autoescape=True) for c in columns)))
        with self.db.transaction() as session:
            # latest: as N mais novas (abertura do dashboard), devolvidas na mesma ordem crescente.
            order = ArpFrame.id.desc() if latest else ArpFrame.id
            rows = list(session.scalars(statement.order_by(order).limit(limit)))
            return [self._frame_item(row, trusted) for row in (rows[::-1] if latest else rows)]

    def _frame_detail(self, row, trusted):
        if row is None:
            return None
        packet = dissect(row.raw)
        return {**self._frame_item(row, trusted), 'raw_hex': row.raw.hex(), 'layers': packet['layers'],
                'verdict': verdict(packet, trusted or {})}

    def arp_frame(self, frame_id, trusted):
        with self.db.transaction() as session:
            return self._frame_detail(session.get(ArpFrame, frame_id), trusted)

    def match_arp_frame(self, mac, ip, before, trusted):
        with self.db.transaction() as session:
            row = session.scalar(select(ArpFrame).where(
                ArpFrame.eth_src == mac.lower(), ArpFrame.sender_ip == ip, ArpFrame.captured_at <= before)
                .order_by(ArpFrame.captured_at.desc(), ArpFrame.id.desc()).limit(1))
            return self._frame_detail(row, trusted)

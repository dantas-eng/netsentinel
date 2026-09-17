"""Reputação, auditoria, baseline, calibrações e eventos."""
from alembic import op
import sqlalchemy as sa

revision = '0001_backend'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('devices',
        sa.Column('mac', sa.String(17), primary_key=True),
        sa.Column('reputation', sa.String(16), nullable=False),
        sa.Column('first_seen', sa.Float()), sa.Column('last_seen', sa.Float()),
        sa.Column('risk', sa.JSON()))
    op.create_table('audit',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('mac', sa.String(17), sa.ForeignKey('devices.mac'), nullable=False),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('actor', sa.String(120), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False))
    op.create_table('calibrations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('mac', sa.String(17), sa.ForeignKey('devices.mac'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('run_id', sa.String(64), nullable=False),
        sa.Column('last_end', sa.Float(), nullable=False),
        sa.Column('samples', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.Float(), nullable=False), sa.Column('completed_at', sa.Float()))
    op.create_index('ix_calibrations_mac', 'calibrations', ['mac'])
    op.create_table('baselines',
        sa.Column('mac', sa.String(17), sa.ForeignKey('devices.mac'), primary_key=True),
        sa.Column('bytes_per_second', sa.Float()),
        sa.Column('calibration_id', sa.Integer(), sa.ForeignKey('calibrations.id'), nullable=False),
        sa.Column('calibrated_at', sa.Float(), nullable=False))
    op.create_table('events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False))
    op.create_index('ix_events_name', 'events', ['name'])
    op.create_table('latest_snapshot', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('payload', sa.JSON(), nullable=False))


def downgrade():
    for name in ('latest_snapshot', 'events', 'baselines', 'calibrations', 'audit', 'devices'):
        op.drop_table(name)

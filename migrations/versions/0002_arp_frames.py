"""Quadros ARP guardados para o visualizador de pacotes (ADR 0014)."""
from alembic import op
import sqlalchemy as sa

revision = '0002_arp_frames'
down_revision = '0001_backend'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('arp_frames',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('captured_at', sa.Float(), nullable=False),
        sa.Column('capture_run_id', sa.String(64), nullable=False),
        sa.Column('source', sa.String(16), nullable=False),
        sa.Column('eth_src', sa.String(17), nullable=False),
        sa.Column('eth_dst', sa.String(17), nullable=False),
        sa.Column('opcode', sa.Integer(), nullable=False),
        sa.Column('sender_mac', sa.String(17), nullable=False),
        sa.Column('sender_ip', sa.String(15), nullable=False),
        sa.Column('target_mac', sa.String(17), nullable=False),
        sa.Column('target_ip', sa.String(15), nullable=False),
        sa.Column('raw', sa.LargeBinary(128), nullable=False))
    op.create_index('ix_arp_frames_captured_at', 'arp_frames', ['captured_at'])
    op.create_index('ix_arp_frames_eth_src', 'arp_frames', ['eth_src'])
    op.create_index('ix_arp_frames_sender_ip', 'arp_frames', ['sender_ip'])


def downgrade():
    op.drop_table('arp_frames')

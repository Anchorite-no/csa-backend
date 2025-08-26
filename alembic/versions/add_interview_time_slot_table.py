"""add interview time slot table

Revision ID: add_interview_time_slot_table
Revises: update_interview_logic
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_interview_time_slot_table'
down_revision = 'update_interview_logic'
branch_labels = None
depends_on = None


def upgrade():
    # 创建面试时间段表
    op.create_table('interview_time_slot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slot_name', sa.String(length=50), nullable=False),
        sa.Column('day_of_week', sa.String(length=10), nullable=False),
        sa.Column('start_time', sa.String(length=10), nullable=False),
        sa.Column('end_time', sa.String(length=10), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=True),
        sa.Column('venue', sa.String(length=50), nullable=True),
        sa.Column('max_capacity', sa.Integer(), nullable=True),
        sa.Column('current_count', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_time_slot_id'), 'interview_time_slot', ['id'], unique=False)
    
    # 为interview表添加time_slot_id字段
    op.add_column('interview', sa.Column('time_slot_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_interview_time_slot_id'), 'interview', ['time_slot_id'], unique=False)
    op.create_foreign_key(None, 'interview', 'interview_time_slot', ['time_slot_id'], ['id'])


def downgrade():
    # 删除外键约束
    op.drop_constraint(None, 'interview', type_='foreignkey')
    op.drop_index(op.f('ix_interview_time_slot_id'), table_name='interview')
    op.drop_column('interview', 'time_slot_id')
    
    # 删除面试时间段表
    op.drop_index(op.f('ix_interview_time_slot_id'), table_name='interview_time_slot')
    op.drop_table('interview_time_slot')

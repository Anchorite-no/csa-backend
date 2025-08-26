"""remove slot_name unique constraint

Revision ID: remove_slot_name_unique
Revises: add_interview_time_slot_table
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_slot_name_unique'
down_revision = 'add_interview_time_slot_table'
branch_labels = None
depends_on = None


def upgrade():
    # 移除slot_name的唯一约束
    # 注意：SQLite不支持直接删除约束，需要重新创建表
    # 这里我们使用一个变通方法
    
    # 1. 创建临时表
    op.create_table('interview_time_slot_temp',
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
    
    # 2. 复制数据
    op.execute("""
        INSERT INTO interview_time_slot_temp 
        SELECT * FROM interview_time_slot
    """)
    
    # 3. 删除原表
    op.drop_table('interview_time_slot')
    
    # 4. 重命名临时表
    op.rename_table('interview_time_slot_temp', 'interview_time_slot')
    
    # 5. 重新创建索引
    op.create_index(op.f('ix_interview_time_slot_id'), 'interview_time_slot', ['id'], unique=False)


def downgrade():
    # 重新添加唯一约束（如果需要回滚）
    # 注意：这可能会导致数据冲突
    pass

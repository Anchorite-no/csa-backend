"""update interview logic

Revision ID: update_interview_logic
Revises: add_evaluation_fields
Create Date: 2024-12-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'update_interview_logic'
down_revision = 'add_evaluation_fields'
branch_labels = None
depends_on = None


def upgrade():
    # 为recruitment表添加一面二面通过状态字段
    op.add_column('recruitment', sa.Column('first_round_passed', sa.Boolean(), nullable=True, default=False))
    op.add_column('recruitment', sa.Column('second_round_passed', sa.Boolean(), nullable=True, default=False))
    
    # 更新现有记录的interview_status
    # 将所有not_started和screening状态改为first_round
    op.execute("UPDATE recruitment SET interview_status = 'first_round' WHERE interview_status IN ('not_started', 'screening')")
    
    # 设置默认值
    op.execute("UPDATE recruitment SET first_round_passed = FALSE WHERE first_round_passed IS NULL")
    op.execute("UPDATE recruitment SET second_round_passed = FALSE WHERE second_round_passed IS NULL")


def downgrade():
    # 移除添加的字段
    op.drop_column('recruitment', 'second_round_passed')
    op.drop_column('recruitment', 'first_round_passed')
    
    # 恢复interview_status的默认值
    op.execute("UPDATE recruitment SET interview_status = 'not_started' WHERE interview_status = 'first_round'")

"""add evaluation table

Revision ID: add_evaluation_table
Revises: 0d9ed7a4bf00
Create Date: 2024-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_evaluation_table'
down_revision = '0d9ed7a4bf00'
branch_labels = None
depends_on = None


def upgrade():
    # 创建evaluation表
    op.create_table('evaluation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=36), nullable=False),
        sa.Column('evaluator_id', sa.String(length=36), nullable=False),
        sa.Column('evaluator_name', sa.String(length=50), nullable=False),
        sa.Column('evaluation_comment', sa.Text(), nullable=False),
        sa.Column('evaluation_time', sa.DateTime(), nullable=True),
        sa.Column('department', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['uid'], ['recruitment.uid'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_id'), 'evaluation', ['id'], unique=False)
    
    # 修改recruitment表，移除evaluation_comment和evaluator_id字段
    op.drop_column('recruitment', 'evaluation_comment')
    op.drop_column('recruitment', 'evaluator_id')


def downgrade():
    # 恢复recruitment表的字段
    op.add_column('recruitment', sa.Column('evaluator_id', sa.String(length=36), nullable=True))
    op.add_column('recruitment', sa.Column('evaluation_comment', sa.Text(), nullable=True))
    
    # 删除evaluation表
    op.drop_index(op.f('ix_evaluation_id'), table_name='evaluation')
    op.drop_table('evaluation')

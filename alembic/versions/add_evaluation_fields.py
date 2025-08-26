"""add evaluation fields

Revision ID: add_evaluation_fields
Revises: add_evaluation_table
Create Date: 2024-12-19 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_evaluation_fields'
down_revision = 'add_evaluation_table'
branch_labels = None
depends_on = None


def upgrade():
    # 为evaluation表添加新的评分字段
    op.add_column('evaluation', sa.Column('technical_skills', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('communication_skills', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('problem_solving', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('teamwork', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('learning_ability', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('motivation', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('overall_score', sa.Float(), nullable=True))
    op.add_column('evaluation', sa.Column('strengths', sa.Text(), nullable=True))
    op.add_column('evaluation', sa.Column('weaknesses', sa.Text(), nullable=True))
    op.add_column('evaluation', sa.Column('result', sa.String(length=20), nullable=True))
    op.add_column('evaluation', sa.Column('recommended_department', sa.String(length=50), nullable=True))


def downgrade():
    # 移除添加的字段
    op.drop_column('evaluation', 'recommended_department')
    op.drop_column('evaluation', 'result')
    op.drop_column('evaluation', 'weaknesses')
    op.drop_column('evaluation', 'strengths')
    op.drop_column('evaluation', 'overall_score')
    op.drop_column('evaluation', 'motivation')
    op.drop_column('evaluation', 'learning_ability')
    op.drop_column('evaluation', 'teamwork')
    op.drop_column('evaluation', 'problem_solving')
    op.drop_column('evaluation', 'communication_skills')
    op.drop_column('evaluation', 'technical_skills')

"""add interview table

Revision ID: add_interview_table
Revises: add_evaluation_table
Create Date: 2024-12-19 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_interview_table'
down_revision = 'add_evaluation_table'
branch_labels = None
depends_on = None


def upgrade():
    # 创建interview表
    op.create_table('interview',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=36), nullable=False),
        sa.Column('stage', sa.String(length=20), nullable=False),
        sa.Column('interview_date', sa.DateTime(), nullable=False),
        sa.Column('interviewer', sa.String(length=50), nullable=False),
        sa.Column('interview_duration', sa.Integer(), nullable=True),
        sa.Column('technical_skills', sa.Float(), nullable=True),
        sa.Column('communication_skills', sa.Float(), nullable=True),
        sa.Column('problem_solving', sa.Float(), nullable=True),
        sa.Column('teamwork', sa.Float(), nullable=True),
        sa.Column('learning_ability', sa.Float(), nullable=True),
        sa.Column('motivation', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=True),
        sa.Column('strengths', sa.Text(), nullable=True),
        sa.Column('weaknesses', sa.Text(), nullable=True),
        sa.Column('technical_questions', sa.Text(), nullable=True),
        sa.Column('behavioral_questions', sa.Text(), nullable=True),
        sa.Column('additional_notes', sa.Text(), nullable=True),
        sa.Column('recommended_department', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['uid'], ['recruitment.uid'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_id'), 'interview', ['id'], unique=False)
    op.create_index(op.f('ix_interview_uid'), 'interview', ['uid'], unique=False)
    
    # 为recruitment表添加interview_status字段
    op.add_column('recruitment', sa.Column('interview_status', sa.String(length=20), nullable=True))


def downgrade():
    # 删除recruitment表的interview_status字段
    op.drop_column('recruitment', 'interview_status')
    
    # 删除interview表
    op.drop_index(op.f('ix_interview_uid'), table_name='interview')
    op.drop_index(op.f('ix_interview_id'), table_name='interview')
    op.drop_table('interview')

"""initial schema: stations, silver_observations, gold_kpis_mensuales

Revision ID: 0001
Revises:
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("provincia", sa.Text(), nullable=True),
        sa.Column("latitud", sa.Float(), nullable=True),
        sa.Column("longitud", sa.Float(), nullable=True),
        sa.Column("elevacion", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "silver_observations",
        sa.Column("station_code", sa.Text(), nullable=False),
        sa.Column("fecha", sa.Text(), nullable=False),
        sa.Column("hora", sa.Text(), nullable=False),
        sa.Column("ts", sa.Float(), nullable=True),
        sa.Column("th", sa.Float(), nullable=True),
        sa.Column("pres_est", sa.Float(), nullable=True),
        sa.Column("pres_nmm", sa.Float(), nullable=True),
        sa.Column("p3", sa.Float(), nullable=True),
        sa.Column("p24", sa.Float(), nullable=True),
        sa.Column("correc_alt", sa.Float(), nullable=True),
        sa.Column("Tmax", sa.Float(), nullable=True),
        sa.Column("Tmin", sa.Float(), nullable=True),
        sa.Column("LL", sa.Float(), nullable=True),
        sa.Column("temp_seco", sa.Float(), nullable=True),
        sa.Column("temp_humedo", sa.Float(), nullable=True),
        sa.Column("hum_ptor", sa.Float(), nullable=True),
        sa.Column("hum_tvap", sa.Float(), nullable=True),
        sa.Column("hum_hr", sa.Float(), nullable=True),
        sa.Column("viento_dir", sa.Text(), nullable=True),
        sa.Column("viento_vel", sa.Float(), nullable=True),
        sa.Column("visibilidad", sa.Float(), nullable=True),
        sa.Column("tend_car", sa.Text(), nullable=True),
        sa.Column("tend_dif", sa.Text(), nullable=True),
        sa.Column("source_sha256", sa.Text(), nullable=False),
        sa.Column("validated_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("station_code", "fecha", "hora", "source_sha256"),
    )
    op.create_table(
        "gold_kpis_mensuales",
        sa.Column("station_code", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("avg_ts", sa.Float(), nullable=True),
        sa.Column("avg_th", sa.Float(), nullable=True),
        sa.Column("avg_pres_nmm", sa.Float(), nullable=True),
        sa.Column("min_Tmin", sa.Float(), nullable=True),
        sa.Column("max_Tmax", sa.Float(), nullable=True),
        sa.Column("avg_hum_hr", sa.Float(), nullable=True),
        sa.Column("days_with_data", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("station_code", "year", "month"),
    )


def downgrade() -> None:
    op.drop_table("gold_kpis_mensuales")
    op.drop_table("silver_observations")
    op.drop_table("stations")
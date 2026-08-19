"""phase 5 timescale hypertable and continuous aggregate

Revision ID: bc7e2855f65b
Revises: d60c13596e6b
Create Date: 2026-08-19 23:30:10.603752

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bc7e2855f65b"
down_revision: str | Sequence[str] | None = "d60c13596e6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: Phase 1's docker-compose already ships the
    # timescale/timescaledb-ha image with this extension available, but
    # a migration shouldn't assume that -- it should be able to create
    # it itself against any Postgres 16 that has the extension files.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # A hypertable requires the partitioning column (ts) in every
    # unique/PK constraint on the table. Reshape both before converting
    # -- see app/models/telemetry.py's TelemetryPoint docstring for why
    # this is (id, ts) and (flight_id, seq_no, ts), not just adding ts
    # on the side.
    op.drop_constraint("telemetry_points_pkey", "telemetry_points", type_="primary")
    op.drop_constraint("uq_telemetry_flight_seq", "telemetry_points", type_="unique")
    op.create_primary_key("telemetry_points_pkey", "telemetry_points", ["id", "ts"])
    op.create_unique_constraint(
        "uq_telemetry_flight_seq", "telemetry_points", ["flight_id", "seq_no", "ts"]
    )

    # The old single-column flight_id/ts indexes are superseded by the
    # composite one below, which serves the actual query pattern
    # (keyset-paginate one flight's points ordered by ts).
    op.drop_index("ix_telemetry_points_flight_id", table_name="telemetry_points")
    op.drop_index("ix_telemetry_points_ts", table_name="telemetry_points")
    op.create_index(
        "ix_telemetry_points_flight_ts", "telemetry_points", ["flight_id", "ts"]
    )

    # migrate_data=>true: earlier phases' live-testing already left rows
    # in this table on any dev DB that's been through them -- a fresh DB
    # has zero rows, so this is a no-op there, but the migration must be
    # correct against both.
    op.execute(
        "SELECT create_hypertable("
        "'telemetry_points', 'ts', "
        "chunk_time_interval => INTERVAL '1 day', "
        "migrate_data => true)"
    )

    # A continuous aggregate: a per-flight, per-minute rollup so a
    # flight-summary query (avg/max altitude, max accel, sample count)
    # never has to scan raw points -- see docs/adr/0010 and
    # docs/BENCHMARKS.md for the measured difference. WITH NO DATA: an
    # initial refresh over however much history already exists can be
    # slow and shouldn't block a migration; refresh_continuous_aggregate
    # is called explicitly after (or the policy below catches up on its
    # own schedule).
    op.execute(
        """
        CREATE MATERIALIZED VIEW telemetry_1m
        WITH (timescaledb.continuous) AS
        SELECT
            flight_id,
            time_bucket('1 minute', ts) AS bucket,
            avg(alt_ft) AS avg_alt_ft,
            max(alt_ft) AS max_alt_ft,
            avg(vel_ft_s) AS avg_vel_ft_s,
            max(vel_ft_s) AS max_vel_ft_s,
            max(accel_g) AS max_accel_g,
            count(*) AS sample_count
        FROM telemetry_points
        GROUP BY flight_id, bucket
        WITH NO DATA
        """
    )
    op.execute(
        "SELECT add_continuous_aggregate_policy("
        "'telemetry_1m', "
        "start_offset => INTERVAL '3 hours', "
        "end_offset => INTERVAL '1 minute', "
        "schedule_interval => INTERVAL '1 minute')"
    )


def downgrade() -> None:
    # The continuous aggregate and its policy are cleanly reversible --
    # do that part for real.
    op.execute("SELECT remove_continuous_aggregate_policy('telemetry_1m', if_exists => true)")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_1m")

    # Converting a hypertable back into a plain table is not something
    # Timescale supports directly (there is no un-create_hypertable).
    # The only honest way to actually reverse it is drop-and-recreate --
    # i.e. lose the table's data -- which is a much bigger hammer than
    # what every other downgrade() in this project does. Rather than
    # pretend this is a clean rollback by quietly leaving the table as a
    # hypertable while reverting its indexes underneath it (a state this
    # codebase never actually runs against), refuse outright and say why.
    raise RuntimeError(
        "Cannot downgrade past the telemetry_points hypertable conversion: "
        "TimescaleDB has no reverse of create_hypertable(). Restore from a "
        "backup taken before this migration, or drop and recreate "
        "telemetry_points from the previous revision's schema if the data "
        "isn't needed."
    )

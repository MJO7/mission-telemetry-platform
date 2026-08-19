-- Phase 5 benchmark data: see docs/BENCHMARKS.md for what this is used
-- to measure and why. Self-contained and idempotent-ish (fixed UUIDs,
-- ON CONFLICT DO NOTHING on the org/vehicle/flight rows) so it can be
-- re-run to reproduce the numbers in that doc.
--
-- Deliberately NOT run through the API or the app's ORM models: this is
-- a one-time bulk data generation step, not application traffic, and
-- generate_series()-driven server-side INSERTs are orders of magnitude
-- faster than round-tripping a million rows through HTTP/ORM one at a
-- time -- exactly the kind of job raw SQL is the right tool for.
--
-- Usage: make benchmark-seed  (or: psql ... -f scripts/benchmark_seed.sql)

INSERT INTO organizations (id, name, slug, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-0000000000b0', 'Benchmark Org', 'benchmark-org', now(), now())
ON CONFLICT (id) DO NOTHING;

INSERT INTO vehicles (id, org_id, name, description, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-0000000000b1',
    '00000000-0000-0000-0000-0000000000b0',
    'Benchmark Vehicle',
    'Phase 5 query-optimization benchmark data -- see docs/BENCHMARKS.md',
    now(), now()
)
ON CONFLICT (id) DO NOTHING;

-- One "subject" flight (the one every benchmark query below targets)
-- plus five "noise" flights whose rows are interleaved in time with
-- it. The noise flights are what make this a realistic test: without
-- them, all 500k of the subject flight's rows are the only occupants
-- of their time chunks, and a plain time-ordered index scan finds them
-- for free -- which is not what a real multi-tenant table looks like.
-- Interleaving five other flights' data across the same time range is
-- what makes filtering by flight_id an actual, measurable problem for
-- the query planner to solve.
INSERT INTO flights (id, org_id, vehicle_id, name, processing_status, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-0000000000f0', '00000000-0000-0000-0000-0000000000b0',
     '00000000-0000-0000-0000-0000000000b1', 'Benchmark Flight (subject, 500k pts)', 'pending', now(), now()),
    ('00000000-0000-0000-0000-0000000000f1', '00000000-0000-0000-0000-0000000000b0',
     '00000000-0000-0000-0000-0000000000b1', 'Noise Flight 1', 'pending', now(), now()),
    ('00000000-0000-0000-0000-0000000000f2', '00000000-0000-0000-0000-0000000000b0',
     '00000000-0000-0000-0000-0000000000b1', 'Noise Flight 2', 'pending', now(), now()),
    ('00000000-0000-0000-0000-0000000000f3', '00000000-0000-0000-0000-0000000000b0',
     '00000000-0000-0000-0000-0000000000b1', 'Noise Flight 3', 'pending', now(), now()),
    ('00000000-0000-0000-0000-0000000000f4', '00000000-0000-0000-0000-0000000000b0',
     '00000000-0000-0000-0000-0000000000b1', 'Noise Flight 4', 'pending', now(), now()),
    ('00000000-0000-0000-0000-0000000000f5', '00000000-0000-0000-0000-0000000000b0',
     '00000000-0000-0000-0000-0000000000b1', 'Noise Flight 5', 'pending', now(), now())
ON CONFLICT (id) DO NOTHING;

-- Subject flight: 500,000 points, one every 100ms (~13.9 hours of flight time).
INSERT INTO telemetry_points (id, org_id, flight_id, seq_no, ts, phase, alt_ft, vel_ft_s, accel_g, qw, qx, qy, qz)
SELECT
    gen_random_uuid(),
    '00000000-0000-0000-0000-0000000000b0',
    '00000000-0000-0000-0000-0000000000f0',
    s,
    '2026-08-01T00:00:00Z'::timestamptz + (s * interval '100 milliseconds'),
    (ARRAY['pad','powered','coasting','apogee','drogue','main','landed'])[1 + (s % 7)]::flight_phase,
    1000 + (s % 5000), 100 + (s % 800), 1 + (s % 5) * 0.5, 1, 0, 0, 0
FROM generate_series(0, 499999) AS s
ON CONFLICT DO NOTHING;

-- Five noise flights, 100,000 points each, timestamps jittered within
-- the same 100ms slots as the subject flight so they land interleaved
-- in the same time chunks, not off to the side in their own.
INSERT INTO telemetry_points (id, org_id, flight_id, seq_no, ts, phase, alt_ft, vel_ft_s, accel_g, qw, qx, qy, qz)
SELECT
    gen_random_uuid(),
    '00000000-0000-0000-0000-0000000000b0',
    flight_id,
    s,
    '2026-08-01T00:00:00Z'::timestamptz + (s * interval '100 milliseconds') + (random() * interval '90 milliseconds'),
    (ARRAY['pad','powered','coasting','apogee','drogue','main','landed'])[1 + (s % 7)]::flight_phase,
    1000 + (s % 5000), 100 + (s % 800), 1 + (s % 5) * 0.5, 1, 0, 0, 0
FROM generate_series(0, 99999) AS s
CROSS JOIN (VALUES
    ('00000000-0000-0000-0000-0000000000f1'::uuid),
    ('00000000-0000-0000-0000-0000000000f2'::uuid),
    ('00000000-0000-0000-0000-0000000000f3'::uuid),
    ('00000000-0000-0000-0000-0000000000f4'::uuid),
    ('00000000-0000-0000-0000-0000000000f5'::uuid)
) AS noise_flights(flight_id)
ON CONFLICT DO NOTHING;

ANALYZE telemetry_points;

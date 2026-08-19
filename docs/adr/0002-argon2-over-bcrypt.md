# ADR-0002: argon2id for password hashing, not bcrypt

**Status:** Accepted — Phase 1

## Context
Passwords for local (non-OAuth) accounts need to be hashed at rest.
bcrypt is the long-standing default; argon2id won the 2015 Password
Hashing Competition and is the current OWASP recommendation.

## Decision
Use `argon2-cffi`'s `PasswordHasher` with its default OWASP-baseline
parameters (19 MiB memory, 2 iterations, 1 lane), not hand-tuned.

## Alternatives considered
**bcrypt.** Well-understood, available everywhere, but its cost function
is CPU-time only. An attacker with a GPU or ASIC farm parallelizes
bcrypt cracking cheaply because each hash attempt needs negligible
memory. argon2id's tunable *memory* cost is the differentiator: making
each guess require ~19 MiB means an attacker's parallelism is capped by
memory bandwidth/cost, not just compute — far more expensive to scale
in hardware.

**Hand-tuning argon2 parameters higher.** Rejected without a load test:
increasing memory/time cost raises login latency under concurrent load,
and guessing at a "stronger" number without measuring is exactly the
unmeasured-complexity trap the project rule (`Measure it; do not invent
it`) warns against. Default OWASP baseline now; revisit with a k6 number
in Phase 8 if login endpoint latency ever becomes a target metric.

## Consequences
Slightly higher CPU/RAM per login than bcrypt at equivalent settings —
irrelevant at this project's request volume, and the honest tradeoff to
name on a whiteboard.

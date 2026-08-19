/**
 * "Full jitter" exponential backoff (the AWS architecture-blog formula):
 * delay = random(0, min(cap, base * 2^attempt))
 *
 * Why full jitter and not plain exponential backoff: plain backoff means
 * every client that disconnected at the same moment (e.g. the API
 * process restarting) reconnects in lockstep on the same schedule --
 * that's a thundering herd hitting the server the instant it comes back
 * up. Spreading each client's retry uniformly across the *whole*
 * [0, cap] window, not just jittering around the edge of it, is what
 * actually breaks up the herd.
 */
const BASE_MS = 500;
const CAP_MS = 15_000;

export function computeBackoffDelay(
  attempt: number,
  random: () => number = Math.random,
): number {
  const cap = Math.min(CAP_MS, BASE_MS * 2 ** attempt);
  return Math.round(random() * cap);
}

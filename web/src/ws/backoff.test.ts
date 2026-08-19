import { describe, expect, it } from "vitest";
import { computeBackoffDelay } from "./backoff";

describe("computeBackoffDelay", () => {
  it("is 0 at the low end of the jitter window", () => {
    expect(computeBackoffDelay(0, () => 0)).toBe(0);
    expect(computeBackoffDelay(5, () => 0)).toBe(0);
  });

  it("grows with attempt number, up to the cap", () => {
    // random() pinned at 1 (the high end) isolates the cap itself.
    expect(computeBackoffDelay(0, () => 1)).toBe(500); // base
    expect(computeBackoffDelay(1, () => 1)).toBe(1000);
    expect(computeBackoffDelay(2, () => 1)).toBe(2000);
    expect(computeBackoffDelay(10, () => 1)).toBe(15000); // capped, not 500 * 2^10
  });

  it("never exceeds the cap even at a very high attempt count", () => {
    expect(computeBackoffDelay(30, () => 1)).toBeLessThanOrEqual(15000);
  });

  it("never goes negative", () => {
    expect(computeBackoffDelay(3, () => 0)).toBeGreaterThanOrEqual(0);
  });
});

import { describe, expect, it } from "vitest";
import { decodeAccessToken, roleAtLeast } from "./jwt";

function fakeToken(payload: Record<string, unknown>): string {
  const base64url = btoa(JSON.stringify(payload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `header.${base64url}.signature`;
}

describe("decodeAccessToken", () => {
  it("decodes a well-formed payload", () => {
    const payload = {
      sub: "u1",
      org_id: "o1",
      role: "engineer" as const,
      exp: 123,
      iat: 100,
      type: "access" as const,
    };
    expect(decodeAccessToken(fakeToken(payload))).toEqual(payload);
  });

  it("throws on a token with no payload segment", () => {
    expect(() => decodeAccessToken("not-a-jwt")).toThrow(/malformed/);
  });
});

describe("roleAtLeast", () => {
  // Mirrors app/core/rbac.py's _RANK exactly -- if these two ever
  // disagree, the UI would show controls the server then rejects.
  it("owner satisfies every requirement", () => {
    expect(roleAtLeast("owner", "viewer")).toBe(true);
    expect(roleAtLeast("owner", "engineer")).toBe(true);
    expect(roleAtLeast("owner", "owner")).toBe(true);
  });

  it("viewer satisfies only viewer", () => {
    expect(roleAtLeast("viewer", "viewer")).toBe(true);
    expect(roleAtLeast("viewer", "engineer")).toBe(false);
    expect(roleAtLeast("viewer", "owner")).toBe(false);
  });

  it("engineer satisfies viewer and engineer but not owner", () => {
    expect(roleAtLeast("engineer", "viewer")).toBe(true);
    expect(roleAtLeast("engineer", "engineer")).toBe(true);
    expect(roleAtLeast("engineer", "owner")).toBe(false);
  });
});

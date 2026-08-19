/**
 * Client-side JWT payload decode -- for UI purposes only (e.g. hiding a
 * "create" button from a viewer). This is NOT a verification step: the
 * browser has no way to check the signature, and doesn't need to --
 * every request carrying this token is re-verified server-side
 * (app/core/rbac.py) on every single call. Trusting this decoded
 * payload for anything actually security-relevant client-side would be
 * decorative, not real access control.
 */
export interface AccessTokenPayload {
  sub: string;
  org_id: string;
  role: "owner" | "engineer" | "viewer";
  exp: number;
  iat: number;
  type: "access";
}

export function decodeAccessToken(token: string): AccessTokenPayload {
  const payloadSegment = token.split(".")[1];
  if (!payloadSegment) {
    throw new Error("malformed access token: no payload segment");
  }
  const base64 = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
  const json = atob(base64);
  return JSON.parse(json) as AccessTokenPayload;
}

/** owner > engineer > viewer -- mirrors app/core/rbac.py's _RANK exactly,
 * so the UI hides/shows controls using the same ordering the server
 * actually enforces. */
const RANK: Record<AccessTokenPayload["role"], number> = {
  viewer: 0,
  engineer: 1,
  owner: 2,
};

export function roleAtLeast(
  role: AccessTokenPayload["role"],
  minimum: AccessTokenPayload["role"],
): boolean {
  return RANK[role] >= RANK[minimum];
}

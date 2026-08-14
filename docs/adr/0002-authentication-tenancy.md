# ADR 0002 — Authentication and tenant isolation

Status: accepted for MVP.

The API uses short-lived signed access tokens and opaque rotating refresh tokens. Access tokens include subject, session id, token type, issue time, not-before time, expiry, issuer, and audience. Only the configured signing algorithm is accepted.

Refresh tokens are transported in an HttpOnly cookie and stored in the database only as SHA-256 hashes. Rotation revokes the previous session and links it to its replacement. Reuse of a revoked refresh token revokes active sessions for the user.

Every authenticated request resolves the current principal from the signed access token and verifies that the referenced session remains active. Workspace membership is the source of tenant authorization. Project and resource identifiers supplied by clients are resolved back to their owning workspace before a controller executes.

Authentication errors do not disclose whether an account exists. Tenant authorization failures use a generic not-found response to reduce enumeration risk. Login rate limiting is process-local for development and CI; production deployment must enforce an additional distributed or edge limit.

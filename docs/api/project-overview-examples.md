# Project overview examples

Default 24-hour UTC window:

```http
GET /core/projects/{project_id}/overview
Authorization: Bearer <session-token>
```

Seven-day daily buckets restricted to production agents:

```http
GET /core/projects/{project_id}/overview?from=2026-06-12T00:00:00Z&to=2026-06-19T00:00:00Z&bucket=day&environment=production
Authorization: Bearer <session-token>
```

The response uses the standard API envelope and places the read model in `data`. Clients must treat nullable latency, success-rate, change, and cost fields according to the metric contract rather than substituting fabricated values.

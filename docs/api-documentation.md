# API reference

FastAPI generates an interactive OpenAPI explorer at `/docs` and a schema at `/openapi.json`.

Authenticated endpoints use `Authorization: Bearer <access_token>`. The current login/register requests use JSON bodies.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service health |
| POST | `/api/auth/register` | Create account, return bearer token |
| POST | `/api/auth/login` | Verify credentials and return bearer token |
| POST | `/api/auth/logout` | Client-side token logout acknowledgment |
| GET | `/api/auth/me` | Current user profile |
| POST | `/api/monitoring/start` | Create or return the user's active session |
| POST | `/api/monitoring/{id}/stop` | Complete a session |
| GET | `/api/monitoring/status` | Current active session |
| POST | `/api/detection/process` | Process one transient base64 JPEG frame for an active owned session |
| GET | `/api/sessions` | List up to 100 owned sessions |
| DELETE | `/api/sessions/{id}` | Delete one owned session and its events |
| GET | `/api/alerts` | List recent events for owned sessions |
| PATCH | `/api/alerts/{id}/acknowledge` | Acknowledge one owned alert |
| GET | `/api/analytics/overview` | Aggregate metrics from saved sessions |
| GET/PUT | `/api/settings` | Read/update the user's EAR and MAR thresholds |

Detection request JSON contains `session_id`, `image` (JPEG data URL or base64), `ear_threshold`, `mar_threshold`, `prolonged`, `blink`, `yawn_edge`, and `alert_sent`. The image field is size-limited. Successful responses include status, heuristic risk, EAR/MAR, PERCLOS, and normalized landmarks. Face-not-detected responses contain an empty landmark array. Detection failures return HTTP errors rather than synthetic measurements.

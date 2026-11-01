# Database schema

The SQLAlchemy models create these tables on API startup. MySQL is the Compose default; SQLite can be selected through `DATABASE_URL`.

| Table | Important fields | Ownership and relations |
| --- | --- | --- |
| `users` | email, name, Argon2 password hash, role, created_at | Unique email; parent of sessions |
| `monitoring_sessions` | user_id, start/end timestamps, status, blink/yawn/alert counts, closure aggregate | Foreign key to users; cascade delete |
| `detection_events` | session_id, kind, severity, detail, timestamp, acknowledged | Foreign key to session; cascade delete |
| `user_preferences` | user_id, EAR threshold, MAR threshold, updated_at | Unique user_id, cascade delete |

Indexes cover account email, session owner, event session/type/time, and preference owner. Session reporting aggregates duration, counters, and average observed closure fraction from stored measurements. Raw webcam frames and facial landmarks are not stored.

Schema evolution is currently handled by SQLAlchemy `create_all` at startup. A versioned Alembic migration history is not included yet.

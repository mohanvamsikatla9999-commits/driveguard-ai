# System architecture

## Data flow

1. The user explicitly starts a browser camera session.
2. The browser captures a 320-pixel-wide JPEG roughly every 350 ms. Audio is never requested.
3. The authenticated browser sends each frame to `POST /api/detection/process`.
4. FastAPI decodes the frame in memory and passes RGB pixels to one shared MediaPipe Face Landmarker instance. Frames and extracted landmarks are not written to disk.
5. EAR, MAR, blink/yawn edge indications, a 60-second rolling eye-closure fraction, and heuristic status are returned to the browser.
6. Session counters, aggregate closure samples, and alert events are stored in the database. No images or face templates are persisted.

The app uses a Next.js client and Python FastAPI API. SQLAlchemy models support MySQL 8 and SQLite for local development. `docker-compose.yml` includes MySQL, the API, and the web server. API authentication is JWT bearer auth with Argon2 password hashes; authorization filters session and alert reads by user ID.

## Detection rules

- EAR uses the six-point eye landmark ratio independently for each eye; the dashboard displays both and their mean.
- MAR uses inner lip vertical distances divided by mouth width.
- Browser temporal logic suppresses normal short closures and marks a closure lasting at least 1.5 seconds as prolonged.
- Yawns require a configurable MAR threshold plus an opening edge.
- PERCLOS is the proportion of valid frames below the configurable EAR threshold over the previous 60 seconds. It is not a validated clinical or automotive standard.
- Risk is a rule score from 0 to 100, not a probability. Lighting, camera angle, glasses, and individual differences can affect the readings.

The interface states when no face is found and warns if multiple faces appear. A multiple-face frame measures the first detected face only, and does not create a fatigue alert.

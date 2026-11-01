# Installation guide

## Docker Compose (recommended)

1. Copy `.env.example` to `.env` and change `JWT_SECRET`, `MYSQL_PASSWORD`, and `MYSQL_ROOT_PASSWORD`.
2. Run `docker compose up --build` from the project root.
3. Visit http://localhost:3000. API health is http://localhost:8000/api/health and interactive docs are http://localhost:8000/docs.

The bundled backend image uses Python 3.11, which has the MediaPipe Tasks runtime required by the bundled `face_landmarker.task` model.

## Run processes separately

Use Python 3.11+ with a MediaPipe wheel available for the selected OS/Python ABI and Node.js 22.

1. Copy `.env.example` to `.env`; set `DATABASE_URL` to MySQL or `sqlite:///./driveguard.db`.
2. In `backend`, create and activate a virtual environment, run `python -m pip install -r requirements.txt`, then `python -m uvicorn app.main:app --reload`.
3. In `frontend`, run `npm install` and `npm run dev`.
4. Open http://localhost:3000, register, then use Live Monitor and allow camera access.

Camera capture works on localhost or HTTPS only. A camera device and adequate lighting are needed to evaluate real face detection. The repository tests validate calculations, account/session operations, and processing of a real encoded blank image; they do not measure fatigue accuracy or replace hardware/browser testing.

# DRIVEGUARD AI

Local-first driver fatigue monitoring prototype. Camera frames are processed in memory and never persisted. This is a heuristic driver-assistance prototype, not a medical assessment or certified automotive safety system.

## Run
1. Copy `.env.example` to `.env`, change secrets.
2. Start MySQL: `docker compose up -d db` (SQLite is available via `DATABASE_URL=sqlite:///./driveguard.db`).
3. Backend: `cd backend; python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt; uvicorn app.main:app --reload`.
4. Frontend: `cd frontend; npm install; npm run dev`.
5. Visit http://localhost:3000, register, and grant camera permission from Live Monitor. API docs: http://localhost:8000/docs.

The detector uses MediaPipe Face Landmarker and actual camera frames. The official task model is bundled at `backend/app/models/face_landmarker.task` from [MediaPipe Models](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task). A frame is sent to the local API for measurement and immediately discarded. The UI reports API/model failures; it does not synthesize detections. Browser camera access requires localhost or HTTPS. Admin role requires direct operator assignment. Password reset delivery and TLS deployment are not implemented.

PERCLOS is a rolling frame fraction with both eyes below the configured EAR threshold, not a validated automotive or clinical standard. Measurements are sensitive to lighting, glasses, camera quality and face angle. Risk is a heuristic, not a probability. Alerts cannot control a vehicle. No face images or video are stored.

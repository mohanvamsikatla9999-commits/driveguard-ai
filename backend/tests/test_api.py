import uuid
import base64

import cv2
import numpy as np
from app.main import DB, FrameIn, Login, Register, auth, eye_aspect_ratio, login, logout, me, mouth_aspect_ratio, process, register, sessions, start, stop

def test_ear_and_mar_are_finite_for_symmetric_landmarks():
    eye=[(0,1),(1,0),(2,0),(4,1),(2,2),(1,2)]
    mouth=[(0,0),(1,-1),(2,-2),(3,-1),(4,0),(3,1),(2,2),(1,1)]
    assert eye_aspect_ratio(eye)>0
    assert mouth_aspect_ratio(mouth)>0

def test_detection_endpoint_processes_real_encoded_frame_without_inventing_face():
    s=DB()
    email=f"frame-{uuid.uuid4().hex}@example.com"
    try:
        token=register(Register(name="Frame Test",email=email,password="LongTestPass123!"),s)["access_token"]
        user=auth(token,s);sid=start(user,s)["session_id"]
        ok,encoded=cv2.imencode(".jpg",np.zeros((240,320,3),dtype=np.uint8));assert ok
        response=process(FrameIn(session_id=sid,image=base64.b64encode(encoded).decode()),user,s)
        assert response["face_detected"] is False
        assert response["landmarks"]==[]
    finally:s.close()

def test_register_login_and_user_scoped_session_lifecycle():
    email=f"test-{uuid.uuid4().hex}@example.com"
    s=DB()
    try:
        created=register(Register(name="Test Driver",email=email,password="LongTestPass123!"),s)
        assert created["user"]["email"]==email
        signed=login(Login(email=email,password="LongTestPass123!"),s)
        user=auth(signed["access_token"],s)
        assert me(user)["email"]==email
        sid=start(user,s)["session_id"]
        assert any(row["id"]==sid for row in sessions(user,s))
        assert stop(sid,user,s)["status"]=="complete"
        assert logout()=={"ok":True}
    finally:s.close()

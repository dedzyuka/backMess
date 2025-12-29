# tests/test_users.py
import pytest
from fastapi.testclient import TestClient
import uuid

from app.main import app

client = TestClient(app)

def test_register_user_success():
    """Тест успешной регистрации пользователя"""
    test_user_id = uuid.uuid4()
    
    response = client.post("/api/v1/users/register", json={
        "user_id": str(test_user_id),
        "nickname": "test_user",
        "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtestpublickey123456789\n-----END PUBLIC KEY-----"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["nickname"] == "test_user"
    assert data["user_id"] == str(test_user_id)
    assert "created_at" in data

def test_register_user_duplicate_id():
    """Тест регистрации с существующим user_id"""
    test_user_id = uuid.uuid4()
    
    # Первая регистрация
    client.post("/api/v1/users/register", json={
        "user_id": str(test_user_id),
        "nickname": "user1",
        "public_key": "public_key_1"
    })
    
    # Вторая попытка с тем же user_id
    response = client.post("/api/v1/users/register", json={
        "user_id": str(test_user_id),
        "nickname": "user2", 
        "public_key": "public_key_2"
    })
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
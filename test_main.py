import time
import uuid

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def unique_email() -> str:
    return f"test_{uuid.uuid4().hex}_{int(time.time())}@example.com"


def register_user(email: str = None, password: str = "Str0ngPassw0rd!"):
    if email is None:
        email = unique_email()
    response = client.post("/auth/register", json={"email": email, "password": password})
    return email, password, response


def register_and_login(email: str = None, password: str = "Str0ngPassw0rd!"):
    email, password, _ = register_user(email, password)
    login_response = client.post("/auth/login", json={"email": email, "password": password})
    token = login_response.json()["access_token"]
    return email, password, token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_new_user_returns_200_and_no_password():
    email = unique_email()
    response = client.post("/auth/register", json={"email": email, "password": "Str0ngPassw0rd!"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_400():
    email = unique_email()
    first = client.post("/auth/register", json={"email": email, "password": "Str0ngPassw0rd!"})
    assert first.status_code == 200

    second = client.post("/auth/register", json={"email": email, "password": "OtherPassw0rd!"})
    assert second.status_code == 400


def test_login_correct_credentials_returns_token():
    email, password, _ = register_user()
    response = client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401():
    email, _, _ = register_user()
    response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401


def test_me_without_token_returns_401():
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_with_valid_token_returns_correct_user():
    email, _, token = register_and_login()
    response = client.get("/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_create_favorite_without_token_returns_401():
    response = client.post("/favorites", json={"item_type": "apod", "item_id": "2024-01-01"})
    assert response.status_code == 401


def test_create_favorite_with_token_and_list_it():
    _, _, token = register_and_login()
    headers = auth_headers(token)

    create_response = client.post(
        "/favorites",
        json={
            "item_type": "apod",
            "item_id": "2024-01-01",
            "title": "Test APOD",
            "image_url": "http://example.com/img.jpg"
        },
        headers=headers
    )
    assert create_response.status_code == 200
    favorite_id = create_response.json()["id"]

    list_response = client.get("/favorites", headers=headers)
    assert list_response.status_code == 200
    favorite_ids = [f["id"] for f in list_response.json()]
    assert favorite_id in favorite_ids


def test_delete_favorite_with_other_users_token_returns_404():
    _, _, owner_token = register_and_login()
    _, _, other_token = register_and_login()

    create_response = client.post(
        "/favorites",
        json={"item_type": "apod", "item_id": "2024-02-02"},
        headers=auth_headers(owner_token)
    )
    favorite_id = create_response.json()["id"]

    delete_response = client.delete(f"/favorites/{favorite_id}", headers=auth_headers(other_token))
    assert delete_response.status_code == 404

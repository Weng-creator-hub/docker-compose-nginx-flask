from app import app

app.config["TESTING"] = True

with app.test_client() as client:
    response = client.get("/health")

    assert response.status_code == 200, (
        f"Unexpected status: {response.status_code}"
    )

    data = response.get_json()
    assert isinstance(data, dict) and data.get("status") == "ok", (
        f"Unexpected response: {data}"
    )

print("PASS: /health returned 200 and status=ok")

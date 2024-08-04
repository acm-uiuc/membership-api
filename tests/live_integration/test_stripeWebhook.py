def test_invalid_webhook_fails(api_client):
    """Sad path: make sure that invalid payloads are not processed"""
    response = api_client.post("/api/v1/provisioning/member", data={"message": "some nonsense"})
    assert response.status_code == 421
    assert response.json() == {'message': 'Invalid payload.'}
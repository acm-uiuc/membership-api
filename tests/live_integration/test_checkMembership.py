def test_valid_member(api_client):
    response = api_client.get("/api/v1/checkMembership?netId=dsingh14")
    assert response.status_code == 200
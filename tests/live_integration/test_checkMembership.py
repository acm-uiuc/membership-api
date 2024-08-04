def test_valid_member(api_client):
    response = api_client.get("/api/v1/checkMembership?netId=dsingh14")
    assert response.status_code == 200
    assert response.json() == {"netId": "dsingh14", "isPaidMember": True}

def test_invalid_member(api_client):
    response = api_client.get("/api/v1/checkMembership?netId=invalid")
    assert response.status_code == 200
    assert response.json() == {"netId": "invalid", "isPaidMember": False,}

def test_invalid_parameters(api_client):
    response = api_client.get("/api/v1/checkMembership")
    assert response.status_code == 400
    assert response.json() == {"message": "No NetID provided."}
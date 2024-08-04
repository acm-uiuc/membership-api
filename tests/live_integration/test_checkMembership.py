def test_valid_member(api_client):
    response = api_client.get("/api/v1/checkMembership?netId=dsingh14")
    assert response.status_code == 200
    assert response.json() == {"netId": "dsingh14", "isPaidMember": True}
    assert response.headers['x-acm-membership-source']  # it should at least exist, may or may not be cached
    response = api_client.get("/api/v1/checkMembership?netId=dsingh14")
    assert response.status_code == 200
    assert response.json() == {"netId": "dsingh14", "isPaidMember": True}
    assert response.headers['x-acm-membership-source'] == 'dynamo'

def test_invalid_member(api_client):
    response = api_client.get("/api/v1/checkMembership?netId=invalid")
    assert response.status_code == 200
    assert response.json() == {"netId": "invalid", "isPaidMember": False,}
    assert response.headers['x-acm-membership-source'] == 'aad' # non-member results should always be double checked against aad


def test_invalid_parameters(api_client):
    response = api_client.get("/api/v1/checkMembership")
    assert response.status_code == 400
    assert response.json() == {"message": "No NetID provided."}
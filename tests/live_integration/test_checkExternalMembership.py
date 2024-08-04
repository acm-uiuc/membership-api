def test_valid_member_testinglist(api_client):
    response = api_client.get("/api/v1/checkExternalMembership?netId=testinguser&list=testinglist")
    assert response.status_code == 200
    assert response.json() == {"netId":"testinguser","list":"testinglist","isPaidMember":True}                                                                                                    

def test_invalid_member(api_client):
    response = api_client.get("/api/v1/checkExternalMembership?netId=testinguser&list=nonexistentlist")
    assert response.status_code == 200
    assert response.json() == {"netId":"testinguser","list":"nonexistentlist","isPaidMember":False}                                                                                                   

def test_invalid_parameters(api_client):
    response = api_client.get("/api/v1/checkExternalMembership")
    assert response.status_code == 400
    assert response.json() == {"message": "No NetID provided."}
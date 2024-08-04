import requests
def test_member_nosession_checkout_session(api_client):
    response = api_client.get("/api/v1/checkout/session?netid=dsingh14")
    assert response.status_code == 409
    assert response.json() == {"message": "dsingh14 is already a paid member."}                                                                                         

def test_no_netid_checkout_session(api_client):
    response = api_client.get("/api/v1/checkout/session")
    assert response.status_code == 400
    assert response.json() == {"message": "No NetID provided"}                                                                                  

def test_new_user_checkout_session(api_client):
    response = api_client.get("/api/v1/checkout/session?netid=newuser")
    assert response.status_code == 200
    assert response.text.startswith("https://checkout.stripe.com")
    stripe_response = requests.get(response.text)
    assert stripe_response.status_code == 200
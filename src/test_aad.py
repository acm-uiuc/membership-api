import requests_mock
from .aad import get_entra_access_token
def test_get_entra_access_token(sample_secret):
    with requests_mock.Mocker() as m:
        m.post("https://login.microsoftonline.com/c8d9148f-9a59-4db3-827d-42ea0c2b6e2e/oauth2/v2.0/token", json={'access_token': 'some_access_token', 'token_type': 'Bearer', 'expires_in': 3600})
        response = get_entra_access_token(sample_secret)
        assert response['access_token'] == 'some_access_token'

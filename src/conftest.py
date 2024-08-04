import pytest
@pytest.fixture
def sample_secret():
    """Fixture to return sample secrets."""
    return {"AAD_CLIENT_ID":"91e1b1a0-a219-4e3a-95c0-724eed58b784","AAD_CLIENT_SECRET":"bfdfsQ~fjslpjfkds.2KR0VgGR5DFjsyo3gpuU1.dFd","STRIPE_KEY_CHECKOUT":"rk_test_hi","AAD_ENROLL_ENDPOINT_SECRET":"whsec_nothing"}


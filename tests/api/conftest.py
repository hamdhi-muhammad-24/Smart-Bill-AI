import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.auth.dependencies import (
    get_current_user,
    require_admin,
)
from app.auth.schemas import UserOut


def _test_admin() -> UserOut:
    return UserOut(
        id=0,
        email="test-admin@slt.local",
        role="ADMIN",
    )


from unittest.mock import patch

@pytest.fixture(scope="session")
def client() -> TestClient:
    app.dependency_overrides[get_current_user] = _test_admin
    app.dependency_overrides[require_admin] = _test_admin
    with patch("app.auth.dependencies.azure_scheme.openid_config.load_config"):
        with TestClient(app, headers={"Authorization": "Bearer test-admin-token"}) as c:
            yield c
    app.dependency_overrides.clear()

"""No DB needed -- the rank comparison in require_role is pure."""
import uuid

import pytest
from fastapi import HTTPException

from app.core.rbac import CurrentUser, require_role
from app.models.tenancy import Role


def _user(role: Role) -> CurrentUser:
    return CurrentUser(user_id=str(uuid.uuid4()), org_id=str(uuid.uuid4()), role=role)


@pytest.mark.parametrize(
    "actual,minimum,should_pass",
    [
        (Role.owner, Role.viewer, True),
        (Role.owner, Role.engineer, True),
        (Role.owner, Role.owner, True),
        (Role.engineer, Role.viewer, True),
        (Role.engineer, Role.engineer, True),
        (Role.engineer, Role.owner, False),
        (Role.viewer, Role.engineer, False),
        (Role.viewer, Role.owner, False),
        (Role.viewer, Role.viewer, True),
    ],
)
async def test_role_rank_enforced(actual: Role, minimum: Role, should_pass: bool):
    dep = require_role(minimum)
    user = _user(actual)
    if should_pass:
        result = await dep(user)
        assert result is user
    else:
        with pytest.raises(HTTPException) as exc_info:
            await dep(user)
        assert exc_info.value.status_code == 403

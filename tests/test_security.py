"""Design doc section 9 -- Security. Owned by `security-control-plane`
(step 4) and `execution-service` (step 5); every line below is reproduced
from the checklist verbatim and will be implemented as those steps land."""

import pytest

pytestmark = pytest.mark.skip(reason="needs security-control-plane (step 4) / execution-service (step 5)")


def test_authorized_tool_call_is_allowed():
    """Authorized tool call -> ALLOW"""


def test_unauthorized_classification_is_denied():
    """Unauthorized classification -> DENY"""


def test_unauthorized_acl_or_department_is_denied():
    """Unauthorized ACL/department -> DENY (the denial-path demo, section 1.2)"""


def test_expired_capability_is_denied():
    """Expired capability -> DENY"""


def test_disabled_tool_is_denied_even_with_a_valid_capability():
    """Disabled tool -> DENY even with a valid capability (section 1.3)"""


def test_execution_zone_has_no_code_path_to_postgres():
    """No code path exists for the execution zone to reach Postgres directly"""


def test_execution_zone_has_no_code_path_to_the_docker_socket():
    """No code path exists for the execution zone to reach the Docker socket"""

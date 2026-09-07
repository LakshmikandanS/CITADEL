"""Design doc section 9 -- Artifact. Owned by `artifact-pipeline` (step 8).

The state-machine half of these (RELEASED is terminal, the TEMP -> RELEASED
walk) is already covered in test_foundation.py; what is skipped here is the
API-layer and Verifier behaviour that step 8 builds.
"""

import pytest

pytestmark = pytest.mark.skip(reason="needs artifact-pipeline (step 8)")


def test_generate_verify_approve_release_happy_path():
    """Generate -> verify -> approve -> release, full happy path"""


def test_released_artifact_rejects_further_mutation():
    """A RELEASED artifact rejects any further mutation attempt"""


def test_verification_failure_marks_the_task_failed():
    """A verification failure marks the task FAILED (no silent pass)"""

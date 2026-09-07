"""Design doc section 9 -- Orchestration. Owned by `orchestrator` (step 7)."""

import pytest

pytestmark = pytest.mark.skip(reason="needs orchestrator (step 7)")


def test_plan_is_schema_conformant_json():
    """Task -> plan produces valid, schema-conformant JSON"""


def test_every_plan_step_reaches_the_tool_gateway():
    """Each plan step's action reaches the Tool Gateway, never a tool directly"""


def test_observation_feeds_the_next_think():
    """Observation feeds correctly into the next step's THINK"""


def test_agent_terminates_on_success_failed_and_max_steps():
    """Agent terminates on SUCCESS, FAILED, and MAX_STEPS correctly"""

"""Design doc section 9 -- RAG. Owned by `data-plane-rag` (step 6)."""

import pytest

pytestmark = pytest.mark.skip(reason="needs data-plane-rag (step 6)")


def test_authorized_document_is_retrieved():
    """Correctly-tagged, authorized document -> retrieved"""


def test_out_of_scope_document_is_filtered_before_reaching_the_agent():
    """Correctly-tagged, out-of-scope document -> filtered before reaching the agent"""


def test_document_missing_its_acl_sidecar_is_rejected_at_ingestion():
    """Document missing its ACL sidecar -> ingestion rejected outright"""

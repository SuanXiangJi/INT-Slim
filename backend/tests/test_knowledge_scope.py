from app.services.knowledge_scope import (
    SYSTEM_KB_USER_ID,
    knowledge_scope,
    readable_owner_ids,
)


def test_regular_user_can_read_private_and_public_knowledge():
    user_id = bytes.fromhex("11" * 16)

    assert readable_owner_ids(user_id) == (user_id, SYSTEM_KB_USER_ID)


def test_system_identity_does_not_duplicate_its_scope():
    assert readable_owner_ids(SYSTEM_KB_USER_ID) == (SYSTEM_KB_USER_ID,)


def test_public_documents_are_read_only_from_user_perspective():
    user_id = bytes.fromhex("22" * 16)

    assert knowledge_scope(user_id, user_id) == "private"
    assert knowledge_scope(SYSTEM_KB_USER_ID, user_id) == "public"

"""
tests/test_visitor_memory.py — verifies the same-day face-matching logic
directly. Uses a real photo, since Haar cascade face detection genuinely
needs a real face to find — a synthetic image won't exercise the actual
detection path.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import visitor_memory as vm
import config

_TEST_PHOTO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_assets", "sample_person.jpg")


@pytest.fixture(autouse=True)
def clean_visitor_memory():
    vm.reset()
    yield
    vm.reset()


def _has_test_photo():
    return os.path.exists(_TEST_PHOTO)


@pytest.mark.skipif(not _has_test_photo(), reason="requires test_assets/sample_person.jpg")
def test_first_sighting_is_new():
    with open(_TEST_PHOTO, "rb") as f:
        photo = f.read()
    assert vm.check_and_record(photo) == "new"


@pytest.mark.skipif(not _has_test_photo(), reason="requires test_assets/sample_person.jpg")
def test_repeated_face_eventually_recognized():
    with open(_TEST_PHOTO, "rb") as f:
        photo = f.read()
    results = [vm.check_and_record(photo) for _ in range(4)]
    # exact same face shown repeatedly should eventually register as a
    # confident match — doesn't need to be immediate, but must happen
    assert "confident" in results


def test_disabled_always_returns_new():
    config.ENABLE_VISITOR_MEMORY = False
    try:
        # even garbage bytes should short-circuit to 'new' when disabled,
        # since it should never even attempt face detection
        assert vm.check_and_record(b"not a real image") == "new"
    finally:
        config.ENABLE_VISITOR_MEMORY = True


def test_reset_clears_memory():
    if not _has_test_photo():
        pytest.skip("requires test_assets/sample_person.jpg")
    with open(_TEST_PHOTO, "rb") as f:
        photo = f.read()
    for _ in range(4):
        vm.check_and_record(photo)
    vm.reset()
    assert vm.check_and_record(photo) == "new"


def test_garbage_bytes_dont_crash():
    # malformed/non-image bytes should be handled gracefully, not raise
    result = vm.check_and_record(b"definitely not a jpeg")
    assert result == "new"

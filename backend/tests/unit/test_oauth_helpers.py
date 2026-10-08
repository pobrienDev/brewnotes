import pytest

from app.security.oauth import _clean_avatar_url, _clean_display_name, safe_next_path


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("/", "/"),
        ("/recipes/abc", "/recipes/abc"),
        ("/styles?q=ipa&page=2", "/styles?q=ipa&page=2"),
        ("/path#frag", "/path#frag"),
        ("//evil.example", "/"),
        ("/\\evil.example", "/"),
        ("https://evil.example", "/"),
        ("javascript:alert(1)", "/"),
        ("/api/v1/me", "/"),
        ("/with space", "/"),
        ("/tab\there", "/"),
        ("/" + "a" * 500, "/"),
    ],
)
def test_safe_next_path(value: str | None, expected: str) -> None:
    assert safe_next_path(value) == expected


def test_display_name_cleaning() -> None:
    assert _clean_display_name("  Pat  ") == "Pat"
    assert _clean_display_name(None) == "Brewer"
    assert _clean_display_name("") == "Brewer"
    assert _clean_display_name(42) == "Brewer"
    assert len(_clean_display_name("x" * 500)) == 200


@pytest.mark.parametrize(
    ("value", "kept"),
    [
        ("https://avatars.githubusercontent.com/u/1?v=4", True),
        ("https://lh3.googleusercontent.com/a/abc=s96-c", True),
        ("http://avatars.githubusercontent.com/u/1", False),
        ("https://evil.example/a.png", False),
        ("https://avatars.githubusercontent.com.evil.example/x", False),
        ("not a url", False),
        (None, False),
        ("https://lh3.googleusercontent.com/" + "a" * 2000, False),
    ],
)
def test_avatar_url_cleaning(value: str | None, kept: bool) -> None:
    result = _clean_avatar_url(value)
    assert (result == value) if kept else (result is None)

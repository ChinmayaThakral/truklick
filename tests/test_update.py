"""Update-check behaviour.

The risky failure modes here are not "it didn't find an update" — they are:
  * a malformed/garbage tag being treated as NEWER (would nag forever, or worse,
    push someone toward a bogus download), and
  * a network hiccup breaking startup or a live run.
Both are covered below.
"""
import pytest

from truklick.update import UpdateInfo, is_newer, parse_version


@pytest.mark.parametrize("latest,current,expected", [
    ("v0.1.4", "0.1.3", True),
    ("0.1.4", "0.1.3", True),
    ("v0.2.0", "0.1.9", True),
    ("v1.0.0", "0.9.9", True),
    ("v0.1.10", "0.1.9", True),      # numeric, not lexicographic
    ("v0.1.3", "0.1.3", False),      # same version is not an update
    ("v0.1.2", "0.1.3", False),      # older is not an update
    ("v0.1.3", "0.1.4", False),
])
def test_version_comparison(latest, current, expected):
    assert is_newer(latest, current) is expected


@pytest.mark.parametrize("junk", ["", "garbage", "v", "vX.Y.Z", "latest", "???"])
def test_junk_tags_never_look_newer(junk):
    """A malformed release tag must never be reported as an available update."""
    assert is_newer(junk, "0.1.3") is False


def test_prerelease_suffix_is_ignored_not_misread():
    assert parse_version("v0.2.0-beta.1") == (0, 2, 0)
    assert is_newer("v0.2.0-beta.1", "0.1.9") is True


def test_check_never_raises_when_offline(monkeypatch):
    """A failed check must return None quietly — never break startup or a run."""
    import truklick.update as u

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(u.urllib.request, "urlopen", boom)
    monkeypatch.setattr(u, "_read_cache", lambda: None)
    assert u.check(force=True) is None


def test_notify_is_silent_when_check_fails(monkeypatch, capsys):
    import truklick.update as u
    monkeypatch.setattr(u, "check", lambda force=False: None)
    u.notify_if_available()
    assert capsys.readouterr().out == ""


def test_notify_prints_only_when_newer(monkeypatch, capsys):
    import truklick.update as u
    monkeypatch.setattr(u, "check",
                        lambda force=False: UpdateInfo("0.1.3", "0.1.3", "url", False))
    u.notify_if_available()
    assert capsys.readouterr().out == ""
    monkeypatch.setattr(u, "check",
                        lambda force=False: UpdateInfo("0.1.3", "0.1.4", "url", True))
    u.notify_if_available()
    assert "0.1.4" in capsys.readouterr().out


def test_code_version_matches_packaging():
    """__version__ and pyproject must agree.

    Real bug this catches: v0.1.3 shipped while the code still reported 0.1.0, so the
    update checker told every user on the LATEST build that an update was available —
    permanently. A version that drifts from the release tag makes update checking
    actively wrong rather than merely useless.
    """
    import re
    from pathlib import Path

    from truklick import __version__

    root = Path(__file__).resolve().parent.parent
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    assert m, "no version in pyproject.toml"
    assert m.group(1) == __version__, (
        f"pyproject says {m.group(1)} but truklick.__version__ is {__version__}")

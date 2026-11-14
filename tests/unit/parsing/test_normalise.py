from hangar.core.config import NormalisationConfig
from hangar.parsing.normalise import normalise

COLLAPSE = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)
KEEP_SPACES = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=False)


def test_nfkc_replaces_ligatures_and_non_breaking_spaces() -> None:
    assert normalise("ﬁre extinguisher", COLLAPSE) == "fire extinguisher"


def test_line_endings_become_newlines() -> None:
    assert normalise("one\r\ntwo\rthree\n", KEEP_SPACES) == "one\ntwo\nthree\n"


def test_runs_of_spaces_and_tabs_become_one_space() -> None:
    assert normalise("torque \t  the\t\tbolt", COLLAPSE) == "torque the bolt"


def test_collapsing_keeps_newlines() -> None:
    assert normalise("one  \n\n  two", COLLAPSE) == "one \n\n two"


def test_spaces_are_kept_when_collapsing_is_off() -> None:
    assert normalise("torque \t the", KEEP_SPACES) == "torque \t the"

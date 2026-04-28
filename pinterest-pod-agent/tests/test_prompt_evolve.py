from scripts.smoke_evomap import FakeDb
from app.evomap.prompt_evolve import PromptEvolver


def test_keyword_signals() -> None:
    signals = PromptEvolver(db=FakeDb()).get_keyword_signals()
    assert signals
    assert signals[0].keyword == "dog mom shirt"

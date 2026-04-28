import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evomap.prompt_evolve import PromptContext, PromptEvolver


class FakeScalarResult:
    def all(self):
        return [
            SimpleNamespace(
                impressions=1000,
                clicks=56,
                ctr=0.056,
                keywords=["dog mom shirt", "custom pet gift"],
                strategy_snapshot={},
            ),
            SimpleNamespace(
                impressions=800,
                clicks=28,
                ctr=0.035,
                keywords=["dog mom shirt", "funny quote tee"],
                strategy_snapshot={},
            ),
        ]


class FakeDb:
    def scalars(self, _statement):
        return FakeScalarResult()


if __name__ == "__main__":
    evolver = PromptEvolver(db=FakeDb(), min_impressions=100)
    context = PromptContext(
        product_type="t-shirt",
        niche="pet lovers",
        audience="women who buy custom dog gifts",
        season="Mother's Day",
        offer="15% off",
        destination_url="https://example.com/products/dog-mom-shirt",
    )
    signals = evolver.get_keyword_signals()
    print("signals:")
    for signal in signals:
        print(f"- {signal.keyword}: weight={signal.weight}, avg_ctr={signal.avg_ctr}")
    print("\nprompt_head:")
    print(evolver.build_content_prompt(context).splitlines()[0])

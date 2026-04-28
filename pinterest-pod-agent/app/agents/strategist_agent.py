from app.evomap.prompt_evolve import PromptEvolver


class StrategistAgent:
    def __init__(self, evolver: PromptEvolver) -> None:
        self.evolver = evolver

    def suggest_next_strategy(self, *, niche: str | None = None, product_type: str | None = None) -> str:
        return self.evolver.generate_strategy_advice(niche=niche, product_type=product_type)

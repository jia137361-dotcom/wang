from app.evomap.prompt_evolve import PromptContext, PromptEvolver


class DesignAgent:
    def __init__(self, evolver: PromptEvolver) -> None:
        self.evolver = evolver

    def build_visual_prompt(self, context: PromptContext) -> str:
        return self.evolver.build_visual_prompt(context)

from app.evomap.prompt_evolve import PromptContext, PromptEvolver


class ContentAgent:
    def __init__(self, evolver: PromptEvolver) -> None:
        self.evolver = evolver

    def generate_brief(self, context: PromptContext) -> str:
        return self.evolver.generate_content_brief(context)

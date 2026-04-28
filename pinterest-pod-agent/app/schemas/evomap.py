from pydantic import BaseModel, Field


class PromptContextRequest(BaseModel):
    product_type: str = Field(max_length=80)
    niche: str = Field(max_length=120)
    audience: str = Field(max_length=240)
    season: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    destination_url: str | None = Field(default=None, max_length=1024)
    generate: bool = False


class PromptBuildResponse(BaseModel):
    prompt: str
    generated_text: str | None = None


class StrategyAdviceResponse(BaseModel):
    advice: str

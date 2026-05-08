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


class ContentTemplateUpsert(BaseModel):
    scope: str = Field(max_length=120)
    template_type: str = Field(pattern="^(title_description|image_prompt)$")
    template_text: str = Field(min_length=1)
    is_active: bool = True


class ContentTemplateRead(BaseModel):
    id: int
    scope: str
    template_type: str
    template_text: str
    is_active: bool

    model_config = {"from_attributes": True}

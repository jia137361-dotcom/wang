"""Insert EvoMap content templates into DB and generate content."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_sessionmaker
from app.models.content_template import ContentTemplate
from sqlalchemy import select

# ── Template definitions ────────────────────────────────────────────────────

TITLE_DESC_TEMPLATES = {
    "global": """Act as an expert Pinterest marketing strategist.
Generate a Pinterest Pin title and description.

Context:
- Niche: {niche}
- Product Type: {product_type}
- Target Audience: {audience}
- Season: {season}
- Offer: {offer}

Rules:
1. TITLE: Extremely concise, catchy, SEO-optimized. Max 60 characters. No quotes.
2. DESCRIPTION: Under 200 characters. Include a subtle CTA and exactly 4 high-traffic hashtags. No quotes.

Output exactly in this format:
[TITLE]
<your title here>
[DESCRIPTION]
<your description here>""",

    "home decor": """Act as an expert Pinterest marketing strategist for HOME DECOR products.
Generate a Pinterest Pin title and description.

Context:
- Niche: {niche}
- Product Type: {product_type}
- Target Audience: {audience}
- Season: {season}
- Offer: {offer}

Home Decor Style Notes:
- Emphasize aesthetics, transformation, ambiance
- Use emotional triggers: cozy, stunning, dreamy
- Mention room placement (living room, bedroom, etc.)

Rules:
1. TITLE: Extremely concise, catchy, SEO-optimized. Max 60 characters. No quotes. Include the room or vibe.
2. DESCRIPTION: Under 200 characters. Include a subtle CTA and exactly 4 high-traffic hashtags. No quotes.

Output exactly in this format:
[TITLE]
<your title here>
[DESCRIPTION]
<your description here>""",

    "fashion": """Act as an expert Pinterest marketing strategist for FASHION products.
Generate a Pinterest Pin title and description.

Context:
- Niche: {niche}
- Product Type: {product_type}
- Target Audience: {audience}
- Season: {season}
- Offer: {offer}

Fashion Style Notes:
- Emphasize style, trendiness, self-expression
- Use aspirational language: chic, effortless, statement
- Mention outfit pairing or occasion

Rules:
1. TITLE: Extremely concise, catchy, SEO-optimized. Max 60 characters. No quotes.
2. DESCRIPTION: Under 200 characters. Include a subtle CTA and exactly 4 high-traffic hashtags. No quotes.

Output exactly in this format:
[TITLE]
<your title here>
[DESCRIPTION]
<your description here>""",
}

IMAGE_PROMPT_TEMPLATES = {
    "global": """Generate an EXTREMELY detailed image generation prompt for a Pinterest Pin featuring {product_type} in the {niche} niche.

Requirements:
- Clear subject: {product_type} as the hero element, beautifully styled
- Environment: {niche}-appropriate setting with contextual props
- Lighting: Golden hour natural light OR soft studio lighting with subtle shadows
- Camera: Shot on 35mm lens, f/1.8, 8K resolution, photorealistic
- Color palette: Warm, inviting tones appropriate for {niche}
- Aesthetic: Pinterest-worthy, highly shareable, aspirational lifestyle feel
- Target audience vibe: {audience}

Output the image prompt on a single line, extremely detailed, 200-400 words.""",

    "home decor": """Generate an EXTREMELY detailed image generation prompt for a Pinterest Pin featuring {product_type} in the {niche} niche.

Requirements:
- Clear subject: {product_type} as the hero element in a beautifully styled interior
- Environment: A sunlit, meticulously curated room with complementary decor pieces, plants, and soft textiles
- Lighting: Morning sunlight streaming through gauze curtains, creating soft shadows and warm highlights
- Camera: Shot on 50mm lens, f/1.4, 8K resolution, photorealistic, architectural digest style
- Color palette: Neutral base with strategic warm accents, {niche}-appropriate color harmony
- Aesthetic: High-end interior magazine spread, aspirational, warm and inviting
- Target audience vibe: {audience}

Output the image prompt on a single line, extremely detailed, 200-400 words.""",

    "fashion": """Generate an EXTREMELY detailed image generation prompt for a Pinterest Pin featuring {product_type} in the {niche} niche.

Requirements:
- Clear subject: {product_type} as the hero element, worn or styled on-trend
- Environment: Fashion-forward setting — urban streetscape, minimalist studio, or chic interior
- Lighting: Golden hour backlight OR dramatic softbox studio lighting
- Camera: Shot on 85mm lens, f/1.4, 8K resolution, photorealistic, Vogue editorial style
- Color palette: On-trend seasonal palette appropriate for {niche}
- Aesthetic: Editorial fashion photography, aspirational, effortlessly cool
- Target audience vibe: {audience}

Output the image prompt on a single line, extremely detailed, 200-400 words.""",
}


def upsert_template(db, scope: str, template_type: str, template_text: str, is_active: bool = True):
    template = db.scalar(
        select(ContentTemplate).where(
            ContentTemplate.scope == scope,
            ContentTemplate.template_type == template_type,
        )
    )
    if template is None:
        template = ContentTemplate(
            scope=scope,
            template_type=template_type,
            template_text=template_text,
            is_active=is_active,
        )
        db.add(template)
    else:
        template.template_text = template_text
        template.is_active = is_active
    return template


def main():
    db = get_sessionmaker()()
    try:
        inserted = 0
        for scope, text in TITLE_DESC_TEMPLATES.items():
            t = upsert_template(db, scope, "title_description", text)
            print(f"  [title_description] scope={t.scope} -> id={t.id}")
            inserted += 1

        for scope, text in IMAGE_PROMPT_TEMPLATES.items():
            t = upsert_template(db, scope, "image_prompt", text)
            print(f"  [image_prompt]     scope={t.scope} -> id={t.id}")
            inserted += 1

        db.commit()
        print(f"\nInserted/updated {inserted} templates successfully.")

        # Verify
        all_t = list(db.scalars(select(ContentTemplate).order_by(ContentTemplate.scope, ContentTemplate.template_type)).all())
        print(f"\nTotal templates in DB: {len(all_t)}")
        for t in all_t:
            print(f"  id={t.id} [{t.template_type}] scope={t.scope} active={t.is_active}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

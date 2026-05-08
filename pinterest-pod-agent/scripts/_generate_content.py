"""Generate Pinterest content using templates and create publish_jobs."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_sessionmaker
from app.models.content_template import ContentTemplate
from app.models.publish_job import PublishJob
from sqlalchemy import select

# ── Product/Niche/Audience combos ──────────────────────────────────────────

COMBOS = [
    {
        "niche": "minimalist decor",
        "product_type": "Canvas Wall Art",
        "audience": "modern homeowners",
        "season": "Spring Refresh",
        "offer": "Free Shipping",
        "board_name": "Minimalist Home Inspiration",
    },
    {
        "niche": "street style",
        "product_type": "Oversized Hoodie",
        "audience": "Gen Z trendsetters",
        "season": "Fall Layers",
        "offer": "20% Off First Order",
        "board_name": "Street Style Essentials",
    },
    {
        "niche": "cozy home",
        "product_type": "Ceramic Mug",
        "audience": "coffee & tea lovers",
        "season": "Winter Warmth",
        "offer": "Buy 2 Get 1 Free",
        "board_name": "Cozy Morning Vibes",
    },
    {
        "niche": "home office",
        "product_type": "Desk Lamp",
        "audience": "remote workers & freelancers",
        "season": "Productivity Boost",
        "offer": "15% Off Bundle",
        "board_name": "Home Office Setup",
    },
    {
        "niche": "pet lovers",
        "product_type": "Dog Bandana",
        "audience": "dog moms & dads",
        "season": "Summer Fun",
        "offer": "Free Personalization",
        "board_name": "Pawsome Style",
    },
]

# ── AI-Generated Content ────────────────────────────────────────────────────
# Generated using the stored templates as guidance

GENERATED = [
    # ── Canvas Wall Art / Minimalist Decor ──
    {
        "title": "Spring Minimalist Wall Art to Transform Your Space",
        "description": (
            "Elevate your home with this stunning minimalist canvas wall art. "
            "Clean lines and serene tones bring instant calm to any room. "
            "Perfect for modern homeowners craving a seasonal refresh. "
            "Tap to shop with free shipping today! "
            "#MinimalistDecor #WallArt #SpringRefresh #ModernHome"
        ),
        "image_prompt": (
            "A premium stretched canvas wall art print featuring abstract minimalist geometric shapes in warm beige, "
            "terracotta, and cream tones, hanging on a bright white wall in a sun-drenched modern living room. "
            "A mid-century wooden console table sits below with a small ceramic vase holding dried pampas grass. "
            "Morning sunlight streams through floor-to-ceiling linen curtains, casting soft diagonal shadows "
            "across the wall and floor. A plush cream boucle armchair is partially visible in the foreground. "
            "Shot on 50mm lens at f/1.4, 8K resolution, photorealistic, editorial interior photography. "
            "The color palette is warm neutral with subtle sage green accents. The composition follows the "
            "rule of thirds with the canvas as the clear focal point. Shallow depth of field blurs the "
            "background slightly while keeping the artwork razor sharp. Aspirational lifestyle aesthetic "
            "suitable for Architectural Digest. Warm, inviting, serene atmosphere."
        ),
    },
    # ── Oversized Hoodie / Street Style ──
    {
        "title": "The Ultimate Oversized Hoodie for Effortless Cool",
        "description": (
            "Level up your street style with this ultra-soft oversized hoodie. "
            "Dropped shoulders and a relaxed fit make every outfit effortlessly chic. "
            "Layer it up this fall and turn heads wherever you go. "
            "Grab yours now with 20% off your first order! "
            "#StreetStyle #OversizedHoodie #FallFashion #GenZFashion"
        ),
        "image_prompt": (
            "A young model wearing an oversized heather grey hoodie with dropped shoulder seams and a relaxed, "
            "slouchy silhouette, paired with loose-fit cargo pants and chunky white sneakers. The model stands "
            "against a textured concrete wall in a sunlit urban alleyway in late afternoon golden hour. "
            "Warm amber light wraps around the fabric folds, highlighting the plush cotton texture. "
            "A vintage bicycle leans against the wall in the background, partially out of focus. "
            "Shot on 85mm lens at f/1.4, 8K resolution, photorealistic, editorial fashion photography. "
            "Color palette: muted earth tones with pops of neon from distant street art reflections. "
            "The composition centers the hoodie's drape and volume. Shallow depth of field isolates "
            "the subject from the urban backdrop. Vogue street style editorial aesthetic. "
            "Effortlessly cool, aspirational, authentic vibe."
        ),
    },
    # ── Ceramic Mug / Cozy Home ──
    {
        "title": "Handcrafted Ceramic Mug for Your Coziest Mornings",
        "description": (
            "Start every morning right with this artisan ceramic mug. "
            "The perfect companion for coffee, tea, and quiet moments at home. "
            "Its weight, texture, and warmth feel just right in your hands. "
            "Buy 2 get 1 free - stock up on cozy today! "
            "#CeramicMug #CozyHome #CoffeeLovers #MorningRitual"
        ),
        "image_prompt": (
            "A handcrafted speckled ceramic mug in warm oatmeal glaze, filled with steaming latte art, "
            "resting on a rustic wooden side table beside a frost-covered window. Soft morning light "
            "diffuses through the window, illuminating the rising steam in ethereal wisps. A chunky knit "
            "throw blanket drapes over a nearby reading chair, and a stack of vintage books sits in "
            "the corner. Cinnamon sticks and star anise are scattered artfully on the table surface. "
            "Shot on 35mm lens at f/1.8, 8K resolution, photorealistic, cozy lifestyle photography. "
            "Warm cream, oat, and soft brown color palette with hints of frosty blue from the window. "
            "The composition places the mug off-center following the golden ratio, steam curling upward "
            "into the light. Extremely shallow depth of field creates dreamy bokeh from the window frost. "
            "Hygge-inspired, warm, intimate, comforting aesthetic worthy of a coffee brand campaign."
        ),
    },
    # ── Desk Lamp / Home Office ──
    {
        "title": "The Desk Lamp That Makes Working from Home Beautiful",
        "description": (
            "Illuminate your productivity with this sleek, adjustable desk lamp. "
            "Warm LED light reduces eye strain during long work sessions while "
            "adding a touch of elegance to any home office. "
            "Transform your workspace today - 15% off bundles! "
            "#HomeOffice #DeskLamp #WFH #ProductivityHacks"
        ),
        "image_prompt": (
            "A sleek matte black architect desk lamp with brass joints and an adjustable articulated arm, "
            "casting a warm pool of light onto a minimalist oak desk. The desk surface holds a leather-bound "
            "notebook, a mechanical pencil, and a ceramic coffee cup. A 27-inch monitor displays a clean "
            "design interface, blurred in the background. A fiddle leaf fig plant sits in the corner catching "
            "light from a nearby window. Late afternoon sunlight mixes with the lamp's warm glow creating "
            "beautiful dual-source lighting. Shot on 50mm lens at f/2.0, 8K resolution, photorealistic, "
            "interior design photography. Color palette: matte black, warm brass, natural oak, and "
            "deep green from the plant. The composition uses the lamp as a leading line drawing the eye "
            "diagonally across the frame. Aspirational yet attainable workspace aesthetic."
        ),
    },
    # ── Dog Bandana / Pet Lovers ──
    {
        "title": "Adorable Personalized Dog Bandana for Your Best Friend",
        "description": (
            "Make your pup the most stylish one at the park with this custom bandana. "
            "Soft, breathable fabric with fun patterns and optional name embroidery. "
            "Because every dog deserves to look paw-some! "
            "Order now with free personalization included. "
            "#DogBandana #PetLovers #DogMom #PuppyStyle"
        ),
        "image_prompt": (
            "An adorable golden retriever wearing a pastel floral pattern bandana with embroidered name "
            "visible on the corner, sitting happily in a sun-drenched grassy park. The dog's coat gleams "
            "golden in the warm late afternoon sunlight, with a gentle breeze ruffling the bandana fabric. "
            "Wildflowers dot the meadow in the background with soft bokeh circles of light filtering "
            "through tree leaves. A blurred picnic basket and blanket are visible in the distance. "
            "Shot on 85mm lens at f/1.8, 8K resolution, photorealistic, lifestyle pet photography. "
            "Color palette: warm golden tones, soft pastels from the bandana, fresh grass green, "
            "and dappled sunlight. The dog is centered in the frame with the bandana as the key "
            "fashion detail. The expression captures pure joy and companionship. Heartwarming, "
            "shareable, aspirational pet lifestyle aesthetic."
        ),
    },
]


def main():
    db = get_sessionmaker()()
    try:
        created_jobs = []
        for combo, gen in zip(COMBOS, GENERATED):
            job_id = f"job_ai_{uuid.uuid4().hex[:12]}"
            now = datetime.now(UTC)

            job = PublishJob(
                job_id=job_id,
                account_id="test-account-1",
                campaign_id="demo",
                status="pending",
                board_name=combo["board_name"],
                image_path="var/uploads/placeholder.png",
                title=gen["title"],
                description=gen["description"],
                product_type=combo["product_type"],
                niche=combo["niche"],
                audience=combo["audience"],
                season=combo["season"],
                offer=combo["offer"],
                tagged_topics=json.dumps(
                    [combo["niche"].title(), combo["product_type"], combo["audience"].title()]
                ),
            )
            db.add(job)
            created_jobs.append(
                {
                    "job_id": job_id,
                    "title": gen["title"],
                    "niche": combo["niche"],
                    "product_type": combo["product_type"],
                    "image_prompt": gen["image_prompt"],
                }
            )

        db.commit()
        print(f"Created {len(created_jobs)} publish_jobs:\n")

        for j in created_jobs:
            print(f"  Job: {j['job_id']}")
            print(f"  Niche: {j['niche']} | Product: {j['product_type']}")
            print(f"  Title: {j['title']}")
            print(f"  Image Prompt: {j['image_prompt'][:150]}...")
            print()

        # Output JSON for later use
        print("---JSON---")
        print(json.dumps(created_jobs, indent=2))

    finally:
        db.close()


if __name__ == "__main__":
    main()

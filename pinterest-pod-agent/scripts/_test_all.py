"""Queue image generation for AI-generated content and run comprehensive tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_sessionmaker
from app.models.publish_job import PublishJob
from app.models.content_template import ContentTemplate
from app.models.scheduled_task import ScheduledTask
from app.models.social_account import SocialAccount
from sqlalchemy import select, func

IMAGE_SIZE = json.dumps({"width": 800, "height": 1200})

IMAGE_PROMPTS = {
    "job_ai_a44928f88ec2": "A premium stretched canvas wall art print featuring abstract minimalist geometric shapes in warm beige, terracotta, and cream tones, hanging on a bright white wall in a sun-drenched modern living room. A mid-century wooden console table sits below with a small ceramic vase holding dried pampas grass. Morning sunlight streams through floor-to-ceiling linen curtains, casting soft diagonal shadows across the wall and floor. A plush cream boucle armchair is partially visible in the foreground. Shot on 50mm lens at f/1.4, 8K resolution, photorealistic, editorial interior photography. The color palette is warm neutral with subtle sage green accents. The composition follows the rule of thirds with the canvas as the clear focal point. Shallow depth of field blurs the background slightly while keeping the artwork razor sharp. Aspirational lifestyle aesthetic suitable for Architectural Digest. Warm, inviting, serene atmosphere.",
    "job_ai_30f8e7f1ce50": "A young model wearing an oversized heather grey hoodie with dropped shoulder seams and a relaxed, slouchy silhouette, paired with loose-fit cargo pants and chunky white sneakers. The model stands against a textured concrete wall in a sunlit urban alleyway in late afternoon golden hour. Warm amber light wraps around the fabric folds, highlighting the plush cotton texture. A vintage bicycle leans against the wall in the background, partially out of focus. Shot on 85mm lens at f/1.4, 8K resolution, photorealistic, editorial fashion photography. Color palette: muted earth tones with pops of neon from distant street art reflections. The composition centers the hoodie's drape and volume. Shallow depth of field isolates the subject from the urban backdrop. Vogue street style editorial aesthetic. Effortlessly cool, aspirational, authentic vibe.",
    "job_ai_020bccca92e0": "A handcrafted speckled ceramic mug in warm oatmeal glaze, filled with steaming latte art, resting on a rustic wooden side table beside a frost-covered window. Soft morning light diffuses through the window, illuminating the rising steam in ethereal wisps. A chunky knit throw blanket drapes over a nearby reading chair, and a stack of vintage books sits in the corner. Cinnamon sticks and star anise are scattered artfully on the table surface. Shot on 35mm lens at f/1.8, 8K resolution, photorealistic, cozy lifestyle photography. Warm cream, oat, and soft brown color palette with hints of frosty blue from the window. The composition places the mug off-center following the golden ratio, steam curling upward into the light. Extremely shallow depth of field creates dreamy bokeh from the window frost. Hygge-inspired, warm, intimate, comforting aesthetic worthy of a coffee brand campaign.",
    "job_ai_3e0b937b20f5": "A sleek matte black architect desk lamp with brass joints and an adjustable articulated arm, casting a warm pool of light onto a minimalist oak desk. The desk surface holds a leather-bound notebook, a mechanical pencil, and a ceramic coffee cup. A 27-inch monitor displays a clean design interface, blurred in the background. A fiddle leaf fig plant sits in the corner catching light from a nearby window. Late afternoon sunlight mixes with the lamp's warm glow creating beautiful dual-source lighting. Shot on 50mm lens at f/2.0, 8K resolution, photorealistic, interior design photography. Color palette: matte black, warm brass, natural oak, and deep green from the plant. The composition uses the lamp as a leading line drawing the eye diagonally across the frame. Aspirational yet attainable workspace aesthetic.",
    "job_ai_ba87b12a1646": "An adorable golden retriever wearing a pastel floral pattern bandana with embroidered name visible on the corner, sitting happily in a sun-drenched grassy park. The dog's coat gleams golden in the warm late afternoon sunlight, with a gentle breeze ruffling the bandana fabric. Wildflowers dot the meadow in the background with soft bokeh circles of light filtering through tree leaves. A blurred picnic basket and blanket are visible in the distance. Shot on 85mm lens at f/1.8, 8K resolution, photorealistic, lifestyle pet photography. Color palette: warm golden tones, soft pastels from the bandana, fresh grass green, and dappled sunlight. The dog is centered in the frame with the bandana as the key fashion detail. The expression captures pure joy and companionship. Heartwarming, shareable, aspirational pet lifestyle aesthetic.",
}


def main():
    db = get_sessionmaker()()
    results = {"tests": [], "image_gen_queued": []}

    print("=" * 60)
    print("COMPREHENSIVE SYSTEM TEST")
    print("=" * 60)

    # 1. Database Health
    print("\n-- 1. Database Health --")
    try:
        count = db.scalar(select(func.count(ContentTemplate.id)))
        results["tests"].append({"test": "database_templates", "ok": True, "count": count})
        print(f"  [OK] DB connected. Templates: {count}")
    except Exception as e:
        results["tests"].append({"test": "database_templates", "ok": False, "error": str(e)})
        print(f"  [FAIL] DB error: {e}")

    # 2. Content Templates
    print("\n-- 2. Content Templates --")
    templates = list(db.scalars(select(ContentTemplate).order_by(ContentTemplate.template_type, ContentTemplate.scope)).all())
    for t in templates:
        print(f"  [TPL] [{t.template_type}] scope={t.scope} active={t.is_active} (id={t.id})")
    results["tests"].append({"test": "list_templates", "ok": len(templates) > 0, "count": len(templates)})

    # 3. Social Accounts
    print("\n-- 3. Social Accounts --")
    accounts = list(db.scalars(select(SocialAccount)).all())
    for a in accounts:
        print(f"  [ACCT] {a.account_id} | {a.platform} | profile={a.adspower_profile_id} | region={a.proxy_region}")
    results["tests"].append({"test": "accounts", "ok": len(accounts) > 0, "count": len(accounts)})

    # 4. AI-Generated Publish Jobs
    print("\n-- 4. AI-Generated Publish Jobs --")
    ai_jobs = list(db.scalars(
        select(PublishJob).where(PublishJob.job_id.like("job_ai_%")).order_by(PublishJob.created_at.asc())
    ).all())
    for j in ai_jobs:
        print(f"  [JOB] {j.job_id}")
        print(f"        Niche: {j.niche} | Product: {j.product_type}")
        print(f"        Title: {j.title}")
        print(f"        Audience: {j.audience} | Season: {j.season}")
        print(f"        Status: {j.status}")
        print()
    results["tests"].append({"test": "ai_publish_jobs", "ok": len(ai_jobs) >= 5, "count": len(ai_jobs)})

    # 5. Queue Image Generation
    print("\n-- 5. Queue Image Generation (Fal.ai) --")
    from app.jobs.tasks import generate_image_asset_task

    for job_id, prompt in IMAGE_PROMPTS.items():
        job = db.scalar(select(PublishJob).where(PublishJob.job_id == job_id))
        if job is None:
            print(f"  [SKIP] Job {job_id} not found")
            continue
        try:
            result = generate_image_asset_task.delay(prompt, IMAGE_SIZE)
            print(f"  [QUEUED] {job_id}")
            print(f"           Celery Task ID: {result.id}")
            print(f"           Product: {job.product_type} | Niche: {job.niche}")
            results["image_gen_queued"].append({
                "job_id": job_id,
                "celery_task_id": result.id,
                "product": job.product_type,
                "niche": job.niche,
            })
        except Exception as e:
            print(f"  [FAIL] Queue failed for {job_id}: {e}")
            results["image_gen_queued"].append({"job_id": job_id, "error": str(e)})

    # 6. Task Dashboard
    print("\n-- 6. Task Dashboard --")
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total_tasks = db.scalar(select(func.count(ScheduledTask.id)))
    pending = db.scalar(select(func.count(ScheduledTask.id)).where(ScheduledTask.status.in_(["pending", "ready", "scheduled"])))
    running = db.scalar(select(func.count(ScheduledTask.id)).where(ScheduledTask.status == "running"))
    completed = db.scalar(select(func.count(ScheduledTask.id)).where(ScheduledTask.status == "completed"))
    failed = db.scalar(select(func.count(ScheduledTask.id)).where(ScheduledTask.status == "failed"))

    print(f"  Total: {total_tasks} | Pending: {pending} | Running: {running}")
    print(f"  Completed: {completed} | Failed: {failed}")
    results["tests"].append({"test": "task_dashboard", "ok": True, "total": total_tasks, "pending": pending, "completed": completed, "failed": failed})

    # 7. Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_ok = all(t["ok"] for t in results["tests"])
    for t in results["tests"]:
        icon = "[OK]" if t["ok"] else "[FAIL]"
        extra = {k: v for k, v in t.items() if k not in ("test", "ok")}
        print(f"  {icon} {t['test']}: {extra}")

    print(f"\n  Image generation tasks queued: {len(results['image_gen_queued'])}")
    for ig in results["image_gen_queued"]:
        if "error" in ig:
            print(f"     [FAIL] {ig['job_id']}: {ig['error']}")
        else:
            print(f"     [OK] {ig['job_id']} -> Celery: {ig['celery_task_id']}")
            print(f"            {ig['product']} / {ig['niche']}")

    if all_ok:
        print("\n*** ALL SYSTEMS OPERATIONAL ***")
    else:
        print("\n*** Some tests failed - check above ***")

    db.close()
    return results


if __name__ == "__main__":
    main()

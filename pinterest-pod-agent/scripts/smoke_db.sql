BEGIN;

INSERT INTO pin_performance (
    title,
    description,
    content_prompt,
    keywords,
    impressions,
    clicks,
    saves,
    ctr,
    save_rate,
    engagement_rate
) VALUES (
    'test pin',
    'test description',
    'test prompt',
    '["dog mom", "custom shirt"]'::jsonb,
    1000,
    42,
    15,
    0.042,
    0.015,
    0.02
);

SELECT id, title, clicks, ctr
FROM pin_performance
WHERE title = 'test pin';

ROLLBACK;

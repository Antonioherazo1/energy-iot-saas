-- Fix timestamps stored in Bogota local time (UTC-5) instead of UTC.
-- ESP32 sends time-only timestamps in local time, which were combined
-- with the UTC date, resulting in timestamps 5 hours behind actual UTC time.
UPDATE telemetry
SET recorded_at = recorded_at + INTERVAL '5 hours'
WHERE recorded_at < '2026-06-05'::date;

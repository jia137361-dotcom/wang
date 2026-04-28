from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.automation import anti_detect
from app.workflows import warmup_flow


if __name__ == "__main__":
    anti_detect.apply_fingerprint_masking_placeholder()
    anti_detect.bypass_anti_scraping_checks_placeholder()
    anti_detect.simulate_sensitive_runtime()
    anti_result = anti_detect.AntiDetect(
        anti_detect.FingerprintConfig(profile_id="placeholder-profile", proxy_region="US")
    ).apply()
    assert anti_result.executed is False
    warmup_flow.run_account_warmup_placeholder("placeholder-account")
    warmup_result = warmup_flow.WarmupFlow().run("placeholder-account")
    assert warmup_result.executed is False
    print("sensitive_placeholders_ok")

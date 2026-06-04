from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env_example_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_env_example_keeps_external_processing_closed_by_default() -> None:
    values = _env_example_values()

    assert values["ALLOW_UNRESTRICTED_DEV_AUTH"] == "false"
    assert values["EXTERNAL_LLM_PROCESSING_ENABLED"] == "false"
    assert values["ALLOW_UNREDACTED_EXTERNAL_CLIENT_DATA"] == "false"
    assert values["AUDIT_PERSIST_PROMPT_BODIES"] == "false"
    assert values["REG_FEED_ENABLED"] == "false"


def test_env_example_requires_operator_secrets_for_real_use() -> None:
    values = _env_example_values()

    assert values["JWT_SHARED_SECRET"] == ""
    assert values["USER_EMAIL_ALLOWLIST"] == ""
    assert values["ANTHROPIC_API_KEY"] == ""

from app.config import tooling_settings
from app.errors import PROBLEM_MEDIA_TYPE
from app.main import create_app


def test_problem_schema_in_spec_with_problem_media_type() -> None:
    spec = create_app(tooling_settings()).openapi()
    assert "Problem" in spec["components"]["schemas"]
    live = spec["paths"]["/api/v1/health/live"]["get"]["responses"]
    assert PROBLEM_MEDIA_TYPE in live["4XX"]["content"]
    assert "application/json" not in live["4XX"]["content"]
    assert PROBLEM_MEDIA_TYPE in live["5XX"]["content"]
    # The spec is served from the API prefix and the docs are development-only.
    assert "/api/v1/openapi.json" not in spec["paths"]

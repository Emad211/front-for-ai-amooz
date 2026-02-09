import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_openapi_schema_generates_successfully(tmp_path):
    """Ensure OpenAPI schema generation completes without crashing.

    Warnings are acceptable as long as the schema is valid.
    """
    out_file = tmp_path / "openapi-schema.yml"
    call_command("spectacular", "--file", str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0

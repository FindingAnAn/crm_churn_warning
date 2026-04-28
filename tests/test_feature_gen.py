"""Unit tests for feature generation template engine."""

import pytest
from features.engineering.feature_gen.template_engine import (
    clear_cache,
    get_template,
    render_template,
)


@pytest.fixture(autouse=True)
def _clear_template_cache():
    """Ensure cache is empty before each test."""
    clear_cache()
    yield
    clear_cache()


def test_get_template_loads_from_disk():
    """Verify that get_template successfully loads the SQL file."""
    # This assumes 'lifetime_table' exists in the correctly placed database/sql folder
    content = get_template("lifetime_table")
    assert content, "Template content should not be empty."
    assert "data_static" in content or "CREATE TABLE" in content


def test_render_template_replaces_placeholders():
    """Verify placeholders like {schema} and {table_name} are correctly replaced."""
    # Usually lifetime_table has placeholders, we'll test the engine string replacement.
    
    # Let's mock the cache to inject a fake template for controlled testing
    from features.engineering.feature_gen.template_engine import _TEMPLATE_CACHE
    _TEMPLATE_CACHE["dummy_test"] = "SELECT * FROM {schema}.{table_name} WHERE id = '{id}'"
    
    rendered = render_template(
        "dummy_test", 
        schema="test_schema", 
        table_name="test_table", 
        id="123"
    )
    
    expected = "SELECT * FROM test_schema.test_table WHERE id = '123'"
    assert rendered == expected, f"Expected {expected}, got {rendered}"


def test_get_template_invalid_throws_error():
    """Verify unknown template name triggers ValueError."""
    with pytest.raises(ValueError, match="Unknown template: invalid_name"):
        get_template("invalid_name")

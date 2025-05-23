import click
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from schemathesis.cli.commands.run import validation
from schemathesis.core.validation import is_latin_1_encodable

from ..utils import SIMPLE_PATH


@pytest.mark.parametrize("value", ["//test", "//ÿ["])
def test_parse_schema_kind(value):
    with pytest.raises(click.UsageError):
        validation.validate_schema(value, None)


def test_validate_schema_path_without_base_url():
    with pytest.raises(click.UsageError):
        validation.validate_schema(SIMPLE_PATH, None)


@given(value=st.text().filter(lambda x: x.count(":") != 1))
@example(":")
@example("0:Ā")
@example("Ā:0")
@settings(deadline=None)
def test_validate_auth(value):
    with pytest.raises(click.BadParameter):
        validation.validate_auth(None, None, value)


def is_invalid_header(header):
    try:
        # We need to avoid generating known valid headers
        key, _ = header.split(":", maxsplit=1)
        return not (key.strip() and is_latin_1_encodable(key))
    except ValueError:
        return True


@given(value=st.lists(st.text().filter(is_invalid_header), min_size=1).map(tuple))
@example((":",))
@example(("0:Ā",))
@example(("Ā:0",))
@example((" :test",))
@settings(deadline=None)
def test_validate_header(value):
    with pytest.raises(click.BadParameter):
        validation.validate_headers(None, None, value)


def test_reraise_format_error():
    with pytest.raises(click.BadParameter, match="Expected KEY:VALUE format, received bla."):
        with validation.reraise_format_error("bla"):
            raise ValueError


@pytest.mark.parametrize(
    "value",
    ["+", "\\", "[", r"0EEE|[>:>\UEEEEEEEEEEEEEEEEEEEEEEEE>", "(?(8))"],
)
def test_validate_regex(value):
    with pytest.raises(click.BadParameter, match="Invalid regex: "):
        validation.validate_regex(None, None, (value,))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("On", True),
        ("F", False),
        ("/tmp/cert.pem", "/tmp/cert.pem"),
    ],
)
def test_convert_request_tls_verify(value, expected):
    assert validation.convert_boolean_string(None, None, value) == expected


@pytest.mark.parametrize(("value", "expected"), [("2", 2), ("auto", validation.get_workers_count())])
def test_convert_workers(value, expected):
    assert validation.convert_workers(None, None, value) == expected


@pytest.mark.parametrize("value", ["1", "1/g", "f/g"])
def test_validate_rate_limit_invalid(value):
    with pytest.raises(click.UsageError) as exc:
        validation.validate_rate_limit(None, None, value)
    assert (
        str(exc.value) == f"Invalid rate limit value: `{value}`. Should be in form `limit/interval`. "
        "Example: `10/m` for 10 requests per minute."
    )


def test_validate_rate_limit_valid():
    assert validation.validate_rate_limit(None, None, "10/m") == "10/m"


@pytest.mark.parametrize(
    ("input_codes", "output", "error"),
    [
        (["200", "404"], ["200", "404"], None),
        (["2xx", "4xx"], ["2xx", "4xx"], None),
        (["200", "2xx", "404", "4xx"], ["200", "2xx", "404", "4xx"], None),
        ([], [], None),
        (["200", "600"], None, "Invalid status code(s): 600"),
        (["2xx", "6xx"], None, "Invalid status code(s): 6xx"),
        (["2xx", "xxx"], None, "Invalid status code(s): xxx"),
        (["2xx", "999"], None, "Invalid status code(s): 999"),
        (["200", "abc"], None, "Invalid status code(s): abc"),
        (["200", "2bc"], None, "Invalid status code(s): 2bc"),
        (["200", "2Xc"], None, "Invalid status code(s): 2Xc"),
        (["200", "20"], None, "Invalid status code(s): 20"),
        (["200", "2xxx"], None, "Invalid status code(s): 2xxx"),
        (["200", "xx"], None, "Invalid status code(s): xx"),
    ],
)
def test_convert_status_codes(input_codes, output, error):
    if error:
        with pytest.raises(click.UsageError) as excinfo:
            validation.convert_status_codes(None, None, input_codes)
        assert error in str(excinfo.value)
    else:
        assert validation.convert_status_codes(None, None, input_codes) == output


def test_convert_status_codes_empty_input():
    assert validation.convert_status_codes(None, None, None) is None

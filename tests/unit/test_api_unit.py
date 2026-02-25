"""Tests for ESS-DIVE MCP Server."""

from essdive_mcp.main import (
    ESSDiveClient,
    get_api_key,
    parse_flmd_file,
    sanitize_tsv_field,
    _norm_header_key,
    _is_truthy,
    _build_tool_error_payload,
    _normalize_doi,
    doi_to_essdive_id,
    essdive_id_to_doi,
    search_ess_deepdive,
    get_ess_deepdive_dataset,
    get_ess_deepdive_file,
    _summarize_essdeepdive_file_response,
)
import pytest
import os
import requests
from unittest.mock import Mock, patch, AsyncMock


class TestGetApiKey:
    """Tests for the get_api_key helper function."""

    def test_get_api_key_from_parameter(self):
        """Test retrieving API key from parameter."""
        result = get_api_key("test_key_123")
        assert result == "test_key_123"

    def test_get_api_key_from_environment(self):
        """Test retrieving API key from environment variable."""
        with patch.dict(os.environ, {"ESSDIVE_API_TOKEN": "env_key_456"}):
            result = get_api_key(None)
            assert result == "env_key_456"

    def test_get_api_key_parameter_takes_precedence(self):
        """Test that parameter takes precedence over environment variable."""
        with patch.dict(os.environ, {"ESSDIVE_API_TOKEN": "env_key"}):
            result = get_api_key("param_key")
            assert result == "param_key"

    def test_get_api_key_missing_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="ESS-DIVE API key is required"):
                get_api_key(None)


class TestBooleanHelpers:
    """Tests for truthy helper parsing."""

    def test_is_truthy_true_values(self):
        """Truthy values are accepted case-insensitively."""
        assert _is_truthy("1")
        assert _is_truthy("true")
        assert _is_truthy("YES")
        assert _is_truthy(" On ")

    def test_is_truthy_false_values(self):
        """Falsy/empty values are rejected."""
        assert not _is_truthy("0")
        assert not _is_truthy("false")
        assert not _is_truthy("")
        assert not _is_truthy(None)


class TestToolErrorPayload:
    """Tests for standard MCP error payload generation."""

    def test_payload_includes_http_details_for_requests_error(self):
        """HTTP status and URL should be exposed for requests HTTP errors."""
        response = Mock()
        response.status_code = 404
        response.url = "https://example.org/test"
        response.text = '{"detail":"not found"}'
        exc = requests.HTTPError("404 Client Error")
        exc.response = response

        payload = _build_tool_error_payload("test-op", exc, verbose=False)

        assert payload["error"]["operation"] == "test-op"
        assert payload["error"]["type"] == "HTTPError"
        assert payload["error"]["http"]["status_code"] == 404
        assert payload["error"]["http"]["url"] == "https://example.org/test"
        assert "hint" in payload["error"]
        assert "traceback" not in payload["error"]

    def test_payload_includes_traceback_in_verbose_mode(self):
        """Traceback should be included when verbose mode is enabled."""
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            payload = _build_tool_error_payload(
                "verbose-op", exc, verbose=True)

        assert payload["error"]["operation"] == "verbose-op"
        assert payload["error"]["type"] == "RuntimeError"
        assert "traceback" in payload["error"]
        assert "RuntimeError: boom" in payload["error"]["traceback"]


class TestSanitizeTsvField:
    """Tests for the sanitize_tsv_field helper function."""

    def test_sanitize_newlines(self):
        """Test that newlines are replaced with spaces."""
        result = sanitize_tsv_field("line1\nline2")
        assert result == "line1 line2"

    def test_sanitize_carriage_returns(self):
        """Test that carriage returns are replaced with spaces."""
        result = sanitize_tsv_field("line1\rline2")
        assert result == "line1 line2"

    def test_sanitize_tabs(self):
        """Test that tabs are replaced with spaces."""
        result = sanitize_tsv_field("col1\tcol2")
        assert result == "col1 col2"

    def test_sanitize_multiple_whitespace(self):
        """Test that multiple whitespace is collapsed to single space."""
        result = sanitize_tsv_field("text   with   spaces")
        assert result == "text with spaces"

    def test_sanitize_strips_leading_trailing(self):
        """Test that leading and trailing whitespace is stripped."""
        result = sanitize_tsv_field("  text  ")
        assert result == "text"

    def test_sanitize_none_value(self):
        """Test that None is converted to empty string."""
        result = sanitize_tsv_field(None)
        assert result == ""

    def test_sanitize_numeric_value(self):
        """Test that numeric values are converted to string."""
        result = sanitize_tsv_field(123)
        assert result == "123"


class TestNormHeaderKey:
    """Tests for the _norm_header_key helper function."""

    def test_norm_header_lowercase(self):
        """Test that header is converted to lowercase."""
        result = _norm_header_key("FileName")
        assert result == "filename"

    def test_norm_header_removes_spaces(self):
        """Test that spaces are removed."""
        result = _norm_header_key("File Name")
        assert result == "filename"

    def test_norm_header_removes_punctuation(self):
        """Test that punctuation is removed."""
        result = _norm_header_key("File-Description")
        assert result == "filedescription"

    def test_norm_header_removes_underscores(self):
        """Test that underscores are removed."""
        result = _norm_header_key("file_name")
        assert result == "filename"

    def test_norm_header_preserves_alphanumeric(self):
        """Test that alphanumeric characters are preserved."""
        result = _norm_header_key("File123Name456")
        assert result == "file123name456"


class TestParseFlmdFile:
    """Tests for the parse_flmd_file function."""

    def test_parse_flmd_basic(self):
        """Test basic FLMD file parsing."""
        content = "filename,description\nfile1.csv,First data file\nfile2.txt,Second data file"
        result = parse_flmd_file(content)

        assert len(result) == 2
        assert result["file1.csv"] == "First data file"
        assert result["file2.txt"] == "Second data file"

    def test_parse_flmd_case_insensitive_headers(self):
        """Test that FLMD parsing handles case-insensitive headers."""
        content = "FileName,File Description\nfile1.csv,First data file"
        result = parse_flmd_file(content)

        assert result["file1.csv"] == "First data file"

    def test_parse_flmd_alternative_column_names(self):
        """Test that FLMD parsing accepts alternative column names."""
        content = "file_name,description\nfile1.csv,First data file"
        result = parse_flmd_file(content)

        assert result["file1.csv"] == "First data file"

    def test_parse_flmd_missing_columns(self):
        """Test that FLMD parsing handles missing required columns."""
        content = "name,other_column\nfile1.csv,Some value"
        result = parse_flmd_file(content)

        # Should return empty dict if required columns are missing
        assert len(result) == 0

    def test_parse_flmd_empty_content(self):
        """Test that FLMD parsing handles empty content."""
        content = ""
        result = parse_flmd_file(content)

        assert result == {}

    def test_parse_flmd_sanitizes_descriptions(self):
        """Test that descriptions are sanitized."""
        content = "filename,description\nfile1.csv,Line1\nLine2"
        result = parse_flmd_file(content)

        assert "file1.csv" in result
        # Newlines should be replaced with spaces
        assert "\n" not in result["file1.csv"]

    def test_parse_flmd_skips_empty_rows(self):
        """Test that rows with empty filename or description are skipped."""
        content = "filename,description\nfile1.csv,Description 1\n,Description 2\nfile3.csv,"
        result = parse_flmd_file(content)

        assert len(result) == 1
        assert "file1.csv" in result

    def test_parse_flmd_invalid_content_raises_value_error(self):
        """Test that malformed input raises a clear parsing error."""
        with pytest.raises(ValueError, match="Invalid FLMD CSV content"):
            parse_flmd_file(123)  # type: ignore[arg-type]


class TestESSDiveClient:
    """Tests for the ESSDiveClient class."""

    def test_client_initialization(self):
        """Test ESSDiveClient initialization."""
        client = ESSDiveClient(api_token="test_token")

        assert client.api_token == "test_token"
        assert client.headers["Authorization"] == "Bearer test_token"

    def test_client_initialization_no_token(self):
        """Test ESSDiveClient initialization without token."""
        client = ESSDiveClient(api_token=None)

        assert client.api_token is None
        assert "Authorization" not in client.headers

    def test_get_headers(self):
        """Test _get_headers method."""
        client = ESSDiveClient(api_token="test_token")
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_search_datasets(self):
        """Test search_datasets method."""
        client = ESSDiveClient(api_token="test_token")

        mock_response = {
            "result": [
                {
                    "id": "ds1",
                    "dataset": {
                        "name": "Dataset 1",
                        "datePublished": "2024-01-01"
                    }
                }
            ],
            "total": 1
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = await client.search_datasets(text="test")

            assert result["total"] == 1
            assert result["result"][0]["id"] == "ds1"

    @pytest.mark.asyncio
    async def test_get_dataset(self):
        """Test get_dataset method."""
        client = ESSDiveClient(api_token="test_token")

        mock_response = {
            "id": "ds1",
            "dataset": {
                "name": "Dataset 1",
                "description": "A test dataset"
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = await client.get_dataset("ds1")

            assert result["id"] == "ds1"
            assert result["dataset"]["name"] == "Dataset 1"

    @pytest.mark.asyncio
    async def test_get_dataset_status(self):
        """Test get_dataset_status method."""
        client = ESSDiveClient(api_token="test_token")

        mock_response = {
            "status": "published",
            "doi": "10.1234/test"
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = await client.get_dataset_status("ds1")

            assert result["status"] == "published"

    @pytest.mark.asyncio
    async def test_get_dataset_permissions(self):
        """Test get_dataset_permissions method."""
        client = ESSDiveClient(api_token="test_token")

        mock_response = {
            "permissions": [
                {"user": "user1", "access": "read"}
            ]
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = await client.get_dataset_permissions("ds1")

            assert "permissions" in result


class TestFormatResults:
    """Tests for the format_results method."""

    def test_format_results_raw(self):
        """Test raw format returns unchanged results."""
        client = ESSDiveClient()

        results = {
            "result": [{"id": "ds1"}],
            "total": 1
        }

        formatted = client.format_results(results, "raw")
        assert formatted == results

    def test_format_results_summary(self):
        """Test summary format."""
        client = ESSDiveClient()

        results = {
            "result": [
                {
                    "id": "ds1",
                    "dataset": {"name": "Dataset 1", "datePublished": "2024-01-01"},
                    "viewUrl": "https://example.com/ds1"
                }
            ],
            "total": 1
        }

        formatted = client.format_results(results, "summary")

        assert isinstance(formatted, str)
        assert "Dataset 1" in formatted
        assert "ds1" in formatted

    def test_format_results_no_results(self):
        """Test formatting when no results are found."""
        client = ESSDiveClient()

        results = {}

        formatted = client.format_results(results, "summary")

        assert "No results found" in formatted


class TestNormalizeDoi:
    """Tests for the _normalize_doi helper function."""

    def test_normalize_doi_with_doi_prefix(self):
        """Test normalizing a DOI that already has the doi: prefix."""
        result = _normalize_doi("doi:10.1234/example")
        assert result == "doi:10.1234/example"

    def test_normalize_doi_without_prefix(self):
        """Test normalizing a DOI without the doi: prefix."""
        result = _normalize_doi("10.1234/example")
        assert result == "doi:10.1234/example"

    def test_normalize_doi_with_https_url(self):
        """Test normalizing a DOI with https://doi.org/ URL."""
        result = _normalize_doi("https://doi.org/10.1234/example")
        assert result == "doi:10.1234/example"

    def test_normalize_doi_with_http_url(self):
        """Test normalizing a DOI with http://doi.org/ URL."""
        result = _normalize_doi("http://doi.org/10.1234/example")
        assert result == "doi:10.1234/example"

    def test_normalize_doi_with_doi_org_prefix(self):
        """Test normalizing a DOI with doi.org/ prefix."""
        result = _normalize_doi("doi.org/10.1234/example")
        assert result == "doi:10.1234/example"

    def test_normalize_doi_strips_whitespace(self):
        """Test that whitespace is stripped."""
        result = _normalize_doi("  10.1234/example  ")
        assert result == "doi:10.1234/example"

    def test_normalize_doi_complex_example(self):
        """Test normalizing a complex real DOI."""
        result = _normalize_doi("https://doi.org/10.15485/1234567")
        assert result == "doi:10.15485/1234567"


class TestDoiConversion:
    """Tests for DOI/ESS-DIVE ID conversion functions."""

    def test_doi_to_essdive_id_success(self):
        """Test successful DOI to ESS-DIVE ID conversion."""
        mock_response = {
            "id": "ess-dive-test-id-12345",
            "dataset": {
                "name": "Test Dataset",
                "doi": "10.1234/test"
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = doi_to_essdive_id("10.1234/test")
            assert result == "ess-dive-test-id-12345"

    def test_doi_to_essdive_id_with_doi_prefix(self):
        """Test DOI conversion with doi: prefix."""
        mock_response = {
            "id": "ess-dive-test-id-67890",
            "dataset": {
                "name": "Test Dataset",
                "doi": "doi:10.1234/test2"
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = doi_to_essdive_id("doi:10.1234/test2")
            assert result == "ess-dive-test-id-67890"

    def test_doi_to_essdive_id_missing_id(self):
        """Test DOI conversion when response has no ID."""
        mock_response = {
            "dataset": {"name": "Test Dataset"}
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(ValueError, match="No dataset ID found"):
                doi_to_essdive_id("10.1234/test")

    def test_essdive_id_to_doi_success(self):
        """Test successful ESS-DIVE ID to DOI conversion."""
        mock_response = {
            "id": "ess-dive-test-id-12345",
            "dataset": {
                "name": "Test Dataset",
                "doi": "10.1234/test"
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = essdive_id_to_doi("ess-dive-test-id-12345")
            assert result == "doi:10.1234/test"

    def test_essdive_id_to_doi_with_url_format(self):
        """Test ESS-DIVE ID to DOI conversion when DOI is in URL format."""
        mock_response = {
            "id": "ess-dive-test-id-67890",
            "dataset": {
                "name": "Test Dataset",
                "doi": "https://doi.org/10.1234/test2"
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = essdive_id_to_doi("ess-dive-test-id-67890")
            assert result == "doi:10.1234/test2"

    def test_essdive_id_to_doi_uses_dataset_at_id(self):
        """Test ESS-DIVE ID to DOI conversion using dataset @id field."""
        mock_response = {
            "id": "ess-dive-test-id-at-id",
            "dataset": {
                "name": "Test Dataset",
                "@id": "doi:10.1234/test3",
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = essdive_id_to_doi("ess-dive-test-id-at-id")
            assert result == "doi:10.1234/test3"

    def test_essdive_id_to_doi_prefers_dataset_at_id_over_doi(self):
        """Test @id is preferred when both @id and doi fields are present."""
        mock_response = {
            "id": "ess-dive-test-id-both",
            "dataset": {
                "name": "Test Dataset",
                "@id": "doi:10.1234/preferred",
                "doi": "10.1234/fallback",
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = essdive_id_to_doi("ess-dive-test-id-both")
            assert result == "doi:10.1234/preferred"

    def test_essdive_id_to_doi_missing_doi(self):
        """Test ESS-DIVE ID to DOI conversion when response has no DOI."""
        mock_response = {
            "id": "ess-dive-test-id-12345",
            "dataset": {
                "name": "Test Dataset"
            }
        }

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(ValueError, match="No DOI found"):
                essdive_id_to_doi("ess-dive-test-id-12345")


class TestMalformedApiResponses:
    """Tests for malformed payloads/responses from ESS-DIVE/ESS-DeepDive."""

    @pytest.mark.asyncio
    async def test_get_dataset_malformed_json_raises_value_error(self):
        """Invalid JSON payloads from ESS-DIVE should raise a parse error."""
        client = ESSDiveClient(api_token="test_token")
        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock()
        mock_response_obj.json.side_effect = ValueError("malformed JSON")

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(ValueError, match="malformed JSON"):
                await client.get_dataset("ds1")

    def test_doi_to_essdive_id_malformed_response_raises_value_error(self):
        """Non-dict ESS-DIVE responses should be surfaced as conversion failures."""
        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock()
        mock_response_obj.json.return_value = ["unexpected", "list"]

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(ValueError, match="Failed to convert DOI"):
                doi_to_essdive_id("10.1234/test")

    def test_essdive_id_to_doi_malformed_dataset_type_raises_value_error(self):
        """Malformed dataset payloads should not be silently accepted."""
        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock()
        mock_response_obj.json.return_value = {
            "id": "ess-dive-test-id",
            "dataset": ["not", "a", "dict"],
        }

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(ValueError, match="Failed to convert ESS-DIVE ID"):
                essdive_id_to_doi("ess-dive-test-id")

    def test_search_ess_deepdive_malformed_json_raises_value_error(self):
        """Malformed ESS-DeepDive JSON responses should raise parsing errors."""
        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.raise_for_status = Mock()
            mock_response_obj.json.side_effect = ValueError(
                "invalid deepdive JSON")
            mock_get.return_value = mock_response_obj

            with pytest.raises(ValueError, match="invalid deepdive JSON"):
                search_ess_deepdive(field_name="temperature")

    def test_get_ess_deepdive_dataset_http_error_is_propagated(self):
        """HTTP errors from malformed ESS-DeepDive file lookups should propagate."""
        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.raise_for_status.side_effect = requests.HTTPError(
                "404 not found"
            )
            mock_get.return_value = mock_response_obj

            with pytest.raises(requests.HTTPError, match="404 not found"):
                get_ess_deepdive_dataset("doi:10.1234/test", "missing.csv")


class TestSearchEssDeepDive:
    """Tests for the search_ess_deepdive function."""

    def test_search_ess_deepdive_by_field_name(self):
        """Test searching ESS-DeepDive by field name."""
        mock_response = {
            "results": [
                {
                    "fieldName": "temperature",
                    "fieldDefinition": "Temperature measurement",
                    "recordCount": 1000,
                    "doi": "10.1234/test"
                }
            ],
            "pageCount": 1,
            "rowStart": 1,
            "pageSize": 25
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = search_ess_deepdive(field_name="temperature")

            assert result["pageCount"] == 1
            assert len(result["results"]) == 1
            assert result["results"][0]["fieldName"] == "temperature"
            mock_get.assert_called_once()

    def test_search_ess_deepdive_with_text_value(self):
        """Test searching ESS-DeepDive by text field value."""
        mock_response = {
            "results": [
                {
                    "fieldValueText": "soil",
                    "fieldName": "sample_type",
                    "recordCount": 500
                }
            ],
            "pageCount": 1,
            "rowStart": 1,
            "pageSize": 25
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = search_ess_deepdive(field_value_text="soil")

            assert result["pageCount"] == 1
            assert result["results"][0]["fieldValueText"] == "soil"

    def test_search_ess_deepdive_with_pagination(self):
        """Test that pagination parameters are included in request."""
        mock_response = {
            "results": [],
            "pageCount": 1,
            "rowStart": 50,
            "pageSize": 10
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = search_ess_deepdive(row_start=50, page_size=10)

            # Check that the call included pagination parameters
            call_args = mock_get.call_args
            params = call_args[1].get("params", {})
            assert params["rowStart"] == 50
            assert params["pageSize"] == 10

    def test_search_ess_deepdive_enforces_max_page_size(self):
        """Test that page_size is limited to 100."""
        mock_response = {
            "results": [],
            "pageCount": 1,
            "rowStart": 1,
            "pageSize": 100
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            # Request with page_size > 100
            result = search_ess_deepdive(page_size=200)

            # Check that page_size was capped at 100
            call_args = mock_get.call_args
            params = call_args[1].get("params", {})
            assert params["pageSize"] == 100

    def test_search_ess_deepdive_with_doi_filter(self):
        """Test searching with DOI filter."""
        mock_response = {
            "results": [
                {
                    "fieldName": "temperature",
                    "doi": "10.1234/test"
                }
            ],
            "pageCount": 1
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = search_ess_deepdive(doi=["10.1234/test", "10.5678/test"])

            call_args = mock_get.call_args
            params = call_args[1].get("params", {})
            assert params["doi"] == ["10.1234/test", "10.5678/test"]

    def test_search_ess_deepdive_enforces_max_doi_count(self):
        """Test that DOI list is limited to 100 items."""
        mock_response = {
            "results": [],
            "pageCount": 1
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            # Create a list of 150 DOIs
            dois = [f"10.{i}/test" for i in range(150)]

            result = search_ess_deepdive(doi=dois)

            # Check that only 100 DOIs were sent
            call_args = mock_get.call_args
            params = call_args[1].get("params", {})
            assert len(params["doi"]) == 100


class TestGetEssDeepDiveDataset:
    """Tests for the get_ess_deepdive_dataset function."""

    def test_get_ess_deepdive_dataset_success(self):
        """Test successfully retrieving an ESS-DeepDive dataset."""
        mock_response = {
            "doi": "doi:10.1234/test",
            "file_path": "dataset.zip/data.csv",
            "file_name": "data.csv",
            "fields": [
                {
                    "fieldName": "temperature",
                    "fieldDefinition": "Temperature measurement",
                    "dataType": "numeric"
                }
            ],
            "recordCount": 1000
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = get_ess_deepdive_dataset(
                "10.1234/test", "dataset.zip/data.csv")

            assert result["doi"] == "doi:10.1234/test"
            assert result["file_path"] == "dataset.zip/data.csv"
            assert len(result["fields"]) == 1

    def test_get_ess_deepdive_dataset_normalizes_doi(self):
        """Test that DOI is normalized to include doi: prefix."""
        mock_response = {
            "doi": "doi:10.1234/test",
            "fields": []
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = get_ess_deepdive_dataset("10.1234/test", "data.csv")

            # Check that the URL was constructed with doi: prefix
            call_args = mock_get.call_args
            url = call_args[0][0]
            assert "doi:10.1234/test" in url

    def test_get_ess_deepdive_dataset_with_doi_prefix_already(self):
        """Test when DOI already has doi: prefix."""
        mock_response = {
            "doi": "doi:10.1234/test",
            "fields": []
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = get_ess_deepdive_dataset("doi:10.1234/test", "data.csv")

            call_args = mock_get.call_args
            url = call_args[0][0]
            # Should not double the prefix
            assert url.count("doi:") == 1


class TestGetEssDeepDiveFile:
    """Tests for the get_ess_deepdive_file function."""

    def test_get_ess_deepdive_file_success(self):
        """Test successfully retrieving an ESS-DeepDive file."""
        mock_response = {
            "doi": "doi:10.1234/test",
            "file_path": "dataset.zip/data.csv",
            "file_name": "data.csv",
            "fields": [
                {
                    "fieldName": "temperature",
                    "fieldDefinition": "Temperature measurement",
                    "dataType": "numeric"
                }
            ],
            "data_download": {
                "contentSize": 1024000,
                "encoding_format": "text/csv",
                "contentURL": "https://example.com/data.csv"
            }
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            result = get_ess_deepdive_file(
                "10.1234/test", "dataset.zip/data.csv")

            assert result["file_name"] == "data.csv"
            assert "data_download" in result
            assert result["data_download"]["contentSize"] == 1024000

    def test_get_ess_deepdive_file_is_alias_for_dataset(self):
        """Test that get_ess_deepdive_file returns same data as get_ess_deepdive_dataset."""
        mock_response = {
            "doi": "doi:10.1234/test",
            "fields": [{"fieldName": "test"}]
        }

        with patch("essdive_mcp.main.requests.get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_get.return_value = mock_response_obj

            # Both functions should call the same API endpoint
            result1 = get_ess_deepdive_file("10.1234/test", "data.csv")
            result2 = get_ess_deepdive_dataset("10.1234/test", "data.csv")

            assert result1 == result2
            # Should have been called twice (once for each function)
            assert mock_get.call_count == 2


class TestEssDeepDiveFileSummary:
    """Tests for normalization of ESS-DeepDive file summary fields."""

    def test_summary_uses_current_api_keys(self):
        """Summary should map current ESS-DeepDive response keys correctly."""
        response = {
            "doi": "doi:10.1234/test",
            "data_file": "dataset.csv",
            "fields": [{"fieldName": "temperature"}],
            "data_download": {
                "contentSize": 1000,
                "encodingFormat": "text/csv",
                "contentUrl": "https://example.org/dataset.csv",
            },
        }

        summary = _summarize_essdeepdive_file_response(response)

        assert summary["doi"] == "doi:10.1234/test"
        assert summary["file_name"] == "dataset.csv"
        assert summary["file_path"] == "dataset.csv"
        assert summary["total_fields"] == 1
        assert summary["field_names"] == ["temperature"]
        assert summary["download_info"]["encoding_format"] == "text/csv"
        assert summary["download_info"]["content_url"] == "https://example.org/dataset.csv"

    def test_summary_supports_legacy_fallback_keys(self):
        """Summary should still support legacy key names."""
        response = {
            "doi": "doi:10.1234/test",
            "file_name": "legacy.csv",
            "file_path": "legacy/path.csv",
            "data_download": {
                "contentSize": 1000,
                "encoding_format": "text/csv",
                "contentURL": "https://example.org/legacy.csv",
            },
        }

        summary = _summarize_essdeepdive_file_response(response)

        assert summary["file_name"] == "legacy.csv"
        assert summary["file_path"] == "legacy/path.csv"
        assert summary["download_info"]["encoding_format"] == "text/csv"
        assert summary["download_info"]["content_url"] == "https://example.org/legacy.csv"


def test_reality():
    """Basic sanity check that tests are working."""
    assert 1 == 1

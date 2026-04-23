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
    _load_project_portals,
    search_project_portals,
    _dataset_matches_local_filters,
    _apply_local_dataset_filters,
    _default_dataset_search_is_public,
    _resolve_startup_api_token,
    PaginationStateStore,
)
import pytest
import os
import requests
import httpx
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

    def test_get_api_key_missing_returns_none(self):
        """Missing token config should be allowed for anonymous public access."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_api_key(None) is None

    def test_resolve_startup_api_token_warns_and_falls_back_on_bad_token_file(
        self, caplog: pytest.LogCaptureFixture
    ):
        """Unreadable token files should warn and fall back to anonymous mode."""
        with caplog.at_level("WARNING", logger="essdive_mcp"):
            resolved = _resolve_startup_api_token(token_file="/tmp/definitely-missing")

        assert resolved is None
        assert "Could not read ESS-DIVE token file" in caplog.text
        assert "Starting without ESS-DIVE auth" in caplog.text


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


class TestDatasetSearchVisibilityDefaults:
    """Tests for default public/private search visibility behavior."""

    def test_anonymous_search_defaults_to_public_only(self):
        """Anonymous search should keep the existing public-only behavior."""
        assert _default_dataset_search_is_public(None) is True

    def test_authenticated_search_allows_private_matches(self):
        """Authenticated search should not force the API back to public-only."""
        assert _default_dataset_search_is_public("token-123") is None


class TestPaginationStateStore:
    """Tests for server-side pagination state used by next/previous page tools."""

    def test_search_followup_reuses_stored_filters_and_next_cursor(self):
        """Next-search-page should reuse the most recent search context."""
        store = PaginationStateStore()

        store.save_search(
            session_id="session-a",
            search_kwargs={
                "text": "soil carbon",
                "sort": "name:asc",
                "page_size": 2,
                "cursor": None,
                "row_start": 1,
            },
            local_filters={"funder": ["DOE"]},
            format_type="summary",
            result={"nextCursor": "next-cursor-123", "previousCursor": None},
        )

        search_kwargs, local_filters, format_type = store.get_search_followup(
            "session-a", "next")

        assert search_kwargs == {
            "text": "soil carbon",
            "sort": "name:asc",
            "page_size": None,
            "cursor": "next-cursor-123",
            "row_start": None,
        }
        assert local_filters == {"funder": ["DOE"]}
        assert format_type == "summary"

    def test_search_followup_allows_format_override(self):
        """Follow-up search tools may override the stored output format."""
        store = PaginationStateStore()
        store.save_search(
            session_id="session-a",
            search_kwargs={"text": "soil carbon"},
            local_filters={},
            format_type="summary",
            result={"nextCursor": "next-cursor-123", "previousCursor": None},
        )

        _, _, format_type = store.get_search_followup(
            "session-a", "next", format_override="raw")

        assert format_type == "raw"

    def test_search_followup_requires_existing_state(self):
        """Paging without a prior search should raise a clear error."""
        store = PaginationStateStore()

        with pytest.raises(ValueError, match="No prior dataset search"):
            store.get_search_followup("session-a", "next")

    def test_search_followup_requires_requested_direction_cursor(self):
        """Paging should fail cleanly when no next/previous cursor exists."""
        store = PaginationStateStore()
        store.save_search(
            session_id="session-a",
            search_kwargs={"text": "soil carbon"},
            local_filters={},
            format_type="summary",
            result={"nextCursor": None, "previousCursor": None},
        )

        with pytest.raises(ValueError, match="No next page is available"):
            store.get_search_followup("session-a", "next")

    def test_search_followup_is_scoped_per_session(self):
        """Pagination state should not leak across sessions."""
        store = PaginationStateStore()
        store.save_search(
            session_id="session-a",
            search_kwargs={"text": "soil carbon"},
            local_filters={},
            format_type="summary",
            result={"nextCursor": "next-a", "previousCursor": None},
        )
        store.save_search(
            session_id="session-b",
            search_kwargs={"text": "wildfire"},
            local_filters={},
            format_type="detailed",
            result={"nextCursor": "next-b", "previousCursor": None},
        )

        kwargs_a, _, format_a = store.get_search_followup("session-a", "next")
        kwargs_b, _, format_b = store.get_search_followup("session-b", "next")

        assert kwargs_a["cursor"] == "next-a"
        assert kwargs_b["cursor"] == "next-b"
        assert format_a == "summary"
        assert format_b == "detailed"

    def test_versions_followup_reuses_identifier_and_cursor(self):
        """Next/previous version-page tools should reuse the last versions request."""
        store = PaginationStateStore()
        store.save_versions(
            session_id="session-a",
            identifier="doi:10.1234/example",
            format_type="detailed",
            result={"nextCursor": "next-version-cursor", "previousCursor": None},
        )

        identifier, cursor, format_type = store.get_versions_followup(
            "session-a", "next")

        assert identifier == "doi:10.1234/example"
        assert cursor == "next-version-cursor"
        assert format_type == "detailed"

    def test_versions_followup_requires_existing_state(self):
        """Paging versions without a prior request should raise a clear error."""
        store = PaginationStateStore()

        with pytest.raises(ValueError, match="No prior dataset-version request"):
            store.get_versions_followup("session-a", "next")

    def test_versions_followup_is_scoped_per_session(self):
        """Version pagination state should not leak across sessions."""
        store = PaginationStateStore()
        store.save_versions(
            session_id="session-a",
            identifier="doi:10.1234/example-a",
            format_type="summary",
            result={"nextCursor": "next-a", "previousCursor": None},
        )
        store.save_versions(
            session_id="session-b",
            identifier="doi:10.1234/example-b",
            format_type="raw",
            result={"nextCursor": "next-b", "previousCursor": None},
        )

        identifier_a, cursor_a, format_a = store.get_versions_followup(
            "session-a", "next")
        identifier_b, cursor_b, format_b = store.get_versions_followup(
            "session-b", "next")

        assert identifier_a == "doi:10.1234/example-a"
        assert cursor_a == "next-a"
        assert format_a == "summary"
        assert identifier_b == "doi:10.1234/example-b"
        assert cursor_b == "next-b"
        assert format_b == "raw"


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


class TestProjectPortalReferences:
    """Tests for shared ESS-DIVE project portal references."""

    def test_load_project_portals(self):
        """Project portal YAML should load a non-empty project list."""
        portals = _load_project_portals()

        assert isinstance(portals, list)
        assert len(portals) >= 5
        assert any(item["acronym"] == "CHESS" for item in portals)

    def test_search_project_portals_exact_acronym(self):
        """Exact acronym lookup should find the matching portal."""
        result = search_project_portals("CHESS", limit=5)

        assert result["count"] >= 1
        first = result["results"][0]
        assert first["acronym"] == "CHESS"
        assert "Colorado Headwaters Ecological Spectroscopy Study" in first["name"]
        assert "ecosis.org" in first["url"]

    def test_search_project_portals_alias(self):
        """Alias lookup should resolve portal entries."""
        result = search_project_portals("East River", limit=5)

        assert result["count"] >= 1
        assert any("East River" in item["name"] or "East River" in " ".join(
            item["aliases"]) for item in result["results"])

    def test_search_project_portals_without_query_lists_entries(self):
        """Listing without a query should return a bounded set of entries."""
        result = search_project_portals(limit=3)

        assert result["query"] is None
        assert result["count"] >= 3
        assert len(result["results"]) == 3


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
    async def test_search_datasets_includes_temporal_and_bbox_params(self):
        """Temporal coverage and bbox filters should be forwarded to the API."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"result": [], "total": 0}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.search_datasets(
                text="snow",
                begin_date="2020",
                end_date="2021-06",
                bbox=[34.0, -119.0, 35.0, -117.0],
            )

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params["beginDate"] == "2020"
            assert params["endDate"] == "2021-06"
            assert params["bbox"] == "34.0,-119.0,35.0,-117.0"

    @pytest.mark.asyncio
    async def test_search_datasets_includes_sort_param(self):
        """Sort directives should be forwarded to the API."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"result": [], "total": 0}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.search_datasets(
                text="soil carbon",
                sort="dateUploaded:desc,authorLastName:asc",
            )

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params["sort"] == "dateUploaded:desc,authorLastName:asc"

    @pytest.mark.asyncio
    async def test_search_datasets_cursor_omits_legacy_row_start_and_default_page_size(self):
        """Cursor follow-up search requests should not force rowStart or pageSize defaults."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"result": [], "total": 0}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.search_datasets(
                text="soil carbon",
                cursor="cursor-123",
                sort="name:asc",
            )

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params == {"cursor": "cursor-123", "text": "soil carbon", "sort": "name:asc"}

    @pytest.mark.asyncio
    async def test_search_datasets_cursor_includes_explicit_matching_page_size(self):
        """Cursor follow-up requests may include pageSize only when explicitly supplied."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"result": [], "total": 0}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.search_datasets(
                text="soil carbon",
                cursor="cursor-123",
                page_size=10,
            )

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params["cursor"] == "cursor-123"
            assert params["pageSize"] == 10
            assert "rowStart" not in params

    @pytest.mark.asyncio
    async def test_search_datasets_cursor_followup_flow_uses_returned_next_cursor(self):
        """A first page's nextCursor should work unchanged for a follow-up page request."""
        client = ESSDiveClient(api_token="test_token")

        first_response = {
            "total": 3,
            "pageSize": 2,
            "nextCursor": "next-cursor-123",
            "previousCursor": None,
            "query": {"text": "soil carbon", "sort": "name:asc"},
            "result": [
                {"id": "ds1", "dataset": {"name": "Dataset 1"}},
                {"id": "ds2", "dataset": {"name": "Dataset 2"}},
            ],
        }
        second_response = {
            "total": 3,
            "pageSize": 2,
            "nextCursor": None,
            "previousCursor": "prev-cursor-123",
            "query": {"text": "soil carbon", "sort": "name:asc"},
            "result": [
                {"id": "ds3", "dataset": {"name": "Dataset 3"}},
            ],
        }

        first_response_obj = Mock()
        first_response_obj.json.return_value = first_response
        first_response_obj.raise_for_status = Mock()

        second_response_obj = Mock()
        second_response_obj.json.return_value = second_response
        second_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=[first_response_obj, second_response_obj]
            )
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            first_page = await client.search_datasets(
                text="soil carbon",
                page_size=2,
                sort="name:asc",
            )
            second_page = await client.search_datasets(
                text="soil carbon",
                sort="name:asc",
                cursor=first_page["nextCursor"],
            )

            assert first_page["nextCursor"] == "next-cursor-123"
            assert second_page["result"][0]["id"] == "ds3"
            assert second_page["previousCursor"] == "prev-cursor-123"

            first_params = mock_client_instance.get.call_args_list[0].kwargs["params"]
            second_params = mock_client_instance.get.call_args_list[1].kwargs["params"]
            assert first_params["pageSize"] == 2
            assert first_params["text"] == "soil carbon"
            assert first_params["sort"] == "name:asc"
            assert second_params == {
                "cursor": "next-cursor-123",
                "text": "soil carbon",
                "sort": "name:asc",
            }

    @pytest.mark.asyncio
    async def test_search_datasets_accepts_string_bbox(self):
        """bbox may be provided in the API's comma-delimited string format."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"result": [], "total": 0}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.search_datasets(
                bbox="34.0,-119.0,35.0,-117.0",
            )

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params["bbox"] == "34.0,-119.0,35.0,-117.0"

    @pytest.mark.asyncio
    async def test_search_datasets_includes_point_search_params(self):
        """Point-based search params should be forwarded together."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"result": [], "total": 0}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.search_datasets(
                lat=37.7749,
                lon=-122.4194,
                radius=5000,
            )

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params["lat"] == 37.7749
            assert params["lon"] == -122.4194
            assert params["radius"] == 5000

    @pytest.mark.asyncio
    async def test_search_datasets_treats_no_matches_404_as_empty_results(self):
        """ESS-DIVE returns 404 for no-match searches; this should not raise."""
        client = ESSDiveClient(api_token="test_token")

        request = httpx.Request("GET", "https://api.ess-dive.lbl.gov/packages")
        response = httpx.Response(
            404,
            request=request,
            json={"detail": "No datasets were found."},
        )
        mock_response_obj = Mock()
        mock_response_obj.status_code = 404
        mock_response_obj.json.return_value = {
            "detail": "No datasets were found."}
        mock_response_obj.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 not found",
            request=request,
            response=response,
        )

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            result = await client.search_datasets(
                lat=37.7749,
                lon=-122.4194,
                radius=5000,
                is_public=True,
                page_size=3,
            )

            assert result["total"] == 0
            assert result["result"] == []
            assert result["pageSize"] == 3
            assert result["query"]["lat"] == 37.7749
            assert result["query"]["lon"] == -122.4194
            assert result["query"]["radius"] == 5000
            assert result["query"]["isPublic"] is True

    @pytest.mark.asyncio
    async def test_search_datasets_requires_complete_point_search_params(self):
        """Point-based search requires lat, lon, and radius together."""
        client = ESSDiveClient(api_token="test_token")

        with pytest.raises(
            ValueError,
            match="lat, lon, and radius must all be provided together",
        ):
            await client.search_datasets(lat=37.7749, radius=5000)

    @pytest.mark.asyncio
    async def test_search_datasets_requires_positive_radius(self):
        """Point-based search radius must be positive."""
        client = ESSDiveClient(api_token="test_token")

        with pytest.raises(
            ValueError,
            match="radius must be greater than 0 meters",
        ):
            await client.search_datasets(
                lat=37.7749,
                lon=-122.4194,
                radius=0,
            )

    @pytest.mark.asyncio
    async def test_search_datasets_rejects_bbox_and_point_search_together(self):
        """bbox and point-based search should not be combined in one request."""
        client = ESSDiveClient(api_token="test_token")

        with pytest.raises(
            ValueError,
            match="Use either bbox or lat/lon/radius",
        ):
            await client.search_datasets(
                bbox=[34.0, -119.0, 35.0, -117.0],
                lat=37.7749,
                lon=-122.4194,
                radius=5000,
            )

    def test_dataset_matches_local_filters(self):
        """Local metadata filters should match nested dataset metadata fields."""
        dataset = {
            "creator": [
                {
                    "givenName": "Jane",
                    "familyName": "Doe",
                    "affiliation": "Pennsylvania State University",
                }
            ],
            "variableMeasured": ["snow water equivalent", "soil moisture"],
            "measurementTechnique": ["Automated snow-depth sensor and field surveys"],
            "funder": [{"name": "U.S. Department of Energy"}],
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "alternateName": ["doi:10.15485/example"],
            "editor": {
                "givenName": "Alex",
                "familyName": "Smith",
                "email": "alex@example.org",
            },
            "distribution": [
                {
                    "name": "snow.csv",
                    "encodingFormat": "text/csv",
                    "contentUrl": "https://example.org/snow.csv",
                }
            ],
        }

        assert _dataset_matches_local_filters(
            dataset,
            {
                "creator_affiliation": ["Pennsylvania"],
                "variable_measured": ["snow water"],
                "measurement_technique": ["sensor"],
                "funder": ["department of energy"],
                "license": ["creativecommons"],
                "alternate_name": ["10.15485"],
                "editor": ["alex@example.org"],
                "file_format": ["csv"],
                "file_name": ["snow.csv"],
                "file_url": ["example.org"],
            },
        )

        assert not _dataset_matches_local_filters(
            dataset,
            {"variable_measured": ["streamflow"]},
        )

    @pytest.mark.asyncio
    async def test_apply_local_dataset_filters_hydrates_results(self):
        """Metadata-only filters should hydrate search results with get-dataset."""
        client = ESSDiveClient(api_token="test_token")
        client.get_dataset = AsyncMock(
            return_value={
                "id": "ds1",
                "dataset": {
                    "name": "Snow dataset",
                    "variableMeasured": ["snow water equivalent"],
                    "creator": [
                        {
                            "givenName": "Jane",
                            "familyName": "Doe",
                            "affiliation": "Pennsylvania State University",
                        }
                    ],
                },
            }
        )

        results = {
            "total": 5,
            "query": {"text": "snowmelt"},
            "result": [
                {
                    "id": "ds1",
                    "dataset": {"name": "Snow dataset"},
                    "viewUrl": "https://example.org/ds1",
                }
            ],
        }

        filtered = await _apply_local_dataset_filters(
            client,
            results,
            {
                "creator_affiliation": ["Pennsylvania"],
                "variable_measured": ["snow water"],
            },
        )

        assert filtered["total"] == 1
        assert filtered["result"][0]["dataset"]["variableMeasured"] == [
            "snow water equivalent"
        ]
        assert filtered["query"]["localFilters"]["creator_affiliation"] == [
            "Pennsylvania"
        ]
        assert filtered["filtering"]["native_total"] == 5
        client.get_dataset.assert_awaited_once_with("ds1")

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
    async def test_get_dataset_versions(self):
        """Test get_dataset_versions method."""
        client = ESSDiveClient(api_token="test_token")

        mock_response = {
            "total": 2,
            "pageSize": 2,
            "nextCursor": "next-cursor",
            "previousCursor": None,
            "result": [
                {
                    "id": "ds-v2",
                    "viewUrl": "https://example.org/ds-v2",
                    "dateUploaded": "2026-01-01T00:00:00Z",
                    "dataset": {
                        "name": "Dataset 1 v2",
                        "@id": "doi:10.1234/example",
                        "datePublished": "2026",
                    },
                }
            ],
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

            result = await client.get_dataset_versions("doi:10.1234/example", page_size=2)

            assert result["total"] == 2
            assert result["result"][0]["id"] == "ds-v2"
            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params["pageSize"] == 2

    @pytest.mark.asyncio
    async def test_get_dataset_versions_omits_page_size_when_unset(self):
        """Cursor follow-up requests should not force a default page size."""
        client = ESSDiveClient(api_token="test_token")

        mock_response_obj = Mock()
        mock_response_obj.json.return_value = {"total": 0, "result": []}
        mock_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_response_obj)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            await client.get_dataset_versions("doi:10.1234/example", cursor="cursor-123")

            params = mock_client_instance.get.call_args.kwargs["params"]
            assert params == {"cursor": "cursor-123"}

    @pytest.mark.asyncio
    async def test_get_dataset_versions_cursor_followup_flow_uses_returned_next_cursor(self):
        """A versions response nextCursor should work unchanged for a follow-up page request."""
        client = ESSDiveClient(api_token="test_token")

        first_response = {
            "total": 3,
            "pageSize": 2,
            "nextCursor": "next-version-cursor",
            "previousCursor": None,
            "result": [
                {"id": "ds-v3", "dataset": {"@id": "doi:10.1234/example"}},
                {"id": "ds-v2", "dataset": {"@id": "doi:10.1234/example"}},
            ],
        }
        second_response = {
            "total": 3,
            "pageSize": 2,
            "nextCursor": None,
            "previousCursor": "prev-version-cursor",
            "result": [
                {"id": "ds-v1", "dataset": {"@id": "doi:10.1234/example"}},
            ],
        }

        first_response_obj = Mock()
        first_response_obj.json.return_value = first_response
        first_response_obj.raise_for_status = Mock()

        second_response_obj = Mock()
        second_response_obj.json.return_value = second_response
        second_response_obj.raise_for_status = Mock()

        with patch("essdive_mcp.main.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=[first_response_obj, second_response_obj]
            )
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_class.return_value = mock_client_instance

            first_page = await client.get_dataset_versions(
                "doi:10.1234/example",
                page_size=2,
            )
            second_page = await client.get_dataset_versions(
                "doi:10.1234/example",
                cursor=first_page["nextCursor"],
            )

            assert first_page["nextCursor"] == "next-version-cursor"
            assert second_page["result"][0]["id"] == "ds-v1"
            assert second_page["previousCursor"] == "prev-version-cursor"

            first_params = mock_client_instance.get.call_args_list[0].kwargs["params"]
            second_params = mock_client_instance.get.call_args_list[1].kwargs["params"]
            assert first_params == {"pageSize": 2}
            assert second_params == {"cursor": "next-version-cursor"}

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
                    "isPublic": True,
                    "url": "https://api.example.com/packages/ds1",
                    "previous": "https://api.example.com/packages/ds0",
                    "next": "https://api.example.com/packages/ds2",
                    "dataset": {"name": "Dataset 1", "datePublished": "2024-01-01"},
                    "viewUrl": "https://example.com/ds1"
                }
            ],
            "total": 1,
            "user": "anonymous",
        }

        formatted = client.format_results(results, "summary")

        assert isinstance(formatted, str)
        assert "Dataset 1" in formatted
        assert "ds1" in formatted
        assert "isPublic: True" not in formatted
        assert "Results include public data only." in formatted
        assert (
            "Links: [View dataset](https://example.com/ds1) | "
            "[API record](https://api.example.com/packages/ds1) | "
            "[Previous version](https://api.example.com/packages/ds0) | "
            "[Next version](https://api.example.com/packages/ds2)"
        ) in formatted

    def test_format_results_summary_with_local_filtering(self):
        """Summary format should mention local metadata filtering when used."""
        client = ESSDiveClient()

        results = {
            "result": [
                {
                    "id": "ds1",
                    "dataset": {"name": "Dataset 1", "datePublished": "2024-01-01"},
                    "viewUrl": "https://example.com/ds1",
                }
            ],
            "total": 1,
            "filtering": {
                "native_total": 12,
                "scanned_results": 5,
                "matched_results": 1,
            },
        }

        formatted = client.format_results(results, "summary")

        assert "after local metadata filtering" in formatted
        assert "from 12 native matches" in formatted

    def test_format_results_summary_includes_effective_sort(self):
        """Summary format should surface the effective API sort order."""
        client = ESSDiveClient()

        results = {
            "result": [
                {
                    "id": "ds1",
                    "dataset": {"name": "Dataset 1", "datePublished": "2024-01-01"},
                    "viewUrl": "https://example.com/ds1",
                }
            ],
            "total": 1,
            "query": {"sort": "name:asc"},
        }

        formatted = client.format_results(results, "summary")

        assert "Sort: name:asc" in formatted

    def test_format_results_summary_omits_cursor_pagination(self):
        """Summary format should not expose raw cursor values."""
        client = ESSDiveClient()

        results = {
            "result": [
                {
                    "id": "ds1",
                    "dataset": {"name": "Dataset 1", "datePublished": "2024-01-01"},
                    "viewUrl": "https://example.com/ds1",
                }
            ],
            "total": 10,
            "nextCursor": "next-cursor",
            "previousCursor": None,
        }

        formatted = client.format_results(results, "summary")

        assert "Pagination:" not in formatted
        assert "next-cursor" not in formatted

    def test_format_results_detailed_with_extra_metadata(self):
        """Detailed format should surface richer dataset metadata when present."""
        client = ESSDiveClient()

        results = {
            "result": [
                {
                    "id": "ds1",
                    "isPublic": True,
                    "url": "https://api.example.com/packages/ds1",
                    "previous": "https://api.example.com/packages/ds0",
                    "next": "https://api.example.com/packages/ds2",
                    "dateUploaded": "2024-01-02T00:00:00Z",
                    "dateModified": "2024-01-03T00:00:00Z",
                    "citation": "Example dataset citation",
                    "dataset": {
                        "name": "Dataset 1",
                        "datePublished": "2024-01-01",
                        "alternateName": ["doi:10.15485/example"],
                        "temporalCoverage": {
                            "startDate": "2020-01-01",
                            "endDate": "2020-12-31",
                        },
                        "spatialCoverage": [
                            {
                                "description": "Pennsylvania",
                                "geo": {"latitude": 41.0, "longitude": -77.5},
                            }
                        ],
                        "variableMeasured": ["snow water equivalent"],
                        "measurementTechnique": ["Automated snow-depth sensor"],
                        "funder": [{"name": "DOE"}],
                        "license": "https://creativecommons.org/licenses/by/4.0/",
                        "provider": {
                            "name": "Example Program",
                            "member": {
                                "givenName": "Ada",
                                "familyName": "Lovelace",
                                "jobTitle": "principalInvestigator",
                                "affiliation": "Example Lab",
                            },
                        },
                        "award": ["DOE Award #12345"],
                    },
                    "viewUrl": "https://example.com/ds1",
                }
            ],
            "total": 1,
            "user": "anonymous",
        }

        formatted = client.format_results(results, "detailed")

        assert "Alternate Names" in formatted
        assert "isPublic: True" not in formatted
        assert "Results include public data only." in formatted
        assert "dateUploaded: 2024-01-02T00:00:00Z" in formatted
        assert "dateModified: 2024-01-03T00:00:00Z" in formatted
        assert (
            "Links: [View dataset](https://example.com/ds1) | "
            "[API record](https://api.example.com/packages/ds1) | "
            "[Previous version](https://api.example.com/packages/ds0) | "
            "[Next version](https://api.example.com/packages/ds2)"
        ) in formatted
        assert "Temporal Coverage: 2020-01-01 to 2020-12-31" in formatted
        assert "Spatial Coverage: Pennsylvania (41.0, -77.5)" in formatted
        assert "Variables Measured: snow water equivalent" in formatted
        assert "Measurement Techniques: Automated snow-depth sensor" in formatted
        assert "Funders: DOE" in formatted
        assert "License: https://creativecommons.org/licenses/by/4.0/" in formatted
        assert "Provider: Example Program (Ada Lovelace, principalInvestigator, Example Lab)" in formatted
        assert "Award: DOE Award #12345" in formatted
        assert "citation: Example dataset citation" in formatted

    def test_format_results_no_results(self):
        """Test formatting when no results are found."""
        client = ESSDiveClient()

        results = {}

        formatted = client.format_results(results, "summary")

        assert "No results found" in formatted

    def test_format_dataset_raw(self):
        """Raw dataset format should return unchanged results."""
        client = ESSDiveClient()
        results = {"id": "ds1", "dataset": {"name": "Dataset 1"}, "isPublic": True}

        formatted = client.format_dataset(results, "raw")

        assert formatted == results

    def test_format_dataset_detailed_includes_top_level_package_fields(self):
        """Detailed dataset format should expose top-level package metadata."""
        client = ESSDiveClient()

        results = {
            "id": "ds1",
            "viewUrl": "https://example.com/ds1",
            "url": "https://api.example.com/packages/ds1",
            "previous": "https://api.example.com/packages/ds0",
            "next": "https://api.example.com/packages/ds2",
            "dateUploaded": "2024-01-02T00:00:00Z",
            "dateModified": "2024-01-03T00:00:00Z",
            "isPublic": True,
            "citation": "Example dataset citation",
            "dataset": {
                "name": "Dataset 1",
                "@id": "doi:10.15485/example",
                "datePublished": "2024-01-01",
                "description": "A test dataset",
                "provider": {
                    "name": "Example Program",
                    "member": {
                        "givenName": "Ada",
                        "familyName": "Lovelace",
                        "jobTitle": "principalInvestigator",
                        "affiliation": "Example Lab",
                    },
                },
                "award": ["DOE Award #12345"],
                "distribution": [
                    {
                        "name": "data.csv",
                        "contentSize": 12,
                        "encodingFormat": "text/csv",
                        "contentUrl": "https://example.com/data.csv",
                        "identifier": "file-1",
                    }
                ],
            },
        }

        formatted = client.format_dataset(results, "detailed")

        assert "**id**: ds1" in formatted
        assert "**doi**: doi:10.15485/example" in formatted
        assert (
            "**links**: [View dataset](https://example.com/ds1) | "
            "[API record](https://api.example.com/packages/ds1) | "
            "[Previous version](https://api.example.com/packages/ds0) | "
            "[Next version](https://api.example.com/packages/ds2)"
        ) in formatted
        assert "**dateUploaded**: 2024-01-02T00:00:00Z" in formatted
        assert "**dateModified**: 2024-01-03T00:00:00Z" in formatted
        assert "**isPublic**: True" in formatted
        assert "**citation**: Example dataset citation" in formatted
        assert "## Provider" in formatted
        assert "Example Program (Ada Lovelace, principalInvestigator, Example Lab)" in formatted
        assert "## Award" in formatted
        assert "DOE Award #12345" in formatted
        assert "## Data Files" in formatted
        assert "data.csv" in formatted

    def test_format_dataset_versions_raw(self):
        """Raw version format should return unchanged results."""
        client = ESSDiveClient()
        results = {"result": [{"id": "ds-v2"}], "total": 1}

        formatted = client.format_dataset_versions(results, "raw")

        assert formatted == results

    def test_format_dataset_versions_summary(self):
        """Summary version format should include pagination cursors and version IDs."""
        client = ESSDiveClient()

        results = {
            "total": 2,
            "pageSize": 2,
            "nextCursor": "next-cursor",
            "previousCursor": None,
            "user": "anonymous",
            "result": [
                {
                    "id": "ds-v2",
                    "isPublic": True,
                    "viewUrl": "https://example.com/ds-v2",
                    "url": "https://api.example.com/packages/ds-v2",
                    "previous": "https://api.example.com/packages/ds-v1",
                    "next": "https://api.example.com/packages/ds-v3",
                    "dateUploaded": "2026-01-01T00:00:00Z",
                    "dataset": {
                        "name": "Dataset 1 v2",
                        "@id": "doi:10.1234/example",
                        "datePublished": "2026",
                    },
                }
            ],
        }

        formatted = client.format_dataset_versions(results, "summary")

        assert isinstance(formatted, str)
        assert "Found 2 visible dataset versions" in formatted
        assert "Results include public data only." in formatted
        assert "Pagination:" not in formatted
        assert "next-cursor" not in formatted
        assert "ds-v2" in formatted
        assert "isPublic: True" not in formatted
        assert "dateUploaded: 2026-01-01T00:00:00Z" in formatted
        assert (
            "Links: [View dataset](https://example.com/ds-v2) | "
            "[API record](https://api.example.com/packages/ds-v2) | "
            "[Previous version](https://api.example.com/packages/ds-v1) | "
            "[Next version](https://api.example.com/packages/ds-v3)"
        ) in formatted

    def test_format_dataset_versions_detailed(self):
        """Detailed version format should surface citation and neighbor links."""
        client = ESSDiveClient()

        results = {
            "total": 1,
            "pageSize": 1,
            "nextCursor": None,
            "previousCursor": None,
            "user": "anonymous",
            "result": [
                {
                    "id": "ds-v2",
                    "viewUrl": "https://example.com/ds-v2",
                    "url": "https://api.example.com/packages/ds-v2",
                    "next": "https://api.example.com/packages/ds-v3",
                    "previous": "https://api.example.com/packages/ds-v1",
                    "dateUploaded": "2026-01-01T00:00:00Z",
                    "dateModified": "2026-01-02T00:00:00Z",
                    "isPublic": True,
                    "citation": "Example Citation",
                    "dataset": {
                        "name": "Dataset 1 v2",
                        "@id": "doi:10.1234/example",
                        "datePublished": "2026",
                        "description": "Example description",
                    },
                }
            ],
        }

        formatted = client.format_dataset_versions(results, "detailed")

        assert "Results include public data only." in formatted
        assert "citation: Example Citation" in formatted
        assert "isPublic: True" not in formatted
        assert "dateUploaded: 2026-01-01T00:00:00Z" in formatted
        assert "dateModified: 2026-01-02T00:00:00Z" in formatted
        assert (
            "Links: [View dataset](https://example.com/ds-v2) | "
            "[API record](https://api.example.com/packages/ds-v2) | "
            "[Previous version](https://api.example.com/packages/ds-v1) | "
            "[Next version](https://api.example.com/packages/ds-v3)"
        ) in formatted
        assert "Newer Version URL" in formatted
        assert "Older Version URL" in formatted


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

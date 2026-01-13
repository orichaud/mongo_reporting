import argparse
import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path
import requests
from get_cluster_report import (
    api_get,
    api_get_all,
    get_tier,
    is_large_tier,
    infer_format,
    validate_args,
    export_report,
    filter_projects,
    Config,
)


def test_api_get_success(mocker):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"id": "1", "name": "Test"}]}
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch("get_cluster_report.get_session", return_value=mock_session)

    data = api_get("/test")
    assert data is not None
    assert data["results"][0]["name"] == "Test"


def test_api_get_http_error(mocker):
    err = requests.exceptions.HTTPError("HTTP Error")
    err.response = MagicMock(status_code=404, text="Not found")
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = err
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch("get_cluster_report.get_session", return_value=mock_session)

    assert api_get("/test") is None


def test_api_get_retries_on_429(mocker):
    mocker.patch("get_cluster_report.config", Config(max_attempts=2))
    err = requests.exceptions.HTTPError("Rate limited")
    err.response = MagicMock(status_code=429, headers={})

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = err
    ok_resp = MagicMock()
    ok_resp.json.return_value = {"ok": True}

    mock_session = MagicMock()
    mock_session.get.side_effect = [fail_resp, ok_resp]
    mocker.patch("get_cluster_report.get_session", return_value=mock_session)
    mocker.patch("time.sleep")

    assert api_get("/test") == {"ok": True}


def test_api_get_respects_retry_after(mocker):
    mocker.patch("get_cluster_report.config", Config(max_attempts=2))
    sleep_mock = mocker.patch("time.sleep")
    err = requests.exceptions.HTTPError("Rate limited")
    err.response = MagicMock(status_code=429, headers={"Retry-After": "60"})

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = err
    ok_resp = MagicMock()
    ok_resp.json.return_value = {"ok": True}

    mock_session = MagicMock()
    mock_session.get.side_effect = [fail_resp, ok_resp]
    mocker.patch("get_cluster_report.get_session", return_value=mock_session)

    assert api_get("/test") == {"ok": True}
    sleep_mock.assert_called_once_with(60)


def test_api_get_all_single_page(mocker):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [{"id": "1"}, {"id": "2"}],
        "totalCount": 2,
    }
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch("get_cluster_report.get_session", return_value=mock_session)

    results = api_get_all("/test")
    assert len(results) == 2


def test_api_get_all_empty(mocker):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [], "totalCount": 0}
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch("get_cluster_report.get_session", return_value=mock_session)

    assert api_get_all("/test") == []


class TestGetTier:
    def test_serverless(self):
        assert get_tier({"clusterType": "SERVERLESS"}) == "Serverless"

    def test_regular(self):
        assert get_tier({"providerSettings": {"instanceSizeName": "M30"}}) == "M30"

    def test_missing(self):
        assert get_tier({}) == "N/A"

    def test_empty(self):
        assert get_tier({"providerSettings": {}}) == "N/A"


class TestIsLargeTier:
    def test_large(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=30))
        assert is_large_tier("M40") is True

    def test_small(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=30))
        assert is_large_tier("M10") is False

    def test_boundary(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=30))
        assert is_large_tier("M30") is False
        assert is_large_tier("M31") is True

    def test_serverless(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=30))
        assert is_large_tier("Serverless") is False

    def test_na(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=30))
        assert is_large_tier("N/A") is False

    def test_custom(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=10))
        assert is_large_tier("M20") is True

    def test_r_series(self, mocker):
        mocker.patch("get_cluster_report.config", Config(highlight_threshold=30))
        assert is_large_tier("R40") is False


class TestInferFormat:
    def test_json(self):
        assert infer_format(Path("r.json"), None) == "json"

    def test_csv(self):
        assert infer_format(Path("r.csv"), None) == "csv"

    def test_uppercase(self):
        assert infer_format(Path("r.JSON"), None) == "json"

    def test_explicit(self):
        assert infer_format(Path("r.txt"), "json") == "json"

    def test_unknown(self):
        with pytest.raises(ValueError):
            infer_format(Path("r.txt"), None)

    def test_no_ext(self):
        with pytest.raises(ValueError):
            infer_format(Path("report"), None)


class TestValidateArgs:
    def test_valid(self):
        validate_args(
            argparse.Namespace(
                items_per_page=100,
                max_attempts=5,
                max_workers=10,
                timeout=30,
                highlight_threshold=30,
            )
        )

    def test_items_low(self):
        with pytest.raises(SystemExit):
            validate_args(
                argparse.Namespace(
                    items_per_page=0,
                    max_attempts=5,
                    max_workers=10,
                    timeout=30,
                    highlight_threshold=30,
                )
            )

    def test_items_high(self):
        with pytest.raises(SystemExit):
            validate_args(
                argparse.Namespace(
                    items_per_page=501,
                    max_attempts=5,
                    max_workers=10,
                    timeout=30,
                    highlight_threshold=30,
                )
            )

    def test_attempts_low(self):
        with pytest.raises(SystemExit):
            validate_args(
                argparse.Namespace(
                    items_per_page=100,
                    max_attempts=0,
                    max_workers=10,
                    timeout=30,
                    highlight_threshold=30,
                )
            )

    def test_timeout_low(self):
        with pytest.raises(SystemExit):
            validate_args(
                argparse.Namespace(
                    items_per_page=100,
                    max_attempts=5,
                    max_workers=10,
                    timeout=0,
                    highlight_threshold=30,
                )
            )

    def test_threshold_neg(self):
        with pytest.raises(SystemExit):
            validate_args(
                argparse.Namespace(
                    items_per_page=100,
                    max_attempts=5,
                    max_workers=10,
                    timeout=30,
                    highlight_threshold=-1,
                )
            )


class TestExportReport:
    def test_json(self, tmp_path):
        reports = [
            {
                "project_name": "test",
                "clusters": [
                    {
                        "name": "c1",
                        "clusterType": "REPLICASET",
                        "diskSizeGB": 10.0,
                        "providerSettings": {"instanceSizeName": "M10"},
                    }
                ],
            }
        ]
        out = tmp_path / "r.json"
        export_report(reports, out, "json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert "generated_at" in data
        assert len(data["projects"]) == 1

    def test_csv(self, tmp_path):
        reports = [
            {
                "project_name": "test",
                "clusters": [
                    {
                        "name": "c1",
                        "clusterType": "REPLICASET",
                        "diskSizeGB": 10.0,
                        "providerSettings": {"instanceSizeName": "M10"},
                    }
                ],
            }
        ]
        out = tmp_path / "r.csv"
        export_report(reports, out, "csv")
        assert out.exists()
        content = out.read_text()
        assert "test" in content and "c1" in content

    def test_empty_project(self, tmp_path):
        out = tmp_path / "r.csv"
        export_report([{"project_name": "empty", "clusters": []}], out, "csv")
        assert "empty" in out.read_text()

    def test_creates_dir(self, tmp_path):
        out = tmp_path / "sub" / "r.json"
        export_report([{"project_name": "t", "clusters": []}], out, "json")
        assert out.exists()


class TestConfig:
    def test_color_disabled(self):
        assert Config(no_color=True).color("\x1b[91m") == ""

    def test_color_forced(self):
        assert Config(force_color=True).color("\x1b[91m") == "\x1b[91m"


class TestFilterProjects:
    @pytest.fixture
    def projects(self):
        return [
            {"id": "1", "name": "prod-us"},
            {"id": "2", "name": "prod-eu"},
            {"id": "3", "name": "dev-us"},
            {"id": "4", "name": "qa-us"},
            {"id": "5", "name": "prod-tools"},
        ]

    def test_no_filter(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config())
        assert len(filter_projects(projects)) == 5

    def test_include(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config(include_projects=["prod-*"]))
        assert len(filter_projects(projects)) == 3

    def test_exclude(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config(exclude_projects=["*-tools"]))
        assert len(filter_projects(projects)) == 4

    def test_both(self, projects, mocker):
        mocker.patch(
            "get_cluster_report.config",
            Config(include_projects=["prod-*"], exclude_projects=["*-tools"]),
        )
        assert len(filter_projects(projects)) == 2

    def test_case_insensitive(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config(include_projects=["PROD-*"]))
        assert len(filter_projects(projects)) == 3

    def test_exact(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config(include_projects=["dev-us"]))
        assert len(filter_projects(projects)) == 1

    def test_no_match(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config(include_projects=["xxx"]))
        assert len(filter_projects(projects)) == 0

    def test_exclude_all(self, projects, mocker):
        mocker.patch("get_cluster_report.config", Config(exclude_projects=["*"]))
        assert len(filter_projects(projects)) == 0

"""Phase 11 (Slice D) — ported action tools as an MCP server.

Network + LLM are mocked everywhere: no live DDG/open-meteo/YouTube/Playwright
calls and no live model spend. Each tool is a plain callable (FastMCP's
``@mcp.tool()`` returns the function unchanged), so we call them directly.
"""

import asyncio
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
jv = importlib.import_module("jarvis_tools_mcp")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
class _Resp:
    """Minimal stand-in for requests.Response."""

    def __init__(self, *, json_data=None, text=""):
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


@pytest.fixture(autouse=True)
def _no_live_llm(monkeypatch):
    """Default: any _route_llm call returns a deterministic stub, not a model."""
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "STUBBED-LLM")


# --------------------------------------------------------------------------- #
# registration
# --------------------------------------------------------------------------- #
def test_all_six_tools_registered():
    tools = asyncio.run(jv.mcp.list_tools())
    names = {t.name for t in tools}
    assert {
        "web_search",
        "weather",
        "reminder",
        "youtube",
        "flight_finder",
        "file_processor",
    } <= names


def test_setup_config_emits_tools_server():
    setup = importlib.import_module("setup_config")
    entry = setup._tools_server()
    assert entry is not None
    assert entry["name"] == "jarvis-tools"
    assert entry["args"] and entry["args"][0].endswith("jarvis_tools_mcp.py")


# --------------------------------------------------------------------------- #
# web_search
# --------------------------------------------------------------------------- #
def test_web_search_formats_and_summarizes(monkeypatch):
    monkeypatch.setattr(
        jv,
        "_ddg_search",
        lambda q, max_results=6: [
            {"title": "T1", "snippet": "S1", "url": "http://a"},
            {"title": "T2", "snippet": "S2", "url": "http://b"},
        ],
    )
    captured = {}

    def fake_llm(prompt, system=None, **k):
        captured["p"] = prompt
        return "SUMMARY"

    monkeypatch.setattr(jv, "_route_llm", fake_llm)
    out = jv.web_search(query="quantum computing")
    assert out == "SUMMARY"
    assert "S1" in captured["p"]  # raw results were fed to the summarizer


def test_web_search_requires_query():
    assert "search query" in jv.web_search(query="").lower()


def test_web_search_compare_mode(monkeypatch):
    monkeypatch.setattr(jv, "_ddg_search", lambda q, max_results=6: [{"snippet": q}])
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "COMPARISON")
    out = jv.web_search(query="", items=["a", "b"], aspect="price")
    assert out == "COMPARISON"


# --------------------------------------------------------------------------- #
# weather (open-meteo, keyless)
# --------------------------------------------------------------------------- #
def test_weather_parses_open_meteo(monkeypatch):
    def fake_get(url, *a, **k):
        if "geocoding" in url:
            return _Resp(
                json_data={
                    "results": [
                        {"latitude": 51.5, "longitude": -0.1, "name": "London", "country": "UK"}
                    ]
                }
            )
        return _Resp(
            json_data={"current": {"temperature_2m": 12.3, "weather_code": 3, "wind_speed_10m": 9.0}}
        )

    monkeypatch.setattr(jv.requests, "get", fake_get)
    out = jv.weather(city="London")
    assert "London" in out
    assert "12.3" in out
    assert jv._weather_code_text(3).lower() in out.lower()  # code 3 == overcast


def test_weather_requires_city():
    assert "city" in jv.weather(city="").lower()


def test_weather_unknown_city(monkeypatch):
    monkeypatch.setattr(jv.requests, "get", lambda url, *a, **k: _Resp(json_data={"results": []}))
    out = jv.weather(city="Zzzxqq")
    assert "couldn't find" in out.lower() or "could not find" in out.lower()


def test_weather_code_text_maps_known_and_unknown():
    assert jv._weather_code_text(0)  # clear sky
    assert jv._weather_code_text(99)  # thunderstorm
    assert jv._weather_code_text(12345)  # unknown -> safe fallback string


# --------------------------------------------------------------------------- #
# reminder (server-host scheduler; never actually schedules in tests)
# --------------------------------------------------------------------------- #
def test_reminder_schedules_future(monkeypatch, tmp_path):
    monkeypatch.setattr(jv, "_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(jv, "_os_name", lambda: "windows")

    class _OK:
        returncode = 0
        stdout = "SUCCESS"
        stderr = ""

    monkeypatch.setattr(jv.subprocess, "run", lambda *a, **k: _OK())
    out = jv.reminder(date="2099-01-01", time="09:30", message="standup")
    assert "2099" in out or "January" in out
    # a notify script was written into the tmp scripts dir
    assert any(p.suffix == ".py" for p in tmp_path.iterdir())


def test_reminder_rejects_past():
    assert "past" in jv.reminder(date="2000-01-01", time="09:00", message="x").lower()


def test_reminder_rejects_bad_format():
    assert "parse" in jv.reminder(date="nope", time="bad", message="x").lower()


def test_reminder_requires_date_and_time():
    assert "date and a time" in jv.reminder(date="", time="", message="x").lower()


# --------------------------------------------------------------------------- #
# youtube
# --------------------------------------------------------------------------- #
def test_youtube_get_info(monkeypatch):
    monkeypatch.setattr(
        jv,
        "_scrape_video_info",
        lambda vid: {"title": "Cool Vid", "channel": "Chan", "views": "1,000"},
    )
    out = jv.youtube(action="get_info", url="https://youtu.be/abcdefghijk")
    assert "Cool Vid" in out and "Chan" in out


def test_youtube_play_returns_url(monkeypatch):
    monkeypatch.setattr(
        jv, "_scrape_first_video_url", lambda q: "https://www.youtube.com/watch?v=ZZZZZZZZZZZ"
    )
    out = jv.youtube(action="play", query="lofi beats")
    assert "youtube.com/watch?v=" in out


def test_youtube_summarize(monkeypatch):
    monkeypatch.setattr(jv, "_get_transcript", lambda vid: "a long transcript about cats")
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "SUMMARY OF VIDEO")
    out = jv.youtube(action="summarize", url="https://youtu.be/abcdefghijk")
    assert out == "SUMMARY OF VIDEO"


def test_youtube_trending(monkeypatch):
    monkeypatch.setattr(
        jv,
        "_scrape_trending",
        lambda region="US", max_results=8: [{"rank": 1, "title": "Hot", "channel": "C"}],
    )
    out = jv.youtube(action="trending", region="US")
    assert "Hot" in out


def test_youtube_unknown_action():
    assert "unknown" in jv.youtube(action="frobnicate").lower()


def test_extract_video_id():
    assert jv._extract_video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert jv._extract_video_id("not a url") is None


# --------------------------------------------------------------------------- #
# flight_finder
# --------------------------------------------------------------------------- #
def test_flight_finder_scrapes_and_parses(monkeypatch):
    monkeypatch.setattr(jv, "_scrape_flight_text", lambda url: "raw google flights page text")
    monkeypatch.setattr(
        jv,
        "_route_llm",
        lambda *a, **k: '[{"airline":"AirX","departure":"08:00","arrival":"10:00","stops":0,"price":"199","currency":"USD"}]',
    )
    out = jv.flight_finder(origin="JFK", destination="LHR", date="2099-05-01")
    assert "AirX" in out


def test_flight_finder_requires_origin_destination():
    assert "origin and destination" in jv.flight_finder(
        origin="", destination="", date="2099-05-01"
    ).lower()


def test_flight_finder_requires_date():
    assert "date" in jv.flight_finder(origin="JFK", destination="LHR", date="").lower()


def test_flight_url_builder_contains_route():
    url = jv._build_google_flights_url("JFK", "LHR", "2099-05-01")
    assert "JFK" in url and "LHR" in url


def test_parse_date_iso_passthrough():
    assert jv._parse_date("2099-05-01") == "2099-05-01"


# --------------------------------------------------------------------------- #
# file_processor (server-side path)
# --------------------------------------------------------------------------- #
def test_file_processor_text_summarize(monkeypatch, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hello world, this is a document about testing", encoding="utf-8")
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "A SUMMARY")
    out = jv.file_processor(file_path=str(f), action="summarize")
    assert out == "A SUMMARY"


def test_file_processor_json_validate(tmp_path):
    f = tmp_path / "data.json"
    f.write_text('{"a": 1}', encoding="utf-8")
    out = jv.file_processor(file_path=str(f), action="validate")
    assert "valid json" in out.lower()


def test_file_processor_missing_file():
    assert "not found" in jv.file_processor(file_path="C:/nope/missing.txt").lower()


def test_file_processor_requires_path():
    assert "no file path" in jv.file_processor(file_path="").lower()


# --------------------------------------------------------------------------- #
# _route_llm shim — wraps the router, degrades on exhaustion
# --------------------------------------------------------------------------- #
def test_route_llm_degrades_on_router_failure(monkeypatch):
    # un-stub: exercise the real _route_llm against a failing router
    monkeypatch.undo()

    def boom(*a, **k):
        raise RuntimeError("ladder exhausted")

    monkeypatch.setattr(jv, "complete_with_fallback", boom)
    out = jv._route_llm("hi")
    assert "unavailable" in out.lower()


# --------------------------------------------------------------------------- #
# parse-logic coverage (mocked I/O — exercises the real regex / formatting)
# --------------------------------------------------------------------------- #
def test_format_ddg_empty_and_populated():
    assert "No results" in jv._format_ddg("q", [])
    out = jv._format_ddg("q", [{"title": "T", "snippet": "S", "url": "u"}])
    assert "T" in out and "S" in out and "u" in out


def test_compare_uses_search_and_summary(monkeypatch):
    monkeypatch.setattr(jv, "_ddg_search", lambda q, max_results=3: [{"snippet": f"about {q}"}])
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "CMP")
    assert jv._compare(["x", "y"], "speed") == "CMP"


def test_scrape_video_info_parses_html(monkeypatch):
    html = (
        '..."title":{"runs":[{"text":"My Title"}]}...'
        '"ownerChannelName":"My Channel"..."viewCount":"12345"..."lengthSeconds":"125"...'
    )
    monkeypatch.setattr(jv.requests, "get", lambda *a, **k: _Resp(text=html))
    info = jv._scrape_video_info("abcdefghijk")
    assert info["title"] == "My Title"
    assert info["channel"] == "My Channel"
    assert info["views"] == "12,345"
    assert info["duration"] == "2:05"


def test_scrape_trending_parses_html(monkeypatch):
    html = (
        '"title":{"runs":[{"text":"First Trending"}]}'
        '"ownerText":{"runs":[{"text":"Chan A"}]}'
        '"title":{"runs":[{"text":"Second Trending"}]}'
        '"ownerText":{"runs":[{"text":"Chan B"}]}'
    )
    monkeypatch.setattr(jv.requests, "get", lambda *a, **k: _Resp(text=html))
    rows = jv._scrape_trending(region="US")
    assert rows[0]["title"] == "First Trending"
    assert rows[0]["channel"] == "Chan A"


def test_scrape_first_video_url_skips_shorts(monkeypatch):
    html = '"videoId":"ZZZZZZZZZZZ"'  # a plain watch video
    monkeypatch.setattr(jv.requests, "get", lambda *a, **k: _Resp(text=html))
    assert jv._scrape_first_video_url("q") == "https://www.youtube.com/watch?v=ZZZZZZZZZZZ"


def test_scrape_network_failure_is_graceful(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(jv.requests, "get", boom)
    assert jv._scrape_video_info("abcdefghijk") == {}
    assert jv._scrape_trending() == []
    assert jv._scrape_first_video_url("q") is None


def test_parse_date_numeric_formats():
    assert jv._parse_date("01/05/2099") == "2099-05-01"  # dd/mm/yyyy (day-first)
    assert jv._parse_date("today") == jv.datetime.now().strftime("%Y-%m-%d")


def test_parse_date_fuzzy_via_router(monkeypatch):
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "2099-12-25")
    assert jv._parse_date("Christmas 2099") == "2099-12-25"


def test_parse_date_unparseable_falls_back_to_today(monkeypatch):
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "not a date")
    assert jv._parse_date("gibberish") == jv.datetime.now().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# weather + reminder branch coverage
# --------------------------------------------------------------------------- #
def test_weather_network_error_is_graceful(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("dns fail")

    monkeypatch.setattr(jv.requests, "get", boom)
    assert "failed" in jv.weather(city="London").lower()


def test_reminder_scheduler_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(jv, "_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(jv, "_os_name", lambda: "windows")

    class _Fail:
        returncode = 1
        stdout = ""
        stderr = "denied"

    monkeypatch.setattr(jv.subprocess, "run", lambda *a, **k: _Fail())
    out = jv.reminder(date="2099-01-01", time="09:30", message="x")
    assert "couldn't register" in out.lower()


def test_reminder_linux_systemd(monkeypatch, tmp_path):
    monkeypatch.setattr(jv, "_scripts_dir", lambda: tmp_path)
    monkeypatch.setattr(jv, "_os_name", lambda: "linux")
    monkeypatch.setattr(jv.shutil, "which", lambda name: "/usr/bin/systemd-run")

    class _OK:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(jv.subprocess, "run", lambda *a, **k: _OK())
    out = jv.reminder(date="2099-01-01", time="09:30", message="x")
    assert "Reminder set" in out


# --------------------------------------------------------------------------- #
# file_processor branch coverage
# --------------------------------------------------------------------------- #
def test_file_processor_code_explain(monkeypatch, tmp_path):
    f = tmp_path / "snippet.py"
    f.write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(jv, "_route_llm", lambda *a, **k: "CODE EXPLANATION")
    assert jv.file_processor(file_path=str(f), action="explain") == "CODE EXPLANATION"


def test_file_processor_code_info(tmp_path):
    f = tmp_path / "snippet.py"
    f.write_text("a\nb\nc\n", encoding="utf-8")
    out = jv.file_processor(file_path=str(f), action="info")
    assert "lines" in out


def test_file_processor_json_format_writes_file(tmp_path):
    f = tmp_path / "d.json"
    f.write_text('{"b":2,"a":1}', encoding="utf-8")
    out = jv.file_processor(file_path=str(f), action="format")
    assert "saved" in out.lower()
    assert (tmp_path / "d_formatted.json").exists()


def test_file_processor_text_word_count(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text("one two three", encoding="utf-8")
    out = jv.file_processor(file_path=str(f), action="word_count")
    assert "3 words" in out


def test_file_processor_unsupported_type(tmp_path):
    f = tmp_path / "pic.png"
    f.write_bytes(b"\x89PNG\r\n")
    out = jv.file_processor(file_path=str(f))
    assert "isn't supported" in out.lower() or "not supported" in out.lower()


def test_llm_model_drops_non_text(monkeypatch):
    seen = {}
    monkeypatch.setattr(jv, "_route_llm", lambda text, **k: seen.setdefault("t", text) or "ok")
    jv._LLMModel().generate_content(["describe", b"\x00binary", "image"])
    assert "describe" in seen["t"] and "image" in seen["t"]
    assert "binary" not in seen["t"]


# --------------------------------------------------------------------------- #
# _os_name mapping
# --------------------------------------------------------------------------- #
def test_os_name_maps(monkeypatch):
    monkeypatch.setattr(jv.platform, "system", lambda: "Darwin")
    assert jv._os_name() == "mac"
    monkeypatch.setattr(jv.platform, "system", lambda: "Windows")
    assert jv._os_name() == "windows" and jv._is_windows()
    monkeypatch.setattr(jv.platform, "system", lambda: "Linux")
    assert jv._os_name() == "linux"


def test_ddg_search_maps_fields(monkeypatch):
    import ddgs

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, q, max_results=6):
            return [{"title": "T", "body": "B", "href": "H"}]

    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    assert jv._ddg_search("q") == [{"title": "T", "snippet": "B", "url": "H"}]


def test_get_transcript_joins_segments(monkeypatch):
    import youtube_transcript_api as yta

    class _FakeTranscript:
        def fetch(self):
            return [{"text": "hello"}, {"text": "world"}]

    class _FakeList:
        def find_manually_created_transcript(self, langs):
            return _FakeTranscript()

    class _FakeAPI:
        @staticmethod
        def list_transcripts(vid):
            return _FakeList()

    monkeypatch.setattr(yta, "YouTubeTranscriptApi", _FakeAPI)
    assert jv._get_transcript("abcdefghijk") == "hello world"

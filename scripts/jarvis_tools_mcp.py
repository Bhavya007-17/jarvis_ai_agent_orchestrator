#!/usr/bin/env python
"""Jarvis action tools as an MCP server (Phase 11 / slice D).

Ports six Mark-XL actions into a single stdio MCP server the OpenJarvis
orchestrator can call through its existing tool-loop (the Phase-2 drop-in seam,
``config.tools.mcp.servers``). The reusable kernels come from
``_vendor/Mark-XL/actions/`` — only the I/O is adapted for a headless web
server, and every in-tool LLM call is rewired through the Phase-1 router
(``complete_with_fallback``) per the project's hard rule "no new LLM path".

Web-safe adaptations vs the originals:
  * weather    — rewritten to fetch open-meteo (free, keyless) and return text,
                 instead of opening the server's browser.
  * youtube    — drops the tkinter URL dialog and browser-open; ``play`` returns
                 the resolved URL, ``summarize`` takes a ``url`` argument.
  * flight     — scrapes via Playwright (repo-present) instead of Selenium.
  * reminder   — runs on the sidecar host (reminders are server-local by nature).

Run as a server:    uv run python scripts/jarvis_tools_mcp.py
Importable for tests: every @mcp.tool() function is also a plain callable.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests

# The MCP server's own directory must be importable so `jarvis_router` resolves
# when OpenJarvis spawns this via `python scripts/jarvis_tools_mcp.py`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from jarvis_router import complete_with_fallback  # noqa: E402
from openjarvis.core.types import Message, Role  # noqa: E402

mcp = FastMCP("jarvis-tools")


# --------------------------------------------------------------------------- #
# LLM-routing shim — the hard-rule linchpin. Every in-tool model call goes here.
# --------------------------------------------------------------------------- #
def _route_llm(
    prompt: str,
    system: str | None = None,
    *,
    task_type: str = "general",
    max_tokens: int = 512,
) -> str:
    """Run one completion through the Phase-1 fallback ladder; never raise."""
    messages: list[Message] = []
    if system:
        messages.append(Message(role=Role.SYSTEM, content=system))
    messages.append(Message(role=Role.USER, content=prompt))
    try:
        result = complete_with_fallback(messages, task_type, max_tokens=max_tokens)
        return (result.get("content") or "").strip()
    except Exception as e:  # ladder exhausted — degrade gracefully
        return f"(LLM unavailable: {e})"


def _os_name() -> str:
    s = platform.system().lower()
    if s == "darwin":
        return "mac"
    if s == "windows":
        return "windows"
    return "linux"


def _is_windows() -> bool:
    return _os_name() == "windows"


# --------------------------------------------------------------------------- #
# web_search  (port: _ddg_search / _format_ddg / _compare)
# --------------------------------------------------------------------------- #
def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover - older package name
        from duckduckgo_search import DDGS

    results: list[dict] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                }
            )
    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):
            lines.append(f"{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _summarize_results(query: str, raw_results: str) -> str:
    system = (
        "You are Jarvis. Summarize web search results clearly and concisely. "
        "Answer the user's query directly and factually."
    )
    prompt = (
        f"User question: {query}\n\n"
        f"Web search results:\n{raw_results[:4000]}\n\n"
        "Answer the question based on these results:"
    )
    return _route_llm(prompt, system, task_type="general", max_tokens=512)


def _compare(items: list[str], aspect: str) -> str:
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []
    lines = [f"Comparison - {aspect.upper()}", "-" * 40]
    for item in items:
        lines.append(f"\n- {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  * {r['snippet']}")
    raw = "\n".join(lines)
    return _summarize_results(f"Compare {', '.join(items)} regarding {aspect}", raw)


@mcp.tool()
def web_search(
    query: str = "",
    mode: str = "search",
    items: list[str] | None = None,
    aspect: str = "general",
) -> str:
    """Search the web (DuckDuckGo) and return a concise, summarized answer.

    Use for current events, facts, or general lookups. For comparing several
    things, pass ``items=["a","b"]`` and an ``aspect`` (e.g. "price").
    """
    items = items or []
    query = (query or "").strip()
    mode = (mode or "search").lower().strip()
    aspect = (aspect or "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query."
    if items and mode != "compare":
        mode = "compare"

    try:
        if mode == "compare" and items:
            return _compare(items, aspect)
        results = _ddg_search(query)
        return _summarize_results(query, _format_ddg(query, results))
    except Exception as e:
        return f"Search failed: {e}"


# --------------------------------------------------------------------------- #
# weather  (web-safe rewrite: open-meteo geocode + forecast -> text)
# --------------------------------------------------------------------------- #
_WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _weather_code_text(code: int) -> str:
    return _WMO_CODES.get(int(code), f"Unknown conditions (code {code})")


def _geocode(city: str) -> dict | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    resp = requests.get(url, params={"name": city, "count": 1}, timeout=10)
    resp.raise_for_status()
    results = (resp.json() or {}).get("results") or []
    return results[0] if results else None


def _current_weather(lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    resp = requests.get(
        url,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,wind_speed_10m",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return (resp.json() or {}).get("current") or {}


@mcp.tool()
def weather(city: str = "", when: str = "today") -> str:
    """Get the current weather for a city (text). Keyless via open-meteo.

    ``when`` is accepted for phrasing but the data returned is current
    conditions (open-meteo's free current endpoint).
    """
    city = (city or "").strip()
    when = (when or "today").strip() or "today"
    if not city:
        return "Please tell me which city you want the weather for."
    try:
        place = _geocode(city)
        if not place:
            return f"I couldn't find a city called '{city}'."
        cur = _current_weather(place["latitude"], place["longitude"])
        if not cur:
            return f"I couldn't retrieve current weather for {city}."
        name = place.get("name", city)
        country = place.get("country", "")
        desc = _weather_code_text(cur.get("weather_code", -1))
        temp = cur.get("temperature_2m")
        wind = cur.get("wind_speed_10m")
        where = f"{name}, {country}".strip().rstrip(",")
        return f"Weather in {where} ({when}): {desc}, {temp}°C, wind {wind} km/h."
    except Exception as e:
        return f"Weather lookup failed: {e}"


# --------------------------------------------------------------------------- #
# reminder  (port: _sanitise / _write_notify_script / _schedule_*)
#   Runs on the sidecar host; reminders are server-local by nature.
# --------------------------------------------------------------------------- #
def _scripts_dir() -> Path:
    d = Path.home() / ".jarvis" / "reminders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitise(text: str, max_len: int = 200) -> str:
    return (
        text.replace("\\", "")
        .replace('"', "")
        .replace("'", "")
        .replace("\n", " ")
        .replace("\r", "")
        .strip()
    )[:max_len]


def _write_notify_script(task_name: str, message: str, os_name: str) -> Path:
    script_path = _scripts_dir() / f"{task_name}.py"
    msg_literal = json.dumps(message)

    if os_name == "windows":
        notify_block = f"""
message = {msg_literal}
notified = False
try:
    from plyer import notification
    notification.notify(title="Jarvis Reminder", message=message, timeout=15)
    notified = True
except Exception:
    pass
if not notified:
    try:
        import subprocess
        subprocess.run(["msg", "*", "/TIME:30", message], check=False)
    except Exception:
        pass
"""
    elif os_name == "mac":
        notify_block = f"""
message = {msg_literal}
try:
    import subprocess
    script = 'display notification "{{}}" with title "Jarvis Reminder"'.format(
        message.replace('"', '')
    )
    subprocess.run(["osascript", "-e", script], check=False)
except Exception:
    pass
"""
    else:  # linux
        notify_block = f"""
message = {msg_literal}
try:
    import subprocess
    subprocess.run(
        ["notify-send", "--urgency=normal", "--expire-time=15000",
         "Jarvis Reminder", message],
        check=False,
    )
except Exception:
    pass
"""

    script_body = f"""# Auto-generated by Jarvis reminder - do not edit
import pathlib
{notify_block}
try:
    pathlib.Path(__file__).unlink(missing_ok=True)
except Exception:
    pass
"""
    script_path.write_text(script_body, encoding="utf-8")
    try:
        script_path.chmod(0o600)
    except Exception:
        pass
    return script_path


def _schedule_windows(target_dt: datetime, task_name: str, script_path: Path) -> str:
    python_exe = Path(sys.executable)
    pythonw = python_exe.parent / "pythonw.exe"
    if pythonw.exists():
        python_exe = pythonw

    xml_path = _scripts_dir() / f"{task_name}.xml"
    xml_content = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo><Description>Jarvis Reminder</Description></RegistrationInfo>\n"
        "  <Triggers><TimeTrigger>\n"
        f'    <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>\n'
        "    <Enabled>true</Enabled>\n"
        "  </TimeTrigger></Triggers>\n"
        "  <Actions><Exec>\n"
        f"    <Command>{python_exe}</Command>\n"
        f'    <Arguments>"{script_path}"</Arguments>\n'
        "  </Exec></Actions>\n"
        "  <Settings>\n"
        "    <StartWhenAvailable>true</StartWhenAvailable>\n"
        "    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>\n"
        "  </Settings>\n"
        "  <Principals><Principal>\n"
        "    <LogonType>InteractiveToken</LogonType>\n"
        "    <RunLevel>LeastPrivilege</RunLevel>\n"
        "  </Principal></Principals>\n"
        "</Task>"
    )
    xml_path.write_text(xml_content, encoding="utf-16")
    result = subprocess.run(
        ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
        capture_output=True,
        text=True,
    )
    try:
        xml_path.unlink(missing_ok=True)
    except Exception:
        pass
    if result.returncode != 0:
        script_path.unlink(missing_ok=True)
        return ""
    return task_name


def _schedule_unix(target_dt: datetime, task_name: str, script_path: Path, os_name: str) -> str:
    if os_name == "mac":
        agents_dir = Path.home() / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        label = f"com.jarvis.reminder.{task_name}"
        plist_path = agents_dir / f"{label}.plist"
        plist_path.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>{script_path}</string></array>
  <key>StartCalendarInterval</key><dict>
    <key>Year</key><integer>{target_dt.year}</integer>
    <key>Month</key><integer>{target_dt.month}</integer>
    <key>Day</key><integer>{target_dt.day}</integer>
    <key>Hour</key><integer>{target_dt.hour}</integer>
    <key>Minute</key><integer>{target_dt.minute}</integer>
  </dict>
</dict></plist>
""",
            encoding="utf-8",
        )
        result = subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
        return label if result.returncode == 0 else ""

    if shutil.which("systemd-run"):
        on_calendar = target_dt.strftime("%Y-%m-%d %H:%M:00")
        result = subprocess.run(
            ["systemd-run", "--user", f"--on-calendar={on_calendar}", f"--unit={task_name}", "--",
             sys.executable, str(script_path)],
            capture_output=True,
            text=True,
        )
        return task_name if result.returncode == 0 else ""
    return ""


@mcp.tool()
def reminder(date: str = "", time: str = "", message: str = "Reminder") -> str:
    """Schedule a desktop reminder on the host at a future date/time.

    ``date`` is ``YYYY-MM-DD`` and ``time`` is ``HH:MM`` (24h). The reminder
    fires on the machine running Jarvis.
    """
    date = (date or "").strip()
    time = (time or "").strip()
    message = (message or "Reminder").strip()

    if not date or not time:
        return "I need both a date and a time to set a reminder."
    try:
        target_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "I couldn't parse that date or time. Please use YYYY-MM-DD and HH:MM."
    if target_dt <= datetime.now():
        return "That time has already passed - I can't set a reminder in the past."

    os_name = _os_name()
    safe_msg = _sanitise(message)
    task_name = f"JARVISReminder_{target_dt.strftime('%Y%m%d_%H%M%S')}"
    try:
        script_path = _write_notify_script(task_name, safe_msg, os_name)
    except Exception as e:
        return f"Could not prepare the reminder script: {e}"

    try:
        if os_name == "windows":
            job_id = _schedule_windows(target_dt, task_name, script_path)
        else:
            job_id = _schedule_unix(target_dt, task_name, script_path, os_name)
    except Exception as e:
        script_path.unlink(missing_ok=True)
        return f"Something went wrong while scheduling the reminder: {e}"

    if not job_id:
        return "I couldn't register the reminder with the system scheduler."
    return f"Reminder set for {target_dt.strftime('%B %d at %I:%M %p')}."


# --------------------------------------------------------------------------- #
# youtube  (port scrapers; drop tkinter + browser-open)
# --------------------------------------------------------------------------- #
_YT_VIDEO_FILTER = "EgIQAQ%3D%3D"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url or "")
    return match.group(1) if match else None


def _scrape_first_video_url(query: str) -> str | None:
    search_url = (
        f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={_YT_VIDEO_FILTER}"
    )
    try:
        html = requests.get(search_url, headers=_HEADERS, timeout=10).text
        for vid in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html):
            if f"/shorts/{vid}" in html:
                continue
            return f"https://www.youtube.com/watch?v={vid}"
    except Exception:
        return None
    return None


def _scrape_video_info(video_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    info: dict = {}
    try:
        html = requests.get(url, headers=_HEADERS, timeout=12).text
        for key, pattern in [
            ("title", r'"title":\{"runs":\[\{"text":"([^"]+)"'),
            ("channel", r'"ownerChannelName":"([^"]+)"'),
            ("views", r'"viewCount":"(\d+)"'),
            ("duration", r'"lengthSeconds":"(\d+)"'),
        ]:
            m = re.search(pattern, html)
            if m:
                raw = m.group(1)
                if key == "views":
                    info[key] = f"{int(raw):,}"
                elif key == "duration":
                    secs = int(raw)
                    info[key] = f"{secs // 60}:{secs % 60:02d}"
                else:
                    info[key] = raw
    except Exception:
        return {}
    return info


def _scrape_trending(region: str = "US", max_results: int = 8) -> list[dict]:
    url = f"https://www.youtube.com/feed/trending?gl={region.upper()}"
    try:
        html = requests.get(url, headers=_HEADERS, timeout=12).text
        titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', html)
        channels = re.findall(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', html)
        results, seen = [], set()
        for i, title in enumerate(titles):
            if title in seen or len(title) < 5:
                continue
            seen.add(title)
            results.append(
                {"rank": len(results) + 1, "title": title,
                 "channel": channels[i] if i < len(channels) else "Unknown"}
            )
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def _get_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        tlist = YouTubeTranscriptApi.list_transcripts(video_id)
        langs = ["en", "es", "de", "fr", "pt", "it"]
        transcript = None
        try:
            transcript = tlist.find_manually_created_transcript(langs)
        except Exception:
            try:
                transcript = tlist.find_generated_transcript(langs)
            except Exception:
                for t in tlist:
                    transcript = t
                    break
        if transcript is None:
            return None
        return " ".join(e["text"] for e in transcript.fetch())
    except Exception:
        return None


@mcp.tool()
def youtube(action: str = "play", query: str = "", url: str = "", region: str = "US") -> str:
    """Interact with YouTube. action one of: play, get_info, summarize, trending.

    play -> resolves and returns the first video URL for ``query``.
    get_info/summarize -> need a ``url``. trending -> uses ``region``.
    """
    action = (action or "play").lower().strip()

    if action == "play":
        if not query.strip():
            return "Please tell me what you'd like to watch."
        found = _scrape_first_video_url(query.strip())
        if found:
            return f"Top result for '{query}': {found}"
        return (
            f"Couldn't resolve a single video; search here: "
            f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        )

    if action == "get_info":
        vid = _extract_video_id(url)
        if not vid:
            return "Please provide a valid YouTube URL."
        info = _scrape_video_info(vid)
        if not info:
            return "Could not retrieve video information."
        return "\n".join(f"{k.capitalize()}: {v}" for k, v in info.items())

    if action == "summarize":
        vid = _extract_video_id(url)
        if not vid:
            return "Please provide a valid YouTube URL to summarize."
        transcript = _get_transcript(vid)
        if not transcript:
            return "I couldn't retrieve a transcript for that video."
        system = (
            "You are Jarvis. Summarize this YouTube transcript: a one-sentence "
            "overview, then 3-5 key points. Be direct."
        )
        return _route_llm(transcript[:12000], system, task_type="reasoning", max_tokens=600)

    if action == "trending":
        rows = _scrape_trending(region=(region or "US").upper())
        if not rows:
            return f"Could not fetch trending videos for region {region}."
        lines = [f"Top trending in {region.upper()}:"]
        lines += [f"{r['rank']}. {r['title']} - {r['channel']}" for r in rows]
        return "\n".join(lines)

    return f"Unknown YouTube action: '{action}'. Try: play, get_info, summarize, trending."


# --------------------------------------------------------------------------- #
# flight_finder  (port: _parse_date / url builder / formatting; Playwright scrape)
# --------------------------------------------------------------------------- #
_CABIN_CODE = {"economy": "1", "premium": "2", "business": "3", "first": "4"}


def _parse_date(raw: str) -> str:
    raw = (raw or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    today = datetime.now()
    lower = raw.lower()
    if "today" in lower:
        return today.strftime("%Y-%m-%d")
    # Last resort: ask the router to normalize a fuzzy date expression.
    out = _route_llm(
        f"Today is {today.strftime('%Y-%m-%d')}. Convert this date expression to "
        f"YYYY-MM-DD: '{raw}'. Return ONLY the date string.",
        max_tokens=16,
    ).strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", out):
        return out
    return today.strftime("%Y-%m-%d")


def _build_google_flights_url(
    origin: str,
    destination: str,
    date: str,
    return_date: str | None = None,
    passengers: int = 1,
    cabin: str = "economy",
) -> str:
    cabin_code = _CABIN_CODE.get(cabin.lower(), "1")
    trip = f"Flights+from+{origin}+to+{destination}+on+{date}"
    if return_date:
        trip += f"+returning+{return_date}"
    return (
        f"https://www.google.com/travel/flights?q={trip}"
        f"&curr=USD&cabin={cabin_code}&adults={passengers}"
    )


def _scrape_flight_text(url: str) -> str:
    """Render the Google Flights page with Playwright and return its text."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)
            return page.inner_text("body")
        finally:
            browser.close()


def _parse_flights(raw_text: str, origin: str, destination: str, date: str) -> list[dict]:
    system = (
        "You are a flight data extraction expert. Extract flights from raw "
        "webpage text. Return ONLY valid JSON, no markdown."
    )
    prompt = (
        f"Extract up to 5 flights from {origin} to {destination} on {date} from this "
        f"Google Flights page text:\n\n{raw_text[:8000]}\n\n"
        'Return a JSON array: [{"airline":"...","departure":"HH:MM","arrival":"HH:MM",'
        '"duration":"Xh Ym","stops":0,"price":"...","currency":"USD"}]. '
        "If none, return []."
    )
    try:
        text = _route_llm(prompt, system, task_type="reasoning", max_tokens=700)
        text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        flights = json.loads(text)
        return flights if isinstance(flights, list) else []
    except Exception:
        return []


def _format_flights(flights: list[dict], origin: str, destination: str, date: str) -> str:
    if not flights:
        return f"I couldn't find any flights from {origin} to {destination} on {date}."
    lines = [f"Flights from {origin} to {destination} on {date}:"]
    for i, f in enumerate(flights[:5], 1):
        stops = f.get("stops", 0)
        stop_str = "non-stop" if stops == 0 else f"{stops} stop(s)"
        price = f"{f.get('price', '')} {f.get('currency', '')}".strip() or "price n/a"
        lines.append(
            f"{i}. {f.get('airline', 'Unknown')}, {f.get('departure', '--:--')}"
            f"->{f.get('arrival', '--:--')}, {stop_str}, {price}"
        )
    return "\n".join(lines)


@mcp.tool()
def flight_finder(
    origin: str = "",
    destination: str = "",
    date: str = "",
    return_date: str = "",
    passengers: int = 1,
    cabin: str = "economy",
) -> str:
    """Search flights between two airports/cities on a date (Google Flights scrape).

    ``date``/``return_date`` accept ``YYYY-MM-DD`` or fuzzy text. Returns the top
    options parsed from the live page.
    """
    origin = (origin or "").strip()
    destination = (destination or "").strip()
    if not origin or not destination:
        return "Please provide both origin and destination."
    if not (date or "").strip():
        return "Please provide a departure date."

    cabin = cabin if cabin in _CABIN_CODE else "economy"
    passengers = max(1, int(passengers or 1))
    date_norm = _parse_date(date)
    ret_norm = _parse_date(return_date) if return_date.strip() else None

    url = _build_google_flights_url(origin, destination, date_norm, ret_norm, passengers, cabin)
    try:
        raw = _scrape_flight_text(url)
    except Exception as e:
        return f"Flight search failed (could not load the page): {e}"
    if not raw:
        return "Could not retrieve flight data; the page may not have loaded."
    flights = _parse_flights(raw, origin, destination, date_norm)
    return _format_flights(flights, origin, destination, date_norm)


# --------------------------------------------------------------------------- #
# file_processor  (port the dispatch tree; _gemini_client -> _route_llm shim)
# --------------------------------------------------------------------------- #
class _LLMModel:
    """Adapter matching Mark-XL's ``model.generate_content(...)`` shape.

    Multimodal inputs (image/audio bytes) are dropped — Jarvis routes to text
    models, so only the text parts of a prompt are sent. Vision/transcription
    file types therefore degrade to a best-effort textual response.
    """

    def generate_content(self, content):
        if isinstance(content, (list, tuple)):
            text = " ".join(c for c in content if isinstance(c, str))
        else:
            text = str(content)

        class _R:
            pass

        r = _R()
        r.text = _route_llm(text, max_tokens=700)
        return r


def _gemini_client():
    return _LLMModel()


def _detect_type(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"}:
        return "image"
    if ext in {"mp4", "avi", "mov", "mkv", "webm", "m4v"}:
        return "video"
    if ext in {"mp3", "wav", "ogg", "m4a", "aac", "flac"}:
        return "audio"
    if ext in {"py", "js", "ts", "tsx", "java", "c", "cpp", "go", "rs", "rb",
               "php", "sh", "sql", "html", "css"}:
        return "code"
    if ext in {"zip", "tar", "gz", "bz2", "xz"}:
        return "archive"
    if ext == "pdf":
        return "pdf"
    if ext in ("docx", "doc"):
        return "docx"
    if ext in ("txt", "md", "rst", "log"):
        return "text"
    if ext in ("csv", "tsv"):
        return "csv"
    if ext in ("xlsx", "xls"):
        return "excel"
    if ext == "json":
        return "json"
    return "unknown"


def _output_path(src: Path, suffix: str, new_ext: str | None = None) -> Path:
    ext = new_ext or src.suffix
    return src.parent / f"{src.stem}_{suffix}{ext}"


def _process_text_doc(path: Path, file_type: str, action: str, params: dict) -> str:
    if file_type == "docx":
        try:
            from docx import Document

            content = "\n".join(p.text for p in Document(path).paragraphs)
        except ImportError:
            return "python-docx not installed. Run: pip install python-docx"
    else:
        content = path.read_text(encoding="utf-8", errors="ignore")

    if not content.strip():
        return "File appears to be empty."
    if action == "word_count":
        return f"{len(content.split())} words, {len(content)} characters."
    if action == "extract_text":
        return content[:2000]

    prompt_map = {
        "summarize": f"Summarize this document concisely:\n\n{content[:40000]}",
        "analyze": f"Analyze this document:\n\n{content[:40000]}",
        "reformat": f"Reformat this text with clean structure:\n\n{content[:40000]}",
        "fix": f"Fix grammar and style in this text:\n\n{content[:40000]}",
    }
    prompt = prompt_map.get(action) or f"{params.get('instruction', action)}\n\n{content[:40000]}"
    return _gemini_client().generate_content(prompt).text


def _process_json(path: Path, action: str, params: dict) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Invalid JSON: {e}"
    if action == "validate":
        return f"Valid JSON. Type: {type(data).__name__}."
    if action == "format":
        out = _output_path(path, "formatted", ".json")
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"Formatted JSON saved: {out.name}"
    preview = json.dumps(data, indent=2, ensure_ascii=False)[:8000]
    return _gemini_client().generate_content(f"Task: {action} this JSON:\n{preview}").text


def _process_code(path: Path, action: str, params: dict) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")
    ext = path.suffix.lstrip(".")
    if action == "info":
        return f"{content.count(chr(10))} lines, {len(content.split())} words."
    prompt_map = {
        "explain": f"Explain this {ext} code:\n\n{content[:30000]}",
        "review": f"Review this {ext} code for bugs and improvements:\n\n{content[:30000]}",
        "fix": f"Fix bugs in this {ext} code:\n\n{content[:30000]}",
        "document": f"Document this {ext} code:\n\n{content[:30000]}",
        "summarize": f"Summarize what this {ext} code does:\n\n{content[:30000]}",
    }
    prompt = prompt_map.get(action) or f"{action}\n\n{content[:30000]}"
    return _gemini_client().generate_content(prompt).text


@mcp.tool()
def file_processor(file_path: str = "", action: str = "", instruction: str = "") -> str:
    """Process a file on the server (summarize/analyze/convert/validate, etc.).

    ``file_path`` must exist on the machine running Jarvis. The handler is chosen
    by file type; ``action`` selects the operation (default per type).
    """
    file_path = (file_path or "").strip()
    if not file_path:
        return "No file path provided."
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return f"File not found: {file_path}"

    file_type = _detect_type(path)
    action = (action or "").lower().strip()
    params = {"instruction": instruction}

    handlers = {
        "text": lambda: _process_text_doc(path, "text", action or "summarize", params),
        "docx": lambda: _process_text_doc(path, "docx", action or "summarize", params),
        "json": lambda: _process_json(path, action or "analyze", params),
        "code": lambda: _process_code(path, action or "explain", params),
    }
    handler = handlers.get(file_type)
    if handler is None:
        return (
            f"File type '{file_type}' isn't supported by the web-safe processor "
            f"(supported: text, docx, json, code)."
        )
    try:
        return handler() or "Done."
    except Exception as e:
        return f"Processing failed: {e}"


if __name__ == "__main__":
    mcp.run()

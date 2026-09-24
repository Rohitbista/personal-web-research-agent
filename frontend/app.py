"""
frontend/app.py
───────────────
Streamlit UI for the Personal Web Research Agent.
Connects to the FastAPI backend running on localhost:8000.

Performance notes
─────────────────
• Completed jobs are cached for 1 hour  — the report never changes once done.
• Session list is cached for 30 s       — avoids re-fetching on every rerun.
• Session detail is cached for 15 s     — titles / history change rarely.
• Active (running/queued) jobs are never cached so SSE + polling stay live.
• The sidebar no longer fires a separate /sessions call when the cache is warm.
"""

import json
import time

import requests
import sseclient
import streamlit as st

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="Web Research Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Tiny HTTP helpers ────────────────────────────────────────────────────────

def api_get(path: str, **kwargs):
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=10, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach backend. Is the FastAPI server running on port 8000?")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None


def api_post(path: str, json_body: dict | None = None, **kwargs):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=json_body, timeout=10, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach backend. Is the FastAPI server running on port 8000?")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None


def api_patch(path: str, json_body: dict):
    try:
        r = requests.patch(f"{BASE_URL}{path}", json=json_body, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach backend.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None


# ─── Cached fetchers ──────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def _cached_sessions() -> list:
    """Fetch the session list. Cached for 30 s."""
    try:
        r = requests.get(f"{BASE_URL}/sessions", timeout=10)
        r.raise_for_status()
        return r.json().get("sessions", [])
    except Exception:
        return []


@st.cache_data(ttl=15, show_spinner=False)
def _cached_session_detail(session_id: str) -> dict | None:
    """Fetch a single session's detail. Cached for 15 s."""
    try:
        r = requests.get(f"{BASE_URL}/sessions/{session_id}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_completed_job(job_id: str) -> dict | None:
    """
    Fetch a job and cache it for 1 hour — but ONLY when it has reached a
    terminal state (completed / failed / cancelled).  Active jobs are
    intentionally not cached so live polling keeps working.
    """
    try:
        r = requests.get(f"{BASE_URL}/research/{job_id}", timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("status") in ("completed", "failed", "cancelled"):
            return data
        return None          # non-terminal → caller must do a live fetch
    except Exception:
        return None


def _invalidate_session_cache():
    """Clear session-related caches after mutations (new job, rename, …)."""
    _cached_sessions.clear()
    _cached_session_detail.clear()


# ─── Session state defaults ───────────────────────────────────────────────────

def _init_state():
    defaults = {
        "active_session_id": None,
        "active_job_id": None,
        "streaming_log": [],   # SSE lines for the current job
        "job_status": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.title("🔍 Research Agent")
        st.divider()

        if st.button("＋  New Session", use_container_width=True, type="primary"):
            st.session_state.active_session_id = None
            st.session_state.active_job_id = None
            st.session_state.streaming_log = []
            st.session_state.job_status = None
            st.rerun()

        st.caption("Past Sessions")

        if st.button("↻  Refresh", use_container_width=True):
            _invalidate_session_cache()
            st.rerun()

        # Single cached fetch — no extra HTTP call on every rerun
        sessions = _cached_sessions()

        if not sessions:
            st.info("No sessions yet. Start your first research above!")
        else:
            for sess in sessions:
                label = f"📂 {sess['title'][:38]}{'…' if len(sess['title']) > 38 else ''}"
                is_active = sess["session_id"] == st.session_state.active_session_id
                btn_type = "primary" if is_active else "secondary"
                if st.button(
                    label,
                    key=f"sess_{sess['session_id']}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    st.session_state.active_session_id = sess["session_id"]
                    st.session_state.active_job_id = None
                    st.session_state.streaming_log = []
                    st.session_state.job_status = None
                    st.rerun()


# ─── Main area ────────────────────────────────────────────────────────────────

def render_main():
    session_id = st.session_state.active_session_id

    # ── Existing session view ─────────────────────────────────────────────────
    if session_id:
        # Cached — no round-trip on most reruns
        data = _cached_session_detail(session_id)
        if not data:
            st.error("Session not found.")
            return

        col_title, col_rename = st.columns([4, 1])
        with col_title:
            st.header(data["title"])
        with col_rename:
            with st.popover("✏️ Rename"):
                new_title = st.text_input("New title", value=data["title"], key="rename_input")
                if st.button("Save", key="rename_save"):
                    result = api_patch(f"/sessions/{session_id}/rename", {"title": new_title})
                    if result:
                        _invalidate_session_cache()
                        st.rerun()

        st.caption(f"Session ID: `{session_id}`")
        st.divider()

        # Research history — already inside the cached session response
        history = data.get("research_history", [])
        if history:
            with st.expander(f"📜 History ({len(history)} jobs)", expanded=False):
                for job in reversed(history):
                    status_emoji = {
                        "completed": "✅",
                        "failed": "❌",
                        "cancelled": "🚫",
                        "running": "⏳",
                        "queued": "🕐",
                    }.get(job["status"], "❓")
                    if st.button(
                        f"{status_emoji} {job['query'][:70]}",
                        key=f"job_{job['research_id']}",
                        use_container_width=True,
                    ):
                        st.session_state.active_job_id = job["research_id"]
                        st.session_state.streaming_log = []
                        st.rerun()

        st.divider()

        # Follow-up query input
        _render_query_form(session_id=session_id)

    else:
        # ── New session ───────────────────────────────────────────────────────
        st.header("New Research")
        st.markdown("Ask anything — the agent will search the web and compile a report for you.")
        _render_query_form(session_id=None)

    st.divider()

    # ── Job display ───────────────────────────────────────────────────────────
    job_id = st.session_state.active_job_id
    if job_id:
        _render_job(job_id)


def _render_query_form(session_id: str | None):
    with st.form("query_form", clear_on_submit=True):
        query = st.text_area(
            "Research query",
            placeholder="e.g. What are the latest developments in quantum computing?",
            height=100,
        )
        submitted = st.form_submit_button("🚀 Start Research", type="primary", use_container_width=True)

    if submitted and query.strip():
        body = {"query": query.strip()}
        if session_id:
            body["session_id"] = session_id

        result = api_post("/research", json_body=body)
        if result:
            st.session_state.active_session_id = result["session_id"]
            st.session_state.active_job_id = result["research_id"]
            st.session_state.streaming_log = []
            st.session_state.job_status = "queued"
            _invalidate_session_cache()
            st.rerun()
    elif submitted:
        st.warning("Please enter a query before starting.")


def _render_job(job_id: str):
    # ── Try the 1-hour cache first (terminal jobs only) ───────────────────────
    data = _cached_completed_job(job_id)

    # Cache miss means the job is still active — do a live fetch
    if data is None:
        data = api_get(f"/research/{job_id}")
    if not data:
        return

    status = data["status"]
    st.session_state.job_status = status

    st.subheader(f"📋 {data['query']}")
    st.caption(f"Job ID: `{job_id}`  ·  Status: **{status}**")

    # Cancel button while running
    if status in ("queued", "running"):
        if st.button("🛑 Cancel", key="cancel_btn"):
            api_post(f"/research/{job_id}/cancel")
            # Bust the cache so the cancelled status shows immediately
            _cached_completed_job.clear()
            st.rerun()

    # ── SSE live stream (only for active jobs) ────────────────────────────────
    if status in ("queued", "running"):
        _stream_events(job_id)

        # Poll until done, then refresh
        with st.spinner("Researching… (page auto-refreshes when done)"):
            _poll_until_done(job_id)

        # Job just finished — bust the session cache so history updates
        _invalidate_session_cache()
        st.rerun()

    # ── Show logged events (if any captured earlier) ──────────────────────────
    if st.session_state.streaming_log:
        with st.expander("🔎 Agent activity log", expanded=False):
            for line in st.session_state.streaming_log:
                st.text(line)

    # ── Final report ──────────────────────────────────────────────────────────
    if status == "completed" and data.get("report"):
        st.success("Research complete!")
        st.markdown("---")
        st.markdown(data["report"])

        st.download_button(
            label="⬇️  Download report (.md)",
            data=data["report"],
            file_name=f"report_{job_id[:8]}.md",
            mime="text/markdown",
        )

    elif status == "failed":
        st.error(f"Research failed: {data.get('error', 'Unknown error')}")

    elif status == "cancelled":
        st.warning("Research was cancelled.")


def _stream_events(job_id: str):
    """
    Consume the SSE stream for *this* job and store lines in session state.
    Stops after seeing a terminal event or 50 events, whichever comes first,
    so Streamlit's script runner is never blocked for long.
    """
    log = st.session_state.streaming_log
    placeholder = st.empty()

    try:
        with requests.get(
            f"{BASE_URL}/research/{job_id}/stream",
            stream=True,
            timeout=60,
        ) as resp:
            client = sseclient.SSEClient(resp)
            for i, event in enumerate(client.events()):
                if event.data:
                    try:
                        payload = json.loads(event.data)
                        msg_type = payload.get("type", "info")
                        msg_data = payload.get("data", event.data)
                    except json.JSONDecodeError:
                        msg_type = "info"
                        msg_data = event.data

                    emoji = {
                        "searching": "🔍",
                        "fetching": "📥",
                        "thinking": "🧠",
                        "writing": "✍️",
                        "completed": "✅",
                        "error": "❌",
                    }.get(msg_type, "▸")

                    line = f"{emoji} [{msg_type}] {msg_data}"
                    log.append(line)
                    placeholder.text(line)

                    if msg_type in ("completed", "error") or i >= 50:
                        break
    except Exception:
        # Stream not available (server restarted, etc.) — fall through to polling
        pass


def _poll_until_done(job_id: str, max_wait: int = 300):
    """Poll /research/{job_id} every 3 s until terminal state or timeout."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        data = api_get(f"/research/{job_id}")
        if data and data["status"] in ("completed", "failed", "cancelled"):
            return
        time.sleep(3)


# ─── Entry point ─────────────────────────────────────────────────────────────

render_sidebar()
render_main()
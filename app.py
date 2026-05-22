"""
app.py — Streamlit chat UI for the Financial Research AI agent.

This is the single entry point for the application. Run with:
    streamlit run app.py

How it works:
  1. On first load, creates a FinancialAgent (once per browser session).
  2. The user types a question in the chat input at the bottom.
  3. The agent calls whichever data tools it needs (stock data, news, etc.)
     and returns a formatted response.
  4. Conversation history is kept in session_state so the agent remembers
     what was asked earlier in the same session.
  5. When a single stock snapshot is fetched, a 1-month price chart is
     rendered below the response using Plotly.
"""

from pathlib import Path

import streamlit as st

# ─── Page config MUST be the first Streamlit call ─────────────────────────────
st.set_page_config(
    page_title="Financial Research AI",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="expanded",
)


# ─── Paths ────────────────────────────────────────────────────────────────────
_PROJECT_ROOT   = Path(__file__).parent
_WATCHLIST_PATH = _PROJECT_ROOT / "config" / "watchlist.txt"


# ─── Price chart helper ───────────────────────────────────────────────────────

def _price_chart(ticker: str):
    """
    Fetch 1-month daily closing prices for `ticker` and return a Plotly figure.

    Returns None silently if the fetch fails or produces insufficient data —
    the chart is optional eye-candy and should never crash the UI.
    """
    try:
        import yfinance as yf
        import plotly.graph_objects as go

        hist = yf.Ticker(f"{ticker}.NS").history(period="1mo")
        if hist.empty or len(hist) < 3:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist["Close"],
            mode="lines",
            line=dict(color="#2196F3", width=2),
            fill="tozeroy",
            fillcolor="rgba(33,150,243,0.08)",
            name="Close",
            hovertemplate="₹%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text=f"{ticker} — 1 Month", font=dict(size=14)),
            height=260,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(showgrid=False, title=None),
            yaxis=dict(title="₹", showgrid=True, gridcolor="#f0f0f0"),
            plot_bgcolor="white",
            paper_bgcolor="white",
            showlegend=False,
            hovermode="x unified",
        )
        return fig
    except Exception:
        return None


# ─── Helper: load watchlist for the sidebar ───────────────────────────────────

def _load_watchlist_tickers() -> list[str]:
    """Read config/watchlist.txt and return ticker symbols for the sidebar."""
    if not _WATCHLIST_PATH.exists():
        return []
    tickers = []
    for line in _WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        ticker = stripped.split("#")[0].strip().upper()
        if ticker:
            tickers.append(ticker)
    return tickers


# ─── Welcome message shown on first load ──────────────────────────────────────

def _welcome_message() -> str:
    return """\
Namaste! 👋 Main aapka **Indian market research assistant** hoon.

Mujhse yeh sab pooch sakte ho:

**📊 Stock Data**
- `Reliance ka snapshot dikhao`
- `Compare TCS and Infosys`
- `HDFCBANK ka PE ratio kya hai?`

**📈 Valuation**
- `WIPRO ki intrinsic value kya hai?`
- `Is TCS overvalued?`

**📰 Market News**
- `Aaj market mein kya hua?`
- `TATAMOTORS ke baare mein koi news hai?`

**🔍 Screener**
- `Low PE stocks dikhao (PE under 15)`
- `IT stocks with ROE above 20%`

**📋 Watchlist**
- `Meri watchlist dikhao`
- `WIPRO watchlist mein add karo`

---
*Saari data live sources se aati hai — Yahoo Finance aur Indian news RSS feeds.*

⚠️ Research tool hai, financial advice nahi. Decisions aapke hain.
"""


# ─── Session state initialisation ─────────────────────────────────────────────

from data.session import load_latest_session, save_session

def _init_session() -> None:
    """Set up all session_state keys on first load."""
    if "messages" not in st.session_state:
        # Try to load existing session
        loaded = load_latest_session()
        if loaded:
            st.session_state.messages, st.session_state.gemini_history = loaded
        else:
            st.session_state.messages = [
                {"role": "assistant", "content": _welcome_message()}
            ]
            st.session_state.gemini_history = []

    if "gemini_history" not in st.session_state:
        st.session_state.gemini_history = []

    if "agent" not in st.session_state:
        st.session_state.agent = None
        st.session_state.agent_error = None
        try:
            from agent.brain import FinancialAgent

            st.session_state.agent = FinancialAgent()
        except EnvironmentError as exc:
            st.session_state.agent_error = str(exc)
        except Exception as exc:
            st.session_state.agent_error = (
                f"Agent failed to start: {type(exc).__name__}: {exc}"
            )


def _reset_chat() -> None:
    """Clear conversation history and restore the welcome message."""
    st.session_state.messages = [
        {"role": "assistant", "content": _welcome_message()}
    ]
    st.session_state.gemini_history = []
    # Save the fresh state
    save_session(st.session_state.messages, st.session_state.gemini_history)


# ─── Initialise session before building any UI ────────────────────────────────
_init_session()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧠 Financial Research AI")
    st.caption("Indian Market Research Assistant")

    st.divider()

    if st.button("🗑️ New Chat", use_container_width=True):
        _reset_chat()
        st.rerun()

    st.divider()

    st.subheader("📋 Your Watchlist")
    tickers = _load_watchlist_tickers()
    if tickers:
        for ticker in tickers:
            st.markdown(f"- `{ticker}`")
    else:
        st.caption("Watchlist is empty. Ask the agent to add stocks!")

    st.divider()

    if st.session_state.agent_error:
        st.error("⚠️ Agent offline")
        with st.expander("What went wrong?"):
            st.code(st.session_state.agent_error)
            st.markdown(
                "**To fix:** Add `GEMINI_API_KEY=your_key_here` to your `.env` file, "
                "then refresh this page.\n\n"
                "Get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey)."
            )
    else:
        st.success("✅ Agent ready")

    st.divider()

    st.caption(
        "⚠️ **Research tool, not financial advice.**  \n"
        "All data is from public sources.  \n"
        "Decisions are entirely yours."
    )


# ─── Main chat area ───────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── Chat input ────────────────────────────────────────────────────────────────

agent_ready = st.session_state.agent is not None

prompt = st.chat_input(
    placeholder="Kuch bhi poochho... (Hindi ya English dono chalega)",
    disabled=not agent_ready,
)

if prompt:
    # ── 1. Show and store the user's message ──────────────────────────────────
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ── 2. Get the agent's response ───────────────────────────────────────────
    with st.chat_message("assistant"):
        # UI elements for progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def progress_callback(current, total, ticker):
            pct = current / total
            progress_bar.progress(pct)
            status_text.text(f"Fetching {current}/{total}: {ticker}...")
            
        st.session_state.agent.set_progress_callback(progress_callback)

        with st.spinner("Soch raha hoon... 🤔"):
            try:
                response_text, updated_history = st.session_state.agent.chat(
                    prompt,
                    st.session_state.gemini_history,
                )
                st.session_state.gemini_history = updated_history
            except Exception as exc:
                response_text = (
                    f"❌ **Kuch unexpected ho gaya** (`{type(exc).__name__}`).  \n"
                    f"Please try again.  \n\n"
                    f"*Detail: {exc}*"
                )
        
        # Clear progress elements when done
        progress_bar.empty()
        status_text.empty()

        # Render the response text
        st.markdown(response_text)

        # ── Price chart (single-stock snapshot only) ──────────────────────────
        # agent.last_chart_ticker is set by brain.py when get_stock_snapshot runs.
        # It's None for comparisons, screener results, news, etc. — so the chart
        # only appears when the user asked about one specific stock.
        chart_ticker = st.session_state.agent.last_chart_ticker
        if chart_ticker:
            fig = _price_chart(chart_ticker)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

    # ── 3. Store the assistant's response in display history ──────────────────
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )
    
    # Save session to disk so it survives page refreshes
    save_session(st.session_state.messages, st.session_state.gemini_history)

    # ── 4. Refresh the sidebar watchlist after any watchlist edits ────────────
    watchlist_keywords = ["watchlist", "add", "remove", "hata", "daal", "jod"]
    if any(kw in prompt.lower() for kw in watchlist_keywords):
        st.rerun()

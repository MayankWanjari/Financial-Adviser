"""agent/brain.py — Gemini-powered financial research agent with function calling.

How it works:
  1. User sends a message (e.g. "RELIANCE ka PE kya hai?")
  2. Gemini reads the message and decides which tool(s) to call
  3. We execute those tools against real data (yfinance, RSS feeds, etc.)
  4. We send the results back to Gemini
  5. Gemini formats a natural-language answer and returns it to the user
  6. Steps 2–5 may repeat if Gemini wants to call multiple tools

The FinancialAgent class is the single entry point. app.py creates one instance
and calls agent.chat() for every user message.

Architecture (after P1 refactor):
  - Tool declarations live in agent/tools.py
  - Tool dispatch logic lives in agent/dispatch.py
  - This file only has the FinancialAgent class (init + chat loop)
"""

import os
import time
from datetime import datetime, timezone as _tz

import google.generativeai as genai
from dotenv import load_dotenv

from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_DECLARATIONS
from agent.dispatch import handle_tool_call, _make_json_safe

# ─── Retry configuration ──────────────────────────────────────────────────────
# Retry on transient server errors (503, timeout). Do NOT retry 429 — quota
# errors won't resolve within seconds.
_RETRYABLE_PHRASES = ("503", "service unavailable", "timeout", "temporarily unavailable")
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2  # seconds; doubles on each attempt (2s, 4s, 8s)


def _send_with_retry(chat_session, message, max_retries: int = _MAX_RETRIES):
    """
    Wrap chat_session.send_message() with exponential backoff for transient failures.

    Retries on 503 / timeout errors only. Quota errors (429) and other client
    errors are re-raised immediately so the caller can surface them to the user.
    """
    for attempt in range(max_retries + 1):
        try:
            return chat_session.send_message(message)
        except Exception as exc:
            exc_str = str(exc).lower()
            is_retryable = any(phrase in exc_str for phrase in _RETRYABLE_PHRASES)
            if not is_retryable or attempt == max_retries:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            time.sleep(delay)


class FinancialAgent:
    """
    Conversational research agent for Indian equity markets.

    Wraps Google Gemini with function calling. The agent decides which data
    tools to call based on the user's question, executes them against real
    data sources (yfinance, RSS feeds, Gemini news analysis), and returns a
    natural-language answer.

    Usage:
        agent = FinancialAgent()
        response, history = agent.chat("RELIANCE ka PE kya hai?", history=[])
        response, history = agent.chat("TCS se compare karo", history=history)

    The `history` list is the conversation memory. Pass the list returned
    from the previous call to maintain context across turns.
    """

    def __init__(self) -> None:
        """
        Load the API key from .env and create the Gemini model.

        The model is created once here and reused across all chat() calls.
        It has the tool declarations and system prompt "baked in".

        Raises:
            EnvironmentError: If GEMINI_API_KEY is not set in the .env file.
        """
        # Set by dispatch.handle_tool_call when get_stock_snapshot runs; reset each turn.
        # app.py reads this to decide whether to render a price chart.
        self.last_chart_ticker: str | None = None
        
        # Optional callback for long-running tools (screener, scorer)
        # Signature: def callback(current: int, total: int, ticker: str)
        self.progress_callback = None

        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY not found in .env file.\n"
                "Get a free key at https://aistudio.google.com/app/apikey\n"
                "Then add GEMINI_API_KEY=your_key_here to your .env file."
            )

        genai.configure(api_key=api_key)

        # The model is configured with:
        #   - tools: the data functions Gemini can call (from agent/tools.py)
        #   - system_instruction: the agent's personality and rules (from prompts.py)
        self._model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools=[TOOL_DECLARATIONS],
            system_instruction=SYSTEM_PROMPT,
        )

    def set_progress_callback(self, cb) -> None:
        """
        Set a callback for long-running operations (like screening Nifty 50).
        The callback should accept (current: int, total: int, ticker: str).
        """
        self.progress_callback = cb

    # ── Main chat interface ────────────────────────────────────────────────────

    def chat(self, user_message: str, history: list) -> tuple[str, list]:
        """
        Send one user message to the agent and get a response back.

        Handles the full Gemini function-calling loop internally:
            user message
              → Gemini (picks tools)
              → tool execution (real data)
              → Gemini (may pick more tools, or write final answer)
              → response text

        Args:
            user_message: The user's question or message as a plain string.
            history:      Prior conversation as a list of Gemini Content objects.
                          Pass [] for the first message in a new conversation.
                          Pass the history returned by the previous chat() call
                          to keep context alive across turns.

        Returns:
            (response_text, updated_history):
              response_text   — Gemini's answer as a plain string.
              updated_history — Updated history to pass into the next chat() call.
                                Includes this turn's messages, tool calls, and results.
        """
        # Reset per-turn state before each new message
        self.last_chart_ticker = None

        try:
            # Seed the chat with the existing history so Gemini remembers the
            # conversation context. Each call creates a new session but passes
            # the prior turns in so they're visible to the model.
            chat_session = self._model.start_chat(history=history)

            # Send the user's message — Gemini may respond with text OR a tool call
            response = _send_with_retry(chat_session, user_message)

            # ── Function calling loop ─────────────────────────────────────────
            # Gemini can call tools multiple times before giving a text answer.
            # Example: "Compare RELIANCE news AND show me the PE" → two tool calls.
            # We keep looping until we get a plain text response.
            max_rounds = 5  # Safety cap — prevents runaway loops on edge cases

            for _ in range(max_rounds):
                # Check this response for function call parts
                try:
                    parts = response.candidates[0].content.parts
                except (IndexError, AttributeError):
                    break  # No candidates — response was blocked or malformed

                fc_parts = [
                    p for p in parts
                    if hasattr(p, "function_call") and p.function_call.name
                ]

                if not fc_parts:
                    break  # No tool calls — Gemini has a text answer ready

                # Execute every tool call in this response, collect results
                fn_response_parts = []
                for part in fc_parts:
                    raw_result = handle_tool_call(part.function_call, self)
                    # Ensure the result dict is JSON-safe (converts datetimes, etc.)
                    safe_result = _make_json_safe(raw_result)
                    fn_response_parts.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=part.function_call.name,
                                response=safe_result,
                            )
                        )
                    )

                # Send all results back to Gemini in a single "function results" turn
                response = _send_with_retry(
                    chat_session,
                    genai.protos.Content(
                        parts=fn_response_parts,
                        role="user",
                    ),
                )

            # Extract the final text answer
            try:
                response_text = response.text
                if not response_text or not response_text.strip():
                    response_text = (
                        "I got the data but couldn't format a response. "
                        "Please try rephrasing your question."
                    )
            except (ValueError, AttributeError):
                # response.text raises if the response is a blocked/empty candidate.
                # This can happen when tool results are too large or trigger safety filters.
                # Try to extract the finish_reason for debugging.
                try:
                    reason = response.candidates[0].finish_reason.name if response.candidates else "unknown"
                except Exception:
                    reason = "unknown"
                response_text = (
                    f"⚠️ Gemini ka response empty aa gaya (reason: {reason}). "
                    "Yeh usually tab hota hai jab data bahut zyada ho. "
                    "Try karo: 'Score RELIANCE' ya 'Top 5 opportunities dikhao' — "
                    "specific question better kaam karta hai."
                )

            # Return the text and the full updated history (including tool call turns).
            # The caller (app.py) stores this and passes it back on the next message.
            return response_text, list(chat_session.history)

        except Exception as exc:
            # Last-resort catch — keeps the Streamlit app alive even if something
            # unexpected happens deep in the Gemini client or data layer.
            exc_str = str(exc)
            is_quota = (
                "429" in exc_str
                or "quota" in exc_str.lower()
                or "resource_exhausted" in exc_str.lower()
            )
            is_network = (
                "connection" in exc_str.lower()
                or "timeout" in exc_str.lower()
                or "ssl" in exc_str.lower()
                or "name resolution" in exc_str.lower()
            )
            if is_quota:
                hours_left = (8 - datetime.now(_tz.utc).hour) % 24 or 24
                error_text = (
                    f"⚠️ **Gemini quota exceeded.**  \n"
                    f"Aapne aaj ka free-tier limit hit kar liya.  \n"
                    f"Daily quota ~{hours_left} ghante mein reset hoti hai (midnight Pacific Time).  \n"
                    f"Tab tak: thoda wait karo, ya 1 minute baad retry karo (per-minute limit ke liye)."
                )
            elif is_network:
                error_text = (
                    "🌐 **No internet / network error.**  \n"
                    "Internet connection check karo aur dobara try karo.  \n"
                    f"*Detail: {exc}*"
                )
            else:
                error_text = (
                    f"❌ **Kuch unexpected ho gaya** (`{type(exc).__name__}`).  \n"
                    f"Please try again.  \n\n"
                    f"*Detail: {exc}*"
                )
            return error_text, history

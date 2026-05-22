"""agent/tools.py — Gemini function-calling tool declarations.

Each FunctionDeclaration tells Gemini: name, description, and parameter schema.
Gemini reads the descriptions to decide WHICH tool to call for a given user question.
Good descriptions are critical — vague descriptions lead to Gemini picking the wrong tool.

To add a new tool:
  1. Add a FunctionDeclaration in this file
  2. Add the dispatch case in agent/dispatch.py
"""

import google.generativeai as genai


# ─── Tool declarations (Gemini function calling schema) ───────────────────────
#
# Each FunctionDeclaration has:
#   name        — identifier Gemini uses in function_call messages
#   description — plain English; Gemini reads this to decide when to use the tool
#   parameters  — JSON Schema for the tool's inputs
#
TOOL_DECLARATIONS = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="get_stock_snapshot",
            description=(
                "Get live price, valuation (PE, PB), quality metrics (ROE, operating "
                "margin, net margin), and leverage (D/E ratio) data for any NSE-listed "
                "Indian stock. Use for questions like 'What is RELIANCE's PE?' or "
                "'Show me HDFCBANK fundamentals'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description=(
                            "NSE ticker symbol without .NS suffix. "
                            "Examples: RELIANCE, TCS, HDFCBANK, INFY, TATAMOTORS"
                        ),
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="compare_stocks",
            description=(
                "Compare multiple NSE stocks side-by-side on price, PE, PB, ROE, "
                "operating margin, net margin, D/E ratio, and dividend yield. "
                "Use when the user asks to compare two or more companies, e.g. "
                "'Compare TCS and Infosys' or 'RELIANCE vs ONGC dikha do'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "tickers": genai.protos.Schema(
                        type=genai.protos.Type.ARRAY,
                        items=genai.protos.Schema(type=genai.protos.Type.STRING),
                        description=(
                            "List of NSE ticker symbols to compare. "
                            "Minimum 2, e.g. ['TCS', 'INFY', 'WIPRO']"
                        ),
                    )
                },
                required=["tickers"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_market_news",
            description=(
                "Fetch today's Indian market news and return an AI-analyzed briefing "
                "covering top stories, sector impact, global context (USD/INR, oil, US Fed), "
                "FII/DII flows, earnings highlights, and watchlist mentions. "
                "Use for broad questions like 'Aaj kya hua markets mein?' or "
                "'Give me today's market briefing'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_stock_news",
            description=(
                "Get recent news headlines specifically about one stock. "
                "Use when the user asks about news for a particular company, e.g. "
                "'TATAMOTORS ke baare mein kya news hai?' or 'Any news on Infosys?'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol to search news for, e.g. TATAMOTORS",
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_watchlist",
            description=(
                "Show the user's current stock watchlist — the list of NSE tickers "
                "they are tracking. Use when asked 'Meri watchlist dikha' or "
                "'What's on my watchlist?'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="add_to_watchlist",
            description=(
                "Add a stock ticker to the user's watchlist. "
                "Use when asked 'Add WIPRO to my watchlist' or 'ONGC watchlist mein daal do'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol to add, e.g. WIPRO",
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="remove_from_watchlist",
            description=(
                "Remove a stock ticker from the user's watchlist. "
                "Use when asked 'Remove TCS from watchlist' or 'TCS hata do watchlist se'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol to remove, e.g. TCS",
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="calculate_valuation",
            description=(
                "Calculate intrinsic value estimates for a stock using the Graham Number "
                "(Benjamin Graham's classic formula) and PE-based fair value. Shows margin "
                "of safety — how far the current price is from the estimated intrinsic value. "
                "Use for questions like 'RELIANCE ki intrinsic value kya hai?', "
                "'Is TCS overvalued?', or 'Show me valuation analysis for HDFCBANK'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. RELIANCE",
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="screen_stocks",
            description=(
                "Screen Indian stocks by fundamental criteria. Scans Nifty 50, "
                "Nifty Midcap 150, or both universes. Filters by PE, ROE, D/E, "
                "market cap, and sector. "
                "WARNING: this takes 1-2 minutes for Nifty 50 — always tell the user "
                "to wait before calling this tool. Use for questions like "
                "'Low PE stocks dikhao', 'Find IT stocks with ROE above 20%', "
                "'Screen midcap stocks with D/E below 0.5'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "pe_max": genai.protos.Schema(
                        type=genai.protos.Type.NUMBER,
                        description="Maximum trailing P/E ratio, e.g. 20 means PE <= 20",
                    ),
                    "pe_min": genai.protos.Schema(
                        type=genai.protos.Type.NUMBER,
                        description="Minimum trailing P/E ratio, e.g. 5",
                    ),
                    "roe_min": genai.protos.Schema(
                        type=genai.protos.Type.NUMBER,
                        description="Minimum Return on Equity in %, e.g. 15 means ROE >= 15%",
                    ),
                    "de_max": genai.protos.Schema(
                        type=genai.protos.Type.NUMBER,
                        description="Maximum debt-to-equity ratio, e.g. 1.0 means D/E <= 1x",
                    ),
                    "market_cap_min": genai.protos.Schema(
                        type=genai.protos.Type.NUMBER,
                        description="Minimum market cap in ₹ Crore, e.g. 50000 means >= ₹50,000 Cr",
                    ),
                    "sector": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description=(
                            "Sector to filter by (case-insensitive substring match). "
                            "Examples: 'Technology', 'Financial Services', 'Energy'"
                        ),
                    ),
                    "universe": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description=(
                            "Which stock universe to scan. "
                            "'nifty50' — large-cap Nifty 50 stocks (default, ~1-2 min). "
                            "'midcap150' — Nifty Midcap 150 stocks (~3-4 min). "
                            "'both' — Nifty 50 + Midcap 150 combined (~5-6 min). "
                            "Use 'midcap150' when the user asks about midcap stocks."
                        ),
                    ),
                },
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="score_stock",
            description=(
                "Score a stock's fundamental attractiveness on a 0-100 scale across "
                "6 criteria: value (PE), quality (ROE), safety (debt), margin of safety "
                "(Graham Number), profitability (net margin), and dividend yield. "
                "Higher score = more fundamentally attractive by these metrics. "
                "Use for questions like 'RELIANCE ka score kya hai?', "
                "'Rate HDFCBANK fundamentals', or 'Is TCS a quality stock?'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. RELIANCE",
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="find_opportunities",
            description=(
                "Scan all Nifty 50 stocks, score each on 6 fundamental criteria, "
                "and return them ranked by score — highest opportunity first. "
                "WARNING: takes 2-3 minutes to scan all 50 stocks. "
                "ALWAYS tell the user this will take a few minutes before calling. "
                "Use for questions like 'Best Nifty 50 stocks dikhao', "
                "'Find top opportunities in Nifty 50', or 'Sabse zyada undervalued stocks'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="analyze_watchlist",
            description=(
                "Analyze all stocks in the user's watchlist at once. Fetches live data, "
                "scores each stock on 6 fundamental criteria, and returns a comprehensive "
                "summary table with scores, key metrics, and highlights. "
                "Use when asked 'Meri poori watchlist analyze karo', 'Watchlist overview', "
                "or 'Meri watchlist mein kaun sa stock best hai?'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="add_portfolio_holding",
            description=(
                "Add a stock holding to the user's portfolio. If the stock already exists, "
                "updates with a weighted average price. "
                "Use when asked 'RELIANCE ke 10 shares add karo at 2450', "
                "'Portfolio me TCS add karo, 5 shares, 3200 pe liya', "
                "or 'I bought 20 HDFCBANK at ₹1600'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. RELIANCE",
                    ),
                    "quantity": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="Number of shares purchased, e.g. 10",
                    ),
                    "avg_price": genai.protos.Schema(
                        type=genai.protos.Type.NUMBER,
                        description="Average purchase price per share in ₹, e.g. 2450.50",
                    ),
                },
                required=["ticker", "quantity", "avg_price"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="remove_portfolio_holding",
            description=(
                "Remove a stock holding from the user's portfolio completely. "
                "Use when asked 'RELIANCE portfolio se hata do', "
                "'Remove TCS from portfolio', or 'Maine TCS bech diya'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol to remove, e.g. TCS",
                    )
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_portfolio_summary",
            description=(
                "Show the user's complete portfolio with current prices, unrealized P&L "
                "for each holding, total portfolio value, and opportunity scores. "
                "Use when asked 'Mera portfolio dikhao', 'Portfolio ka P&L kya hai?', "
                "or 'How is my portfolio doing?'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_pe_history",
            description=(
                "Show a stock's historical PE range to check if it's cheap or expensive "
                "relative to its own history. Shows current PE vs 5-year min/max/median "
                "and percentile bands. "
                "Use when asked 'RELIANCE ka PE history dikhao', "
                "'Is TCS PE historically high?', or 'HDFCBANK cheap hai kya historically?'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. RELIANCE",
                    ),
                    "years": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description=(
                            "Years of history to analyse. Default 5. "
                            "Use 3 for newer listings, 10 for a very long-term view."
                        ),
                    ),
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_technicals",
            description=(
                "Get basic technical analysis indicators for a stock: 50/200-day moving "
                "averages, RSI (14-day), trend signal (bullish/bearish/neutral/mixed), "
                "golden cross / death cross detection, and 20-day support/resistance levels. "
                "Use when asked 'RELIANCE ka technical kya keh raha hai?', "
                "'TCS oversold hai kya?', 'Moving average check karo', "
                "'Golden cross hua kya?', or any question about chart/technical indicators."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. RELIANCE",
                    ),
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="compare_with_peers",
            description=(
                "Compare a stock with all its sector peers on fundamentals and opportunity "
                "scores. Automatically identifies the sector from config/sector_peers.json "
                "and scores every stock in that sector. Returns a ranked table with the "
                "target stock's position among its peers. "
                "WARNING: takes 30–60 seconds depending on sector size — always tell the "
                "user to wait before calling this tool. "
                "Use when asked 'INFY ke peers se compare karo', "
                "'TCS apne sector mein kaisa hai?', or 'RELIANCE vs energy sector'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. INFY",
                    ),
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_dividend_history",
            description=(
                "Show a stock's dividend payment history over the last 5 years, including "
                "annual payouts, dividend growth CAGR, consistency rating (Growing / "
                "Consistent / Irregular / No dividends), and current yield. "
                "Use when asked 'COALINDIA kitna dividend deta hai?', "
                "'ITC ka dividend history dikhao', or 'Dividend growing stocks dikhao'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "ticker": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="NSE ticker symbol without .NS suffix, e.g. ITC",
                    ),
                    "years": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="Years of history to show. Default 5. Max 15.",
                    ),
                },
                required=["ticker"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="generate_daily_master_report",
            description=(
                "Generate a Daily Master Investment Report. This fetches the latest market news to identify impacted stocks and future trends, "
                "AND scans all Nifty 50 stocks to find 3-5 fundamentally strong, underrated stocks suitable for a 1-2 year holding period. "
                "WARNING: Takes 2-3 minutes to run. Always tell the user to wait before calling this tool. "
                "Use when asked 'daily report banao', 'which stock is impacted by what reason', or 'underrated stocks for 1-2 years'."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        ),
    ]
)

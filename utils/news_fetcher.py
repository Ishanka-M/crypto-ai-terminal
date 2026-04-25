"""
News & Sentiment Fetcher
ForexFactory, Investing.com RSS feeds
Crypto news filtering
"""
import feedparser
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup

NEWS_SOURCES = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss",
    "CryptoBriefing": "https://cryptobriefing.com/feed/",
    "Decrypt": "https://decrypt.co/feed",
}

POSITIVE_KEYWORDS = [
    "bullish", "surge", "rally", "pump", "moon", "breakout", "adoption",
    "partnership", "upgrade", "launch", "all-time high", "ATH", "institutional",
    "buy", "inflow", "approval", "ETF", "invest"
]

NEGATIVE_KEYWORDS = [
    "bearish", "crash", "dump", "drop", "ban", "hack", "exploit", "lawsuit",
    "regulation", "FUD", "sell", "outflow", "decline", "loss", "shutdown",
    "scam", "rug", "liquidation"
]

def analyze_sentiment(text: str) -> dict:
    """Simple keyword-based sentiment analysis"""
    text_lower = text.lower()
    positive_score = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    negative_score = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)

    if positive_score > negative_score:
        sentiment = "🟢 Bullish"
        score = positive_score
    elif negative_score > positive_score:
        sentiment = "🔴 Bearish"
        score = negative_score
    else:
        sentiment = "⚪ Neutral"
        score = 0

    return {
        "sentiment": sentiment,
        "positive": positive_score,
        "negative": negative_score,
        "score": score
    }

def is_relevant(title: str, symbol: str) -> bool:
    """Check if news is relevant to given coin"""
    coin_map = {
        "BTCUSDT": ["bitcoin", "btc"],
        "ETHUSDT": ["ethereum", "eth", "ether"],
        "BNBUSDT": ["binance", "bnb"],
        "SOLUSDT": ["solana", "sol"],
        "XRPUSDT": ["ripple", "xrp"],
        "ADAUSDT": ["cardano", "ada"],
        "DOGEUSDT": ["dogecoin", "doge"],
        "AVAXUSDT": ["avalanche", "avax"],
        "MATICUSDT": ["polygon", "matic"],
    }

    keywords = coin_map.get(symbol, [symbol.replace("USDT", "").lower()])
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords) or "crypto" in title_lower

def fetch_news(symbol: str = None, max_articles: int = 20) -> list:
    """Fetch news from RSS feeds and filter by coin"""
    articles = []
    for source, url in NEWS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                published = entry.get("published", "")

                if symbol and not is_relevant(title, symbol):
                    continue

                sentiment = analyze_sentiment(title)
                articles.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "published": published,
                    "sentiment": sentiment["sentiment"],
                    "sentiment_score": sentiment["positive"] - sentiment["negative"],
                })
        except Exception:
            continue

        if len(articles) >= max_articles:
            break

    # Sort by sentiment score
    articles.sort(key=lambda x: x["sentiment_score"], reverse=True)
    return articles[:max_articles]

def get_overall_market_sentiment(articles: list) -> str:
    """Aggregate sentiment from all articles"""
    if not articles:
        return "⚪ Neutral"
    total = sum(a["sentiment_score"] for a in articles)
    if total > 3:
        return "🟢 Strongly Bullish"
    elif total > 0:
        return "🟡 Mildly Bullish"
    elif total < -3:
        return "🔴 Strongly Bearish"
    elif total < 0:
        return "🟠 Mildly Bearish"
    return "⚪ Neutral"

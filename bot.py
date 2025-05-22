import os
import logging
import yfinance as yf
import requests
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import eventlet

# ✅ Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
CORS(app)

# ✅ WebSocket Setup with Reconnection Support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", ping_interval=25, ping_timeout=10)

ALPHA_VANTAGE_API_KEY = "S7B4FCCLL9KFMJ6J"
NEWS_API_KEY = "8acd8ce888e44c4dbe2af98c2a72f5a6"

# ✅ Home Route to Prevent 404 Errors
@app.route("/")
def home():
    return jsonify({"message": "Stock Tracker API is running!"}), 200

# ✅ Function to get stock price
def get_stock_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if not data.empty:
            return round(data["Close"].iloc[-1], 2)
    except Exception as e:
        logging.error(f"⚠️ Error fetching stock price for {ticker}: {e}")
    return None

# ✅ Function to get market sentiment
def get_market_sentiment(ticker):
    try:
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url)
        news = response.json()

        # Check if the response contains relevant news data
        if "feed" not in news:
            logging.warning(f"⚠️ No sentiment data found for {ticker}")
            return "Neutral"

        positive, negative = 0, 0
        for article in news["feed"]:
            title = article.get("title", "").lower()
            summary = article.get("summary", "").lower()  # Check summary too

            if "bullish" in title or "bullish" in summary:
                positive += 1
            elif "bearish" in title or "bearish" in summary:
                negative += 1

        # Determine sentiment based on counts
        if positive > negative:
            return "Bullish"
        elif negative > positive:
            return "Bearish"
        else:
            return "Neutral"  # If no dominant sentiment

    except Exception as e:
        logging.error(f"⚠️ Error fetching sentiment for {ticker}: {e}")
        return "Neutral"

# ✅ Function to get stock news (Limited to 2 Articles)
def get_stock_news(ticker):
    try:
        url = f"https://newsapi.org/v2/everything?q={ticker}&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        data = response.json()

        if "articles" in data:
            articles = [f"📰 {a['title']} 🔗 {a['url']}" for a in data["articles"][:2]]
            return articles
    except Exception as e:
        logging.error(f"⚠️ Error fetching news for {ticker}: {e}")
    
    return ["No recent news available."]

# ✅ WebSocket: Handle Stock Subscription
@socketio.on("subscribe_stock")
def send_stock_data(data):
    ticker = data.get("ticker", "TSLA").upper()
    logging.info(f"✅ Received stock subscription request: {ticker}")

    price = get_stock_price(ticker)
    sentiment = get_market_sentiment(ticker)
    news = get_stock_news(ticker)

    if price:
        socketio.emit("stock_update", {
            "ticker": ticker,
            "price": price,
            "news": news,
            "sentiment": sentiment
        })
        logging.info(f"📡 Sent stock data for {ticker}")
    else:
        socketio.emit("stock_update", {"error": "Invalid stock ticker or data not found"})
        logging.warning(f"⚠️ Stock data not found for {ticker}")

# ✅ WebSocket: Handle Client Disconnection
@socketio.on("disconnect")
def handle_disconnect():
    logging.warning("⚠️ WebSocket client disconnected!")

# ✅ Start Server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)

import yfinance as yf


def get_stock_price(symbol):

    try:

        # Add NSE suffix for Indian stocks
        ticker = symbol.upper() + ".NS"

        stock = yf.Ticker(ticker)

        data = stock.history(period="1d")

        if data.empty:
            return None

        price = data["Close"].iloc[-1]

        return round(price, 2)

    except:
        return None
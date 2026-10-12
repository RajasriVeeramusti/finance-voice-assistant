from tools import calculate_dti
from ml_model import predict_expense
from stock_api import get_stock_price


def income_tool(income):
    return f"Income recorded: ₹{income}"


def expense_tool(expense):
    return f"Expense recorded: ₹{expense}"


def expense_prediction_tool():
    prediction = predict_expense()

    if prediction:
        return f"Predicted next expense: ₹{prediction}"

    return "Not enough data to predict expenses."


def stock_tool(symbol):

    try:
        price = get_stock_price(symbol)
        return f"Current stock price of {symbol} is ₹{price}"

    except:
        return "Stock not found."
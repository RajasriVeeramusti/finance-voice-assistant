from sklearn.linear_model import LinearRegression
import numpy as np

expenses = []

def save_expense(expense):
    expenses.append(expense)

def predict_expense():

    if len(expenses) < 3:
        return None

    X = np.array(range(len(expenses))).reshape(-1,1)
    y = np.array(expenses)

    model = LinearRegression()
    model.fit(X,y)

    next_month = np.array([[len(expenses)]])

    prediction = model.predict(next_month)[0]

    return round(prediction,2)
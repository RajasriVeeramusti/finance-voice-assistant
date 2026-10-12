import json
import os

FILE = "user_data.json"


def save_user_data(income, expenses):

    data = {
        "income": income,
        "expenses": expenses
    }

    with open(FILE, "w") as f:
        json.dump(data, f)


def load_user_data():

    if os.path.exists(FILE):

        with open(FILE, "r") as f:

            data = json.load(f)

            income = data.get("income", 0)
            expenses = data.get("expenses", 0)

            return income, expenses

    return 0, 0
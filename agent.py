
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from database import load_user_data, save_user_data
from tools import financial_health_score, calculate_emi
from ml_model import save_expense, predict_expense
from stock_api import get_stock_price


load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
API_KEY = os.getenv("GROQ_API_KEY", "").strip()

client = Groq(api_key=API_KEY) if API_KEY else None

SYSTEM_PROMPT = """
You are Finance Voice AI Assistant, a friendly, accurate general-purpose
assistant with finance capabilities.

Answer the actual question asked. You can answer general knowledge,
technology, education, programming, science, career, and finance questions.

For personal financial questions, use the supplied financial information
when relevant. Never claim access to bank accounts or personal records that
were not provided.

Explain calculations and assumptions clearly. For loan affordability,
consider income, expenses, existing debt payments, interest rates, tenure,
and emergency savings. For investments, explain risk and diversification;
never promise returns.

Use simple language and practical examples. Do not request loan details
unless the user wants a loan calculation.
"""


# -------------------- DATA HELPERS --------------------

def get_finances():
    """Read the latest financial values from the database."""
    try:
        income, expenses = load_user_data()
        return float(income or 0), float(expenses or 0)
    except (TypeError, ValueError, OSError):
        return 0.0, 0.0


def extract_numbers(text):
    """Extract numbers such as 80000, 80,000, and 1250.50."""
    matches = re.findall(
        r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?",
        str(text).replace("₹", ""),
    )

    numbers = []

    for item in matches:
        try:
            numbers.append(float(item.replace(",", "")))
        except ValueError:
            continue

    return numbers


# -------------------- GENERAL AI --------------------

def generate_ai_response(prompt, history=None):
    """Send general questions to Groq and include recent conversation context."""
    if client is None:
        return (
            "The AI service is not configured because GROQ_API_KEY is missing. "
            "Add a valid key to your .env file and restart Streamlit. "
            "Local financial calculations can still work."
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    if isinstance(history, list):
        for item in history[-12:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if role in ("user", "assistant") and isinstance(content, str):
                if content.strip():
                    messages.append({
                        "role": role,
                        "content": content[:6000],
                    })

    # Add the current question exactly once.
    if not (
        messages
        and messages[-1].get("role") == "user"
        and messages[-1].get("content") == prompt
    ):
        messages.append({
            "role": "user",
            "content": prompt,
        })

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=1200,
        )

        answer = response.choices[0].message.content

        if answer and answer.strip():
            return answer.strip()

        return (
            "I couldn't generate an answer just now. "
            "Please try rephrasing your question."
        )

    except Exception as exc:
        error = str(exc).lower()

        if (
            "401" in error
            or "invalid_api_key" in error
            or "authentication" in error
        ):
            return (
                "Groq authentication failed (401). Check that GROQ_API_KEY "
                "in your .env file is valid and active, then restart Streamlit."
            )

        if "429" in error or "rate_limit" in error:
            return (
                "The AI service has reached its usage limit. "
                "Please wait and try again or check your Groq account limits."
            )

        if "404" in error or "model_not_found" in error:
            return (
                f"The configured model '{MODEL}' is unavailable. "
                "Check the models available in your Groq console and update "
                "GROQ_MODEL in .env."
            )

        return (
            "I couldn't reach the AI service. Check your internet connection, "
            "API configuration, model availability, and usage limits."
        )


# -------------------- INTENT DETECTION --------------------

def detect_intent(text):
    text_lower = text.lower().strip()
    numbers = extract_numbers(text)

    # Explicit income updates
    if (
        numbers
        and re.search(r"\b(income|salary|earnings)\b", text_lower)
        and re.search(
            r"\b(my income is|income is|set income|update income|"
            r"record income|my salary is|salary is|i earn)\b",
            text_lower,
        )
    ):
        return "income"

    # Explicit expense recording
    if (
        numbers
        and re.search(
            r"\b(i spent|i paid|i bought|add expense|record expense|"
            r"record an expense|add an expense)\b",
            text_lower,
        )
    ):
        return "record_expense"

    # Existing expense total queries
    if re.search(
        r"\b(expense|expenses|expenditure|spending)\b",
        text_lower,
    ) and re.search(
        r"\b(my|monthly|current|total|how much|what is|show)\b",
        text_lower,
    ):
        return "expense_query"

    # Existing income queries
    if re.search(r"\b(income|salary)\b", text_lower) and re.search(
        r"\b(my|monthly|current|how much|what is|show)\b",
        text_lower,
    ):
        return "income_query"

    if re.search(
        r"\b(financial summary|summary of my finances|financial health)\b",
        text_lower,
    ):
        return "summary"

    # Saving goal updates are different from actual account balances.
    if (
        re.search(
            r"\b(savings goal|saving goal|target savings|goal amount)\b",
            text_lower,
        )
        or re.search(
            r"\b(update my savings to|set my savings to)\b",
            text_lower,
        )
    ) and numbers:
        return "savings_goal"

    # Definitions about loans should go to the general AI.
    # Only explicit EMI calculation requests use the EMI calculator.
    if (
        re.search(r"\b(calculate|work out|estimate|compute)\b", text_lower)
        and re.search(r"\b(emi|loan repayment)\b", text_lower)
    ):
        return "emi"

    if re.search(
        r"\b(loan affordability|afford a loan|affordable loan)\b",
        text_lower,
    ):
        return "loan_affordability"

    if re.search(r"\b(stock price|share price|stock quote)\b", text_lower):
        return "stock"

    if re.search(
        r"\b(predict|forecast)\b",
        text_lower,
    ) and re.search(r"\b(expense|spending)\b", text_lower):
        return "prediction"

    if re.search(
        r"\b(invest|investment|sip|mutual fund)\b",
        text_lower,
    ):
        return "investment"

    if re.search(
        r"\b(save|saving|savings|surplus|leftover)\b",
        text_lower,
    ):
        return "savings"

    return "general"


# -------------------- FINANCIAL SUMMARY --------------------

def financial_summary():
    income, expenses = get_finances()

    if income <= 0:
        return (
            "Your monthly income is not saved yet. "
            "For example, say: 'My income is 80000'."
        )

    remaining = income - expenses
    savings_ratio = remaining / income * 100

    try:
        score, status = financial_health_score(income, expenses)
        health_text = (
            f"\n- Financial health score: {score}/100 ({status})"
        )
    except Exception:
        health_text = ""

    return (
        "### Your Financial Summary\n\n"
        f"- Monthly income: ₹{income:,.2f}\n"
        f"- Monthly expenses: ₹{expenses:,.2f}\n"
        f"- Remaining balance: ₹{remaining:,.2f}\n"
        f"- Income remaining: {savings_ratio:.2f}%"
        f"{health_text}"
    )


# -------------------- STOCK INFORMATION --------------------

def stock_response(text):
    match = re.search(
        r"(?:stock price of|share price of|price of)\s+([A-Za-z0-9.&-]+)",
        text,
        re.IGNORECASE,
    )

    if not match:
        match = re.search(
            r"\b([A-Za-z]{2,10})\s+(?:stock|share)\s+price\b",
            text,
            re.IGNORECASE,
        )

    if not match:
        return (
            "Please specify a company or symbol, for example: "
            "'stock price of TCS'."
        )

    symbol = match.group(1).upper().replace("&", "")

    try:
        price = get_stock_price(symbol)
    except Exception:
        price = None

    if price:
        return (
            f"Latest available price for {symbol}: ₹{float(price):,.2f}. "
            "Market data may be delayed."
        )

    return (
        f"I couldn't retrieve the price for {symbol}. "
        "Check the company symbol and try again."
    )


# -------------------- MAIN ROUTER --------------------

def route_query(user_input, history=None):
    """Route personal-finance actions locally and other questions to Groq."""
    text = str(user_input or "").strip()

    if not text:
        return "Please type or say a question."

    lower = text.lower()
    numbers = extract_numbers(text)
    intent = detect_intent(text)

    income, expenses = get_finances()

    # Update income without overwriting expenses.
    if intent == "income":
        amount = numbers[0]

        if amount < 0:
            return "Income cannot be negative."

        save_user_data(amount, expenses)

        return f"Your monthly income has been saved as ₹{amount:,.2f}."

    if intent == "income_query":
        if income <= 0:
            return (
                "No monthly income is saved yet. "
                "Tell me: 'My income is 80000'."
            )

        return f"Your saved monthly income is ₹{income:,.2f}."

    # Record a new purchase by adding it to the current expense total.
    if intent == "record_expense":
        amount = numbers[0]

        if amount < 0:
            return "An expense amount cannot be negative."

        updated_expenses = expenses + amount
        save_user_data(income, updated_expenses)

        try:
            save_expense(amount)
        except Exception:
            pass

        return (
            f"Recorded ₹{amount:,.2f}. Your saved monthly expense total "
            f"is now ₹{updated_expenses:,.2f}."
        )

    if intent == "expense_query":
        if expenses <= 0:
            return (
                "No monthly expenses are saved yet. "
                "You can record a purchase by saying "
                "'I spent 500 on groceries'."
            )

        return f"Your saved monthly expenditure is ₹{expenses:,.2f}."

    if intent == "summary":
        return financial_summary()

    if intent == "savings_goal":
        goal = numbers[0]

        if goal <= 0:
            return "Your savings goal must be greater than zero."

        try:
            temp_file = "savings_goal.json.tmp"

            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump({"goal": goal}, file, indent=2)

            os.replace(temp_file, "savings_goal.json")

        except OSError:
            return (
                "I couldn't save your savings goal. "
                "Check the project folder permissions."
            )

        return (
            f"Your savings goal has been saved as ₹{goal:,.2f}. "
            "This updates your goal only, not your actual income, expenses, "
            "or bank balance."
        )

    if intent == "savings":
        if income > 0:
            remaining = income - expenses

            return (
                f"Your estimated monthly surplus is ₹{remaining:,.2f} "
                f"(income ₹{income:,.2f} minus expenses ₹{expenses:,.2f}). "
                "Cover essential costs and debt payments first, and maintain "
                "an emergency fund before choosing a savings transfer."
            )

        return generate_ai_response(text, history=history)

    if intent == "emi":
        if not numbers:
            return (
                "Please provide the loan amount, annual interest rate, and "
                "tenure. Example: 'Calculate EMI for a 500000 loan at 9% "
                "for 60 months'."
            )

        principal = numbers[0]
        rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", lower)
        months_match = re.search(r"(\d+)\s*(?:months?|mos)\b", lower)
        years_match = re.search(r"(\d+)\s*years?\b", lower)

        rate = float(rate_match.group(1)) if rate_match else 8.0

        if months_match:
            months = int(months_match.group(1))
        elif years_match:
            months = int(years_match.group(1)) * 12
        else:
            months = 12

        if principal <= 0 or rate < 0 or months <= 0:
            return (
                "Please provide a positive loan amount and tenure "
                "and a non-negative interest rate."
            )

        try:
            emi = calculate_emi(principal, rate, months)
        except Exception:
            monthly_rate = rate / 1200

            if monthly_rate == 0:
                emi = principal / months
            else:
                factor = (1 + monthly_rate) ** months
                emi = principal * monthly_rate * factor / (factor - 1)

        return (
            "### EMI Estimate\n\n"
            f"- Loan amount: ₹{principal:,.2f}\n"
            f"- Annual interest rate: {rate:.2f}%\n"
            f"- Tenure: {months} months\n"
            f"- Estimated monthly EMI: ₹{emi:,.2f}\n\n"
            "This is an estimate, not a lender quote or loan approval."
        )

    if intent == "loan_affordability":
        if income > 0:
            balance = income - expenses

            return (
                f"Your saved monthly income is ₹{income:,.2f} and your "
                f"saved monthly expenses are ₹{expenses:,.2f}. That leaves "
                f"₹{balance:,.2f} before any new loan payment.\n\n"
                "For affordability, consider existing EMIs, essential costs, "
                "interest rate, loan tenure, emergency savings, and your "
                "lender's eligibility criteria. If you share a loan amount, "
                "interest rate, and tenure, I can estimate the EMI."
            )

        return generate_ai_response(
            "Explain loan affordability in simple language. Cover income, "
            "expenses, existing debt payments, interest, tenure, emergency "
            "savings, and how to assess affordability. This is a general "
            "question; do not require a loan amount.",
            history=history,
        )

    if intent == "stock":
        return stock_response(text)

    if intent == "prediction":
        try:
            prediction = predict_expense()
        except Exception:
            prediction = None

        if prediction is None:
            return (
                "I don't have enough expense history for a prediction yet. "
                "Record several expenses first."
            )

        return (
            f"Estimated next expense: approximately ₹{float(prediction):,.2f}."
        )

    if intent == "investment":
        return generate_ai_response(
            "Give educational investment information. Explain risk, "
            "diversification, time horizon, and that returns are not "
            "guaranteed. Question: " + text,
            history=history,
        )

    # Definitions, explanations, and general questions always go to AI.
    return generate_ai_response(text, history=history)

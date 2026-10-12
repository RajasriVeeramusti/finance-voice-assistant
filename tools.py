import math


# -------------------------
# DEBT TO INCOME RATIO
# -------------------------

def calculate_dti(income, expenses):

    if income == 0:
        return 0

    return round(expenses / income, 2)


# -------------------------
# EMI CALCULATOR
# -------------------------

def calculate_emi(principal, annual_interest_rate, months):

    if months == 0:
        return 0

    r = annual_interest_rate / (12 * 100)

    if r == 0:
        return round(principal / months, 2)

    emi = (principal * r * (1 + r)**months) / ((1 + r)**months - 1)

    return round(emi, 2)


# -------------------------
# AFFORDABLE EMI ESTIMATE
# -------------------------

def affordable_emi(income, expenses):

    savings = income - expenses

    safe_emi = savings * 0.5

    return round(safe_emi, 2)


# -------------------------
# SAVINGS GOAL PLANNER
# -------------------------

def savings_plan(goal_amount, months):

    monthly_savings = goal_amount / months

    return round(monthly_savings, 2)


# -------------------------
# FINANCIAL HEALTH SCORE
# -------------------------

def financial_health_score(income, expenses):

    if income == 0:
        return 0, "Unknown"

    savings_ratio = (income - expenses) / income

    score = savings_ratio * 100

    if score > 60:
        status = "Excellent"
    elif score > 40:
        status = "Good"
    elif score > 20:
        status = "Average"
    else:
        status = "Poor"

    return round(score, 2), status
                    process_message(recognized_text)

        except Exception as exc:
            # Do not print or expose secret values.
            st.error(
                "Automatic transcription failed. Check that GROQ_API_KEY is valid, "
                "the Groq package is installed, and the transcription model is available. "
                f"Error type: {type(exc).__name__}."
            )



# -------------------- FINANCIAL DASHBOARD --------------------

st.markdown("## 📊 Dashboard Summary")

income, expenses = load_user_data()

income = float(income or 0)
expenses = float(expenses or 0)

if income > 0:
    savings = income - expenses
    savings_ratio = savings / income

    col1, col2, col3 = st.columns(3)

    col1.metric("💰 Monthly Income", f"₹{income:,.2f}")
    col2.metric("💸 Monthly Expenses", f"₹{expenses:,.2f}")
    col3.metric("📈 Remaining Balance", f"₹{savings:,.2f}")

    st.progress(min(max(savings_ratio, 0.0), 1.0))
    st.caption(
        f"Income remaining: {savings_ratio * 100:.2f}%"
    )

    labels = []
    values = []

    if expenses > 0:
        labels.append("Expenses")
        values.append(expenses)

    if savings > 0:
        labels.append("Remaining balance")
        values.append(savings)

    if values:
        fig, ax = plt.subplots(figsize=(4, 3))

        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"fontsize": 9},
            radius=0.8,
        )

        ax.axis("equal")
        ax.set_title("Income Allocation", fontsize=11)

        st.pyplot(fig, use_container_width=False)
        plt.close(fig)

    try:
        with open(
            "expense_history.json",
            "r",
            encoding="utf-8",
        ) as file:
            expense_history = json.load(file)

        if isinstance(expense_history, list) and expense_history:
            st.markdown("### 📈 Expense Trend")
            st.line_chart(expense_history)
        else:
            st.info("No expense trend data is available yet.")

    except (OSError, json.JSONDecodeError, ValueError):
        st.info("No expense history available yet.")

    st.markdown("### 🤖 Financial Insights")

    if savings < 0:
        st.warning(
            "Your saved expenses exceed your income. "
            "Review your budget and essential costs."
        )
    elif savings_ratio < 0.30:
        st.warning(
            "Less than 30% of your income remains after expenses. "
            "Review your budget and savings goals."
        )
    elif savings_ratio > 0.50:
        st.success(
            "More than 50% of your income remains after expenses. "
            "Keep an emergency fund and review your budget regularly."
        )
    else:
        st.info(
            "Your remaining balance is moderate. "
            "Set a realistic savings target based on your expenses."
        )

else:
    st.info(
        "To populate the dashboard, say 'My income is 80000' "
        "and then record your expenses."
    )


import json
import os
import uuid
from datetime import datetime

import matplotlib.pyplot as plt
import streamlit as st
import hashlib
import re

from agent import route_query
from database import load_user_data


# -------------------- PAGE CONFIGURATION --------------------

st.set_page_config(
    page_title="Finance Voice AI Assistant",
    page_icon="💰",
    layout="wide",
)

CHAT_FILE = "chat_sessions.json"

st.markdown(
    """
    <style>
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 10px;
        margin-bottom: 8px;
    }
    [data-testid="stSidebar"] {
        min-width: 260px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------- CHAT HISTORY --------------------

def load_sessions():
    """Load saved chats and ignore empty conversations."""
    try:
        with open(CHAT_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {}

        sessions = {}

        for chat_id, session in data.items():
            if not isinstance(session, dict):
                continue

            messages = session.get("messages", [])
            cleaned_messages = []

            if isinstance(messages, list):
                for message in messages:
                    if (
                        isinstance(message, dict)
                        and message.get("role") in ("user", "assistant")
                        and "content" in message
                    ):
                        cleaned_messages.append({
                            "role": message["role"],
                            "content": str(message["content"]),
                        })

            # Only load chats containing a real user message.
            if not any(
                message["role"] == "user"
                for message in cleaned_messages
            ):
                continue

            sessions[str(chat_id)] = {
                "title": str(session.get("title", "New chat")),
                "created_at": str(session.get("created_at", "")),
                "messages": cleaned_messages,
            }

        return sessions

    except (OSError, json.JSONDecodeError):
        return {}


def save_sessions():
    """Save only chats in which the user has sent a message."""
    persistable_sessions = {
        chat_id: session
        for chat_id, session in st.session_state.chat_sessions.items()
        if any(
            message.get("role") == "user"
            for message in session.get("messages", [])
        )
    }

    temp_file = CHAT_FILE + ".tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(
                persistable_sessions,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temp_file, CHAT_FILE)

    except OSError as exc:
        st.warning(f"Unable to save chat history: {exc}")


def create_chat():
    """Create a blank chat in memory, without saving it to history."""
    chat_id = str(uuid.uuid4())

    st.session_state.chat_sessions[chat_id] = {
        "title": "New chat",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
    }

    st.session_state.active_chat_id = chat_id


# -------------------- INITIALIZE SESSION --------------------

if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_sessions()

if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = None

# Create one blank chat when the current browser session starts.
if (
    st.session_state.active_chat_id is None
    or st.session_state.active_chat_id
    not in st.session_state.chat_sessions
):
    create_chat()


# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.title("💰 Finance Assistant")
    st.caption("Your personal finance chatbot")

    if st.button("＋ New Chat", use_container_width=True):
        create_chat()
        st.rerun()

    st.divider()
    st.subheader("Chat History")

    # Display only conversations with at least one user message.
    recent_chat_ids = [
        chat_id
        for chat_id, session in reversed(
            list(st.session_state.chat_sessions.items())
        )
        if any(
            message.get("role") == "user"
            for message in session.get("messages", [])
        )
    ]

    if not recent_chat_ids:
        st.caption("No previous conversations.")

    for chat_id in recent_chat_ids:
        session = st.session_state.chat_sessions[chat_id]
        title = session.get("title", "New chat")

        if st.button(
            title[:42],
            key=f"history_{chat_id}",
            use_container_width=True,
            type=(
                "primary"
                if chat_id == st.session_state.active_chat_id
                else "secondary"
            ),
        ):
            st.session_state.active_chat_id = chat_id
            st.rerun()

    st.divider()

    if st.button("🗑️ Clear All History", use_container_width=True):
        st.session_state.chat_sessions = {}

        # Clear the saved history file.
        try:
            with open(CHAT_FILE, "w", encoding="utf-8") as file:
                json.dump({}, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            st.warning(f"Unable to clear saved history: {exc}")

        # Start a fresh blank chat without saving it.
        create_chat()
        st.rerun()


# -------------------- ACTIVE CHAT --------------------

active_chat = st.session_state.chat_sessions[
    st.session_state.active_chat_id
]


# -------------------- RESPONSE FORMATTING --------------------

def render_answer_content(answer):
    """Render normal text as Markdown and display display-math as real equations."""
    answer = str(answer or "")
    # Accept common display-math forms: \[ ... \], $$ ... $$, and
    # a bracketed expression containing clear LaTeX commands (e.g. \frac).
    pattern = re.compile(
        r"\\\[(.*?)\\\]|\$\$(.*?)\$\$|"
        r"\[\s*(?=[^\]]*(?:\\frac|\\times|\\sqrt|\\sum|\\int|\\cdot|\\div|\\pi|\\text|\^\{)).*?\]",
        re.DOTALL,
    )
    cursor = 0
    for match in pattern.finditer(answer):
        before = answer[cursor:match.start()].strip()
        if before:
            st.markdown(before)

        formula = next((group for group in match.groups() if group is not None), None)
        if formula is None:
            # The third alternative matches bracketed LaTeX without a capture group.
            formula = match.group(0).strip()[1:-1]
        formula = formula.strip().strip("$").strip()
        if formula:
            st.latex(formula)
        cursor = match.end()

    remainder = answer[cursor:].strip()
    if remainder:
        st.markdown(remainder)



# -------------------- CHAT INTERFACE --------------------

st.title("💰 Finance Voice AI Assistant")
st.caption("Ask questions by typing or speaking.")
st.markdown("## 💬 Chat")

for message in active_chat["messages"]:
    avatar = "👤" if message["role"] == "user" else "🤖"

    with st.chat_message(message["role"], avatar=avatar):
        render_answer_content(message["content"])


# -------------------- MESSAGE PROCESSING --------------------

def process_message(user_text):
    """Answer the question and save the conversation."""
    user_text = str(user_text or "").strip()

    if not user_text:
        return

    chat_id = st.session_state.active_chat_id
    chat = st.session_state.chat_sessions[chat_id]

    # Add the user message exactly once and display it in this run.
    chat["messages"].append({
        "role": "user",
        "content": user_text,
    })
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_text)

    # Use the first user message as the chat title.
    if chat["title"] == "New chat":
        chat["title"] = user_text.replace("\n", " ")[:42]

    # The chat becomes eligible for history after this save.
    save_sessions()

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            try:
                # Pass earlier messages as context.
                history = chat["messages"][:-1]

                answer = route_query(
                    user_text,
                    history=history,
                )
                answer = str(answer)

            except Exception as exc:
                answer = (
                    "I encountered an unexpected error while answering. "
                    "Please try again. Check the terminal for details."
                )
                print(f"Chat processing error: {exc}")

            render_answer_content(answer)

    chat["messages"].append({
        "role": "assistant",
        "content": answer,
    })

    save_sessions()

# -------------------- TEXT INPUT --------------------

user_input = st.chat_input(
    "Ask anything about your finances or other topics..."
)

if user_input:
    process_message(user_input)


# -------------------- VOICE INPUT --------------------

st.markdown("## 🎤 Voice Input")
st.caption(
    "Click the recorder, speak your complete question, then stop the recording. "
    "The app will automatically transcribe it and answer in text."
)

# Browser-side recording avoids server microphone/PyAudio problems on Streamlit Cloud.
audio_recording = st.audio_input("🎙️ Record your question", key="voice_recording")

if audio_recording is not None:
    audio_bytes = audio_recording.getvalue()
    audio_digest = hashlib.sha256(audio_bytes).hexdigest()
    last_attempted_digest = st.session_state.get("last_attempted_audio_digest")

    # st.audio_input causes reruns; the digest ensures a recording is handled once.
    if audio_bytes and audio_digest != last_attempted_digest:
        # Set before network calls to prevent duplicate submissions during reruns.
        st.session_state.last_attempted_audio_digest = audio_digest

        try:
            api_key = st.secrets.get("GROQ_API_KEY", "")
            if not api_key:
                st.error(
                    "GROQ_API_KEY is missing. Add it under Streamlit Cloud → "
                    "App settings → Secrets."
                )
            else:
                from groq import Groq

                with st.spinner("Transcribing your recording..."):
                    groq_client = Groq(api_key=api_key)
                    transcription = groq_client.audio.transcriptions.create(
                        file=("voice_question.wav", audio_bytes),
                        model="whisper-large-v3-turbo",
                        response_format="json",
                    )
                    recognized_text = str(
                        getattr(transcription, "text", "") or ""
                    ).strip()

                if not recognized_text:
                    st.warning(
                        "No speech was detected. Please record your question again."
                    )
                else:
                    st.success(f"Transcribed: {recognized_text}")
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

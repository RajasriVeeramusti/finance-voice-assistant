
import threading

_engine = None
_engine_lock = threading.RLock()
_speech_lock = threading.Lock()
_speech_thread = None
_stop_requested = threading.Event()


def _speak_worker(text):
    global _engine

    try:
        import pyttsx3

        # Create and use the engine in the worker thread.
        engine = pyttsx3.init()

        with _engine_lock:
            _engine = engine

        if _stop_requested.is_set():
            engine.stop()
            return

        engine.say(str(text))
        engine.runAndWait()

    except Exception as exc:
        print(f"Text-to-speech error: {exc}")

    finally:
        with _engine_lock:
            _engine = None


def speak(text):
    """Start speech without blocking the Streamlit interface."""
    global _speech_thread

    if not text or not str(text).strip():
        return

    # Avoid starting overlapping speech.
    stop_speaking()

    _stop_requested.clear()

    # Remove Markdown markers before speaking the response.
    clean_text = str(text)
    for marker in ("###", "**", "__", "`", "*"):
        clean_text = clean_text.replace(marker, "")

    _speech_thread = threading.Thread(
        target=_speak_worker,
        args=(clean_text,),
        daemon=True,
    )
    _speech_thread.start()


def stop_speaking():
    """Request cancellation of the current spoken response."""
    _stop_requested.set()

    with _engine_lock:
        engine = _engine

    if engine is not None:
        try:
            engine.stop()
        except Exception as exc:
            print(f"Could not stop text-to-speech: {exc}")


def is_speaking():
    """Return whether the speech worker is still running."""
    return _speech_thread is not None and _speech_thread.is_alive()

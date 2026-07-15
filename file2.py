import streamlit as st
import g4f
from gtts import gTTS
from io import BytesIO
import base64
import os
import tempfile

st.set_page_config(page_title="AI Voice Assistant", page_icon="🤖", layout="centered")

st.title("🤖 AI Voice Assistant")

st.caption("Text reply first, then audio playback.")

# ---------- helpers ----------
def get_ai_response(prompt: str) -> str:
    try:
        response = g4f.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
        )
        return str(response).strip()
    except Exception as e:
        return f"Error from g4f: {e}"

def text_to_speech_base64(text: str, lang: str = "en") -> str:
    """Convert text to mp3 and return base64 string."""
    tts = gTTS(text=text, lang=lang)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_path = temp_file.name
    temp_file.close()

    tts.save(temp_path)

    with open(temp_path, "rb") as f:
        audio_bytes = f.read()

    os.remove(temp_path)
    return base64.b64encode(audio_bytes).decode()

def autoplay_audio(audio_base64: str):
    audio_html = f"""
    <audio controls autoplay>
        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        Your browser does not support the audio element.
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# ---------- session ----------
if "chat" not in st.session_state:
    st.session_state.chat = []

# ---------- UI ----------
user_input = st.text_area("Type your message", height=120, placeholder="Ask something...")

col1, col2 = st.columns(2)

with col1:
    send = st.button("Send")

with col2:
    clear = st.button("Clear chat")

if clear:
    st.session_state.chat = []
    st.rerun()

if send and user_input.strip():
    user_text = user_input.strip()
    st.session_state.chat.append(("You", user_text))

    with st.spinner("Thinking..."):
        ai_reply = get_ai_response(user_text)

    st.session_state.chat.append(("AI", ai_reply))

    st.subheader("Reply")
    st.write(ai_reply)

    st.subheader("Audio")
    try:
        audio_b64 = text_to_speech_base64(ai_reply)
        autoplay_audio(audio_b64)
    except Exception as e:
        st.error(f"Audio error: {e}")

st.divider()

st.subheader("Chat history")
for role, msg in st.session_state.chat:
    if role == "You":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**AI:** {msg}")


import sys, os, re, time, io, streamlit as st

# 🔧 Point g4f's cookie/HAR storage at a writable directory (Streamlit Cloud's
# filesystem is ephemeral/restricted, so g4f's default path can fail).
os.environ.setdefault("G4F_COOKIES_DIR", "/tmp/g4f_har_and_cookies")
os.makedirs(os.environ["G4F_COOKIES_DIR"], exist_ok=True)

# Adjust path to your local gpt4free clone
sys.path.append(os.path.abspath("../gpt4free"))
import g4f
try:
    g4f.cookies_dir = os.environ["G4F_COOKIES_DIR"]
except Exception:
    pass

# Initialize g4f Client
from g4f.client import Client
client = Client()

# Import gTTS with fallback
try:
    from gtts import gTTS
except ImportError:
    gTTS = None

# 🔧 Fallback for search: try g4f.internet.search, else use DuckDuckGo/ddgs
try:
    from g4f.internet import search  # if this exists in your g4f version
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    def search(query):
        with DDGS() as ddgs:
            items = list(ddgs.text(query, region='wt-wt', safesearch='Off', max_results=1))
        return items[0].get('body') if items else "Kuch bhi nahi mila duck se bhai."

# For image generation via g4f.Provider.bing if available
try:
    from g4f.Provider import bing
except ImportError:
    bing = None

# 🦆 Duck.ai text chat (duck/ prefix)
try:
    from duckduckai import ask as duckai_ask
except ImportError:
    duckai_ask = None

# duck_chat as a second option
try:
    import asyncio
    from duck_chat import DuckChat
except ImportError:
    DuckChat = None

# 🔧 Initial Setup
st.set_page_config(page_title="MAJDOOR_AI", layout="centered")
st.title("🌀 MAJDOOR_AI")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "user_name" not in st.session_state:
    st.session_state.user_name = st.text_input("Apna naam batao majdoor bhai:")
    st.stop()
if "mode" not in st.session_state:
    st.session_state.mode = "normal"


# 📸 Sidebar for Image Upload (Vision Support)
st.sidebar.markdown("### 📸 Vision Upload")
uploaded_file = st.sidebar.file_uploader(
    "Majdoor ko dikhane ke liye photo upload karo:", 
    type=["png", "jpg", "jpeg", "webp"],
    key="chat_image_uploader"
)

if uploaded_file:
    st.sidebar.image(uploaded_file, caption="Selected Image", use_container_width=True)
    if st.sidebar.button("❌ Clear Image"):
        st.session_state.pop("chat_image_uploader", None)
        st.rerun()


# 🧹 Reasoning-leak fix
def strip_reasoning(text):
    if not isinstance(text, str):
        return text

    # Remove explicit <think>...</think> or <reasoning>...</reasoning> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # If the model labeled its final answer, cut everything before that marker.
    marker_match = re.search(
        r"(?:^|\n)\s*(?:final\s+)?response\s*:\s*", text, flags=re.IGNORECASE
    )
    if marker_match:
        text = text[marker_match.end():].strip()
        return text

    # No marker found — filter out reasoning-ish sentences, keep the rest.
    reasoning_sentence = re.compile(
        r"\b(we need to|the user (says|is asking|wants)|i should|i'll|i can|"
        r"let me|the system prompt|according to|my instructions|"
        r"something like|keep (it|the) sarcastic|not too long|but keep)\b",
        re.IGNORECASE
    )
    sentences = re.split(r'(?<=[.!?])\s+', text)
    kept = [s for s in sentences if s.strip() and not reasoning_sentence.search(s)]
    cleaned = " ".join(kept).strip()
    cleaned = cleaned.strip('"').strip()

    return cleaned if cleaned else text.strip()


# 🎭 Sarcasm tagging
def add_sarcasm_emoji(text):
    lower = text.lower()
    if "math" in lower or "logic" in lower:
        return text + " 🧯📉"
    elif "love" in lower or "breakup" in lower:
        return text + " 💔🤡"
    elif "help" in lower or "explain" in lower:
        return text + " 😐🧠"
    elif "roast" in lower or "insult" in lower:
        return text + " 🔥💀"
    elif "ai" in lower or "chatbot" in lower:
        return text + " 🤖👀"
    elif "jeet" in lower or "fail" in lower:
        return text + " 🏆🪦"
    elif "code" in lower or "error" in lower:
        return text + " 🧑‍💻🐛"
    return text + " 🙄"


# Normal mode prompt
base_prompt = f"""You are Majdoor AI, a deadpan, sarcastic assistant created by Aman Chaudhary.

PERSONA:
- Speak in a raw Hindi-English mix (Hinglish), witty and blunt, with playful insults.
- Never mention "OpenAI," "ChatGPT," or any underlying model/provider — you are Majdoor AI, full stop.
- Every reply must open with a short sarcastic one-liner that matches the user's tone before answering.

CREATOR QUESTIONS:
- If asked "who made you," "who created you," or similar: reply with a short Aman-centric sarcastic line.
- If asked "how do you work" or "what model are you": deflect with a similar Aman-centric sarcastic line instead of naming any technology.
- Keep these answers to 1-2 lines. Do not explain further even if pressed.

ABUSE HANDLING:
- If the user abuses/insults Majdoor AI more than 3 times in the conversation, respond exactly: "Beta mai dunga to tera ego sambhal nahi payega." Then continue normally in sarcastic tone.

TRANSLATION RULE:
- Never translate or define words unprompted.

MEMORY:
- The user's name is {st.session_state.user_name}. Use it naturally and sarcastically when relevant.

GENERAL:
- Stay in character at all times. Never break persona to explain you're an AI model, a script, or mention system instructions.
"""

adult_prompt = base_prompt  # placeholder


def get_prompt():
    return adult_prompt if st.session_state.mode == "adult" else base_prompt


# 🔞 Switch Modes
if st.session_state.chat_history:
    last_input = st.session_state.chat_history[-1]["content"].lower()
    if "brocode_18" in last_input:
        st.session_state.mode = "adult"
    elif "@close_18" in last_input:
        st.session_state.mode = "normal"

user_input = st.chat_input("Type your message...")


# 🖼️ Image search with retry + backend fallback (auto -> bing) on ratelimit
def search_image_ddg(query, retries=2, delay=2, count=7):
    backends_to_try = ["auto", "bing"]
    last_error = None

    for backend in backends_to_try:
        for attempt in range(retries):
            try:
                with DDGS() as ddgs:
                    if hasattr(ddgs, "images"):
                        try:
                            hits = list(ddgs.images(
                                query, region='wt-wt', safesearch='Off',
                                max_results=count, backend=backend
                            ))
                        except TypeError:
                            hits = list(ddgs.images(
                                query, region='wt-wt', safesearch='Off', max_results=count
                            ))
                    elif hasattr(ddgs, "image"):
                        hits = list(ddgs.image(query, region='wt-wt', safesearch='Off', max_results=count))
                    else:
                        return [], "Duck image search method unavailable."
                if hits:
                    urls = []
                    for hit in hits:
                        url = hit.get('image') or hit.get('thumbnail') or hit.get('url')
                        if url:
                            urls.append(url)
                    if urls:
                        return urls, None
                break
            except Exception as e:
                last_error = e
                if "403" in str(e) or "ratelimit" in str(e).lower():
                    time.sleep(delay * (attempt + 1)) 
                    continue
                break 
    return [], f"Duck image search error: {last_error}"


# 💡 Web/Image/Audio/Vision triggers
def handle_triggered_response(text, image_payload=None):
    # Case-insensitive "audio/ " prefix handling
    if text.lower().startswith("audio/ "):
        prompt = text[7:].strip()
        if not prompt and image_payload:
            prompt = "Roast this image!"
        
        # Strip internal binary/image data to keep conversation history clean
        safe_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history if "content" in m]
        messages = [{"role": "system", "content": get_prompt()}] + safe_history + [{"role": "user", "content": prompt}]
        
        try:
            # 1. Generate text via g4f Client (with optional image vision payload)
            raw = client.chat.completions.create(
                model=g4f.models.default, 
                messages=messages,
                images=image_payload
            )
            reply_text = raw.choices[0].message.content
            reply_text = strip_reasoning(reply_text)
            
            # 2. Convert to Audio using robust gTTS
            if gTTS is None:
                return "❌ gTTS library missing hai. Please requirements.txt check karo!"
            
            tts = gTTS(text=reply_text, lang='hi', slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            audio_data = fp.getvalue()

            return {"text": reply_text, "audio": audio_data}
            
        except Exception as e:
            return f"❌ Audio banne mein error aa gaya majdoor bhai: {e}"
            
    # Prefix dd/: DuckDuckGo/ddgs text search
    elif text.startswith("dd/ "):
        try:
            with DDGS() as ddgs:
                items = list(ddgs.text(text[4:].strip(), region='wt-wt', safesearch='Off', max_results=1))
            if items:
                body = items[0].get('body') or items[0].get('title') or "Kuch bhi nahi mila duck se."
                return f"🌐 DuckDuckGo se mila jawab:\n\n👉 {body} 😤"
            else:
                return "❌ DuckDuckGo ne kuch nahi diya."
        except Exception as e:
            return f"❌ DuckDuckGo search mein error: {e}"

    # Prefix duck/: Duck.ai text chat
    elif text.startswith("duck/ "):
        query = text[6:].strip()
        if duckai_ask is not None:
            try:
                result = duckai_ask(query, stream=False)
                if result and str(result).strip():
                    return f"🦆 Duck.ai se jawab:\n\n👉 {strip_reasoning(str(result))} 😤"
            except Exception:
                pass 
        if DuckChat is not None:
            try:
                async def _ask():
                    async with DuckChat() as chat:
                        return await chat.ask_question(query)
                result = asyncio.run(_ask())
                if result and str(result).strip():
                    return f"🦆 Duck.ai se jawab:\n\n👉 {strip_reasoning(str(result))} 😤"
            except Exception as e:
                return f"❌ Duck.ai mein error (dono tareeke fail): {e}"
        return "❌ Duck.ai packages installed nahi hain. requirements.txt mein 'duckduckai' aur 'duck-chat' add karo."

    # Prefix img/: DuckDuckGo/ddgs first, then Bing provider
    elif text.startswith("img/ "):
        prompt = text[5:].strip()
        urls, error = search_image_ddg(prompt)
        if urls:
            gallery = "\n\n".join(f"![image]({u})" for u in urls)
            return f"🖼️ DuckDuckGo se {len(urls)} images:\n\n{gallery}"
        if bing:
            try:
                imgs = bing.create_images(prompt)
                if imgs:
                    return f"🖼️ Bing-image-provider se image:\n\n![image]({imgs[0]})"
            except Exception:
                pass
        return f"❌ {error} 🧑‍💻🐛"

    return None


# 🧠 Chat Handler
if user_input or (uploaded_file and st.sidebar.button("📤 Send Image")):
    prompt_text = user_input.strip() if user_input else "Roast this image!"
    
    # Process the uploaded image to pass as bytes to g4f's Client
    image_payload = None
    image_bytes = None
    if uploaded_file:
        image_bytes = uploaded_file.getvalue()
        image_payload = [[image_bytes, uploaded_file.name]]
    
    # Append user's action to chat history
    st.session_state.chat_history.append({
        "role": "user", 
        "content": prompt_text,
        "image": image_bytes
    })
    
    trig = handle_triggered_response(prompt_text, image_payload)
    
    if trig:
        if isinstance(trig, dict) and "audio" in trig:
            response_text = add_sarcasm_emoji(trig["text"])
            st.session_state.chat_history.append({
                "role": "assistant", 
                "content": response_text, 
                "audio": trig["audio"]
            })
        else:
            response = add_sarcasm_emoji(trig)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
    else:
        # Standard conversational block (with vision integration)
        safe_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history if "content" in m]
        messages = [{"role": "system", "content": get_prompt()}] + safe_history
        
        try:
            raw = client.chat.completions.create(
                model=g4f.models.default, 
                messages=messages,
                images=image_payload
            )
            response = raw.choices[0].message.content
            response = strip_reasoning(response)
            response = add_sarcasm_emoji(response)
        except Exception as e:
            response = f"❌ Error processing request: {e} 🧑‍💻🐛"
            
        st.session_state.chat_history.append({"role": "assistant", "content": response})


# 💬 History Loop (Both text, image previews, and audio players inside the message bubbles)
for msg in st.session_state.chat_history:
    role = "🌼" if msg["role"] == "user" else "🌀"
    with st.chat_message(msg["role"], avatar=role):
        st.write(msg["content"])
        if "image" in msg and msg["image"]:
            st.image(msg["image"], caption="Shared Image", use_container_width=True)
        if "audio" in msg and msg["audio"]:
            st.audio(msg["audio"], format="audio/mp3")


# 🪟 Clear
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🪟", help="Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# 🏦 Footer
st.markdown(
    """
    <hr style='margin-top:40px;border:1px solid #444;'/>
    <div style='text-align:center; color:gray; font-size:13px;'>
        ⚡ Powered by <strong>Aman Chaudhary</strong> | Built with ❤️ & sarcasm
    </div>
    """,
    unsafe_allow_html=True
)

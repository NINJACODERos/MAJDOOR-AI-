import sys, os, re, time, io, base64, asyncio, requests, streamlit as st

# 🔧 Point g4f's cookie/HAR storage at a writable directory (Streamlit Cloud's
# filesystem is ephemeral/restricted, so g4f's default path can fail).
os.environ.setdefault("G4F_COOKIES_DIR", "/tmp/g4f_har_and_cookies")
os.makedirs(os.environ["G4F_COOKIES_DIR"], exist_ok=True)

# Adjust path to your local gpt4free clone
sys.path.append(os.path.abspath("../gpt4free"))
import g4f
from g4f.client import Client as G4FClient
try:
    g4f.cookies_dir = os.environ["G4F_COOKIES_DIR"]
except Exception:
    pass

# 🔊 Audio providers.
# We call the `edge_tts` package DIRECTLY (not through g4f.Provider.EdgeTTS),
# because g4f's EdgeTTS wrapper currently throws `VoicesManager is not
# defined` — a bug inside g4f itself, not our code. Calling edge_tts
# directly gets the exact same free Microsoft voice service, no g4f bug,
# no API key, no bot-check wall.
try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    from g4f.Provider import OpenAIFM
except ImportError:
    OpenAIFM = None
try:
    from g4f.Provider import PollinationsAI
except ImportError:
    PollinationsAI = None

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


# 🔊 Audio generation.
# Order: direct edge_tts (free, no key, bypasses g4f's buggy EdgeTTS
# wrapper) -> OpenAIFM -> PollinationsAI. Each is a separate fallback
# in case one is down/blocked.
def _edge_tts_generate_sync(text: str, voice: str = "hi-IN-MadhurNeural") -> bytes:
    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())
    finally:
        loop.close()


def generate_audio_native(prompt: str):
    errors = []

    if edge_tts is not None:
        try:
            audio_bytes = _edge_tts_generate_sync(prompt, voice="hi-IN-MadhurNeural")
            if audio_bytes:
                return audio_bytes, None
        except Exception as e:
            errors.append(f"edge_tts (direct) failed: {e}")

    if OpenAIFM is not None:
        try:
            client = G4FClient(provider=OpenAIFM)
            response = client.media.generate(
                prompt,
                model="gpt-4o-mini-tts",
                audio={"voice": "coral"},
            )
            item = response.data[0]
            if getattr(item, "b64_json", None):
                return base64.b64decode(item.b64_json), None
            if getattr(item, "url", None):
                r = requests.get(item.url, timeout=20)
                if r.ok:
                    return r.content, None
        except Exception as e:
            errors.append(f"OpenAIFM failed: {e}")

    if PollinationsAI is not None:
        try:
            client = G4FClient(provider=PollinationsAI)
            response = client.media.generate(
                prompt,
                model="gpt-4o-mini-audio",
                audio={"voice": "alloy", "format": "mp3"},
            )
            item = response.data[0]
            if getattr(item, "b64_json", None):
                return base64.b64decode(item.b64_json), None
            if getattr(item, "url", None):
                r = requests.get(item.url, timeout=20)
                if r.ok:
                    return r.content, None
        except Exception as e:
            errors.append(f"PollinationsAI failed: {e}")

    return None, " | ".join(errors) if errors else "Koi audio provider available nahi hai."


# 💡 Web/Image/Audio triggers
def handle_triggered_response(text):
    # Case-insensitive "audio/ " prefix handling
    if text.lower().startswith("audio/ "):
        prompt = text[7:].strip()
        
        # Strip internal binary keys to keep the history context perfectly clean
        safe_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history if "content" in m]
        messages = [{"role": "system", "content": get_prompt()}] + safe_history + [{"role": "user", "content": prompt}]
        
        try:
            # 1. Generate text via standard g4f
            raw = g4f.ChatCompletion.create(model=g4f.models.default, messages=messages, stream=False)
            reply_text = raw if isinstance(raw, str) else raw.get("choices", [{}])[0].get("message", {}).get("content", "Arey kuch nahi mila.")
            reply_text = strip_reasoning(reply_text)
            
            # 2. Convert to Audio (direct edge_tts -> OpenAIFM -> PollinationsAI)
            audio_data, err = generate_audio_native(reply_text)
            if audio_data is None:
                return f"❌ Audio banne mein error aa gaya majdoor bhai: {err}"

            # Return both so we can display text + play the matching audio
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
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    trig = handle_triggered_response(user_input.strip())
    
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
        # Filter audio keys out before feeding history context to g4f
        safe_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history if "content" in m]
        messages = [{"role": "system", "content": get_prompt()}] + safe_history
        raw = g4f.ChatCompletion.create(model=g4f.models.default, messages=messages, stream=False)
        response = raw if isinstance(raw, str) else raw.get("choices", [{}])[0].get("message", {}).get("content", "Arey kuch khaas nahi mila.")
        response = strip_reasoning(response)
        response = add_sarcasm_emoji(response)
        st.session_state.chat_history.append({"role": "assistant", "content": response})

# 💬 History Loop (Both text and audio inside the exact same chat message bubble)
for msg in st.session_state.chat_history:
    role = "🌼" if msg["role"] == "user" else "🌀"
    with st.chat_message(msg["role"], avatar=role):
        st.write(msg["content"])
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

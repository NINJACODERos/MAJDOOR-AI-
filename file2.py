import streamlit as st
import g4f
from g4f.client import AsyncClient # Changed to AsyncClient
import tempfile
import os
import asyncio
import nest_asyncio
import inspect

# Apply asyncio patch to prevent Streamlit threading conflicts
nest_asyncio.apply()

st.set_page_config(page_title="MAJDOOR_AI", page_icon="🌀", layout="centered")

st.title("🌀 MAJDOOR_AI")
st.markdown("### Upload an image and get roasted! 🌼")

# File uploader for the image
uploaded_file = st.file_uploader("Majdoor ko dikhane ke liye photo upload karo:", type=["png", "jpg", "jpeg"])

# ---------------------------------------------------------
# CRITICAL FIX: Wrap the API calls in a proper async task 
# to guarantee an event loop context for 'anyio'
# ---------------------------------------------------------
async def process_roast_and_audio(img_path):
    # Initialize the client INSIDE the task so it binds to the correct event loop
    client = AsyncClient()
    
    # Step 2: Generate the roast (Vision)
    chat_response = await client.chat.completions.create(
        model=g4f.models.default,
        messages=[{"role": "user", "content": "Roast this image in a funny, sarcastic way in Hinglish."}],
        image=open(img_path, "rb")
    )
    roast_text = chat_response.choices[0].message.content

    # Step 3: Generate the Audio (Text-to-Speech)
    audio_response = await client.audio.speech.create(
        model="tts-1",
        voice="onyx",
        input=roast_text
    )
    
    # Save audio to a temporary file manually to ensure async compatibility
    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    audio_path = tmp_audio.name
    
    # Safely handle the audio generation output regardless of the async provider
    if hasattr(audio_response, 'stream_to_file'):
        if inspect.iscoroutinefunction(audio_response.stream_to_file):
            await audio_response.stream_to_file(audio_path)
        else:
            audio_response.stream_to_file(audio_path)
    elif hasattr(audio_response, 'iter_bytes'):
        with open(audio_path, 'wb') as f:
            async for chunk in audio_response.iter_bytes():
                f.write(chunk)
    elif hasattr(audio_response, 'content'):
        with open(audio_path, 'wb') as f:
            f.write(audio_response.content)
    else:
        with open(audio_path, 'wb') as f:
            f.write(audio_response) # Fallback if returned as raw bytes

    return roast_text, audio_path

# ---------------------------------------------------------
# STREAMLIT UI & EXECUTION FLOW
# ---------------------------------------------------------
if uploaded_file is not None:
    st.image(uploaded_file, caption="Selected Image", use_column_width=True)
    
    if st.button("Roast this image! 🔥"):
        
        # Step 1: Save the uploaded image to a temporary file for g4f to read
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
            tmp_img.write(uploaded_file.getvalue())
            img_path = tmp_img.name

        try:
            with st.spinner("Majdoor is looking at your image and warming up his vocal cords..."):
                
                # RUN THE ASYNC FUNCTION
                # This creates the main task that 'anyio' was missing!
                roast_text, audio_path = asyncio.run(process_roast_and_audio(img_path))
                
                st.success("### The Roast:")
                st.write(roast_text)

                # Step 4: Play the audio in the app
                st.audio(audio_path, format="audio/mp3")
                
                # Clean up the temporary audio file
                os.remove(audio_path)

        except Exception as e:
            # Graceful error handling so the app doesn't crash
            st.error(f"❌ Majdoor is on a tea break! The free AI providers are currently busy or blocking the request. \n\n**Technical Details:** {e}")
            st.info("Try clicking the roast button again in a few seconds.")
            
        finally:
            # Clean up the temporary image file
            if os.path.exists(img_path):
                os.remove(img_path)

st.markdown("---")
st.caption("⚡ Powered by Aman Chaudhary | Built with ❤️ & sarcasm")
            

import streamlit as st
import g4f
from g4f.client import Client
import tempfile
import os
import nest_asyncio

# Apply asyncio patch to prevent Streamlit threading conflicts with g4f
nest_asyncio.apply()

# Initialize the g4f client
client = Client()

st.set_page_config(page_title="MAJDOOR_AI", page_icon="🌀", layout="centered")

st.title("🌀 MAJDOOR_AI")
st.markdown("### Upload an image and get roasted! 🌼")

# File uploader for the image
uploaded_file = st.file_uploader("Majdoor ko dikhane ke liye photo upload karo:", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Selected Image", use_column_width=True)
    
    if st.button("Roast this image! 🔥"):
        
        # Step 1: Save the uploaded image to a temporary file for g4f to read
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
            tmp_img.write(uploaded_file.getvalue())
            img_path = tmp_img.name

        try:
            with st.spinner("Majdoor is looking at your image..."):
                # Step 2: Generate the roast (Vision)
                # Using standard default routing, let g4f auto-select the best free vision provider
                chat_response = client.chat.completions.create(
                    model=g4f.models.default,
                    messages=[{"role": "user", "content": "Roast this image in a funny, sarcastic way in Hinglish."}],
                    image=open(img_path, "rb")
                )
                
                roast_text = chat_response.choices[0].message.content
                st.success("### The Roast:")
                st.write(roast_text)

            with st.spinner("Majdoor is warming up his vocal cords..."):
                # Step 3: Generate the Audio (Text-to-Speech)
                audio_response = client.audio.speech.create(
                    model="tts-1",
                    voice="onyx", # Deep voice model
                    input=roast_text
                )
                
                # Save audio to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                    audio_response.stream_to_file(tmp_audio.name)
                    audio_path = tmp_audio.name
                
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

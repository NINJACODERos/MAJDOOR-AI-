import g4f
import pyttsx3

def init_audio():
    """Initialize the text-to-speech engine."""
    engine = pyttsx3.init()
    # Set speech rate (optional)
    rate = engine.getProperty('rate')
    engine.setProperty('rate', rate - 20) # Slow down the speech a bit
    return engine

def speak(engine, text):
    """Speak the given text using the TTS engine."""
    engine.say(text)
    engine.runAndWait()

def get_ai_response(prompt):
    """Get a response from the g4f AI."""
    try:
        response = g4f.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
        )
        return response
    except Exception as e:
        return f"An error occurred: {e}"

def main():
    print("Initializing AI Audio Assistant...")
    engine = init_audio()
    print("Ready! Type 'quit' or 'exit' to stop.")
    
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ['quit', 'exit']:
            speak(engine, "Goodbye!")
            break
        
        print("AI is thinking...")
        response = get_ai_response(user_input)
        
        print(f"AI: {response}")
        speak(engine, response)

if __name__ == "__main__":
    main()
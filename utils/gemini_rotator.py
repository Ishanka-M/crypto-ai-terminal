"""
Gemini API Key Rotation Manager
Keys limit වෙද්දී automatically rotate වෙනවා
Streamlit secrets එකෙන් keys load කරනවා
"""
import google.generativeai as genai
import streamlit as st
import time

def _load_keys() -> list:
    """Streamlit secrets එකෙන් Gemini keys load කරනවා"""
    keys = []
    try:
        gem = st.secrets.get("gemini", {})
        for i in range(1, 8):
            k = gem.get(f"key_{i}", "").strip()
            if k and not k.startswith("YOUR_") and len(k) > 10:
                keys.append(k)
    except Exception:
        pass
    # Fallback: hardcode කරන්න ඕනේ නම් මෙතන දාන්න
    # if not keys:
    #     keys = ["AIzaSy..."]
    return keys if keys else ["INVALID_KEY"]

class GeminiRotator:
    def __init__(self):
        self.keys = _load_keys()
        self.current_index = 0
        self.failed_keys = set()

    def get_current_key(self):
        return self.keys[self.current_index]

    def rotate(self):
        self.failed_keys.add(self.current_index)
        for i in range(len(self.keys)):
            if i not in self.failed_keys:
                self.current_index = i
                return True
        self.failed_keys.clear()  # Reset and try again
        self.current_index = 0
        return False

    def configure(self):
        genai.configure(api_key=self.get_current_key())

    def generate(self, prompt: str, retries: int = 7) -> str:
        for attempt in range(retries):
            try:
                self.configure()
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                error_msg = str(e).lower()
                if "quota" in error_msg or "limit" in error_msg or "429" in error_msg or "exhausted" in error_msg:
                    rotated = self.rotate()
                    if not rotated:
                        return "⚠️ All Gemini API keys exhausted. Please wait or add more keys."
                    time.sleep(1)
                else:
                    return f"❌ Gemini Error: {str(e)}"
        return "⚠️ Max retries reached."

@st.cache_resource
def get_gemini_rotator():
    return GeminiRotator()

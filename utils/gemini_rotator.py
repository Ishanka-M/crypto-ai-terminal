# utils/gemini_rotator.py
# ============================================
# Gemini API Key Rotator
# - Supports multiple API keys (rotation)
# - Safe import (no crash if not installed)
# - Saves keys to Google Sheets
# - Quota tracking per key
# ============================================

import os
import time
import json
import streamlit as st
from datetime import datetime
from typing import Optional

# ── Safe import ─────────────────────────────
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

# ── Default model ───────────────────────────
DEFAULT_MODEL  = "gemini-2.5-flash-preview-05-20"
DEFAULT_MODEL2 = "gemini-2.5-pro-preview-05-06"


# ─────────────────────────────────────────
# KEY ROTATOR CLASS
# ─────────────────────────────────────────

class GeminiKeyRotator:
    """
    Manages multiple Gemini API keys with automatic rotation.

    When one key hits quota limit → automatically switches to next key.
    Tracks usage per key.
    """

    def __init__(self, api_keys: list, model_name: str = DEFAULT_MODEL):
        if not GENAI_AVAILABLE:
            raise RuntimeError(
                "google-generativeai not installed.\n"
                "Add to requirements.txt: google-generativeai>=0.5.0"
            )
        if not api_keys:
            raise ValueError("No API keys provided.")

        self.api_keys    = [k.strip() for k in api_keys if k.strip()]
        self.model_name  = model_name
        self.current_idx = 0
        self.usage       = {k: {"calls": 0, "errors": 0, "last_used": None}
                            for k in self.api_keys}
        self._configure_current()

    def _configure_current(self):
        """Applies the current key to the genai library."""
        key = self.api_keys[self.current_idx]
        genai.configure(api_key=key)

    def _rotate(self):
        """Switches to the next available key."""
        self.current_idx = (self.current_idx + 1) % len(self.api_keys)
        self._configure_current()
        key = self.api_keys[self.current_idx]
        st.toast(f"🔄 Rotated to API key #{self.current_idx + 1}", icon="🔑")
        return key

    @property
    def current_key(self) -> str:
        return self.api_keys[self.current_idx]

    @property
    def current_key_masked(self) -> str:
        k = self.current_key
        return f"{k[:8]}...{k[-4:]}" if len(k) > 12 else "****"

    def generate(self, prompt: str, system: str = "", retries: int = 3) -> str:
        """
        Sends a prompt to Gemini with automatic key rotation on failure.

        Args:
            prompt:  User message
            system:  System instruction
            retries: How many times to retry (rotating keys)

        Returns:
            Generated text response
        """
        if not GENAI_AVAILABLE:
            return "❌ Gemini not available — install google-generativeai"

        last_error = None
        for attempt in range(retries):
            try:
                key = self.current_key
                self.usage[key]["calls"] += 1
                self.usage[key]["last_used"] = datetime.now().isoformat()

                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system or "You are a professional crypto trading analyst.",
                )
                response = model.generate_content(prompt)
                return response.text

            except Exception as e:
                err_str = str(e).lower()
                last_error = str(e)
                key = self.current_key
                self.usage[key]["errors"] += 1

                # Quota exceeded → rotate key
                if any(x in err_str for x in ["quota", "rate", "429", "limit", "exhausted"]):
                    if len(self.api_keys) > 1:
                        self._rotate()
                        time.sleep(1)
                        continue
                    else:
                        return f"⚠️ Quota exceeded. Add more API keys in Settings."

                # Auth error → skip this key
                elif any(x in err_str for x in ["api_key", "invalid", "401", "403"]):
                    if len(self.api_keys) > 1:
                        self._rotate()
                        continue
                    else:
                        return f"❌ Invalid API key. Check your key in Settings."

                # Other error → retry after short wait
                time.sleep(2 ** attempt)

        return f"❌ Gemini API error after {retries} attempts: {last_error}"

    def get_usage_stats(self) -> list:
        """Returns usage stats for all keys."""
        stats = []
        for i, key in enumerate(self.api_keys):
            u = self.usage[key]
            stats.append({
                "index":     i + 1,
                "key":       f"{key[:8]}...{key[-4:]}",
                "calls":     u["calls"],
                "errors":    u["errors"],
                "last_used": u["last_used"] or "Never",
                "active":    i == self.current_idx,
            })
        return stats


# ─────────────────────────────────────────
# SINGLETON — one rotator per session
# ─────────────────────────────────────────

def get_gemini_rotator() -> Optional[GeminiKeyRotator]:
    """
    Returns the cached GeminiKeyRotator from session state.
    Returns None if no keys configured.
    """
    if not GENAI_AVAILABLE:
        return None

    # Check session state
    if "gemini_rotator" in st.session_state and st.session_state.gemini_rotator:
        return st.session_state.gemini_rotator

    # Try to build from saved keys (session or secrets)
    keys = _load_keys_from_sources()
    if not keys:
        return None

    try:
        rotator = GeminiKeyRotator(keys)
        st.session_state.gemini_rotator = rotator
        return rotator
    except Exception:
        return None


def _load_keys_from_sources() -> list:
    """Loads API keys from all available sources (priority order)."""
    keys = []

    # 1. From session state (user entered in UI)
    if "gemini_api_keys" in st.session_state:
        keys = [k for k in st.session_state.gemini_api_keys if k.strip()]
        if keys:
            return keys

    # 2. From Streamlit secrets (Streamlit Cloud deployment)
    try:
        secret_keys = st.secrets.get("GEMINI_API_KEYS", "")
        if secret_keys:
            keys = [k.strip() for k in secret_keys.split(",") if k.strip()]
            if keys:
                return keys
        # Single key format
        single = st.secrets.get("GEMINI_API_KEY", "")
        if single:
            return [single.strip()]
    except Exception:
        pass

    # 3. From environment (.env file)
    env_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    if env_keys:
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]

    return keys


def initialize_rotator_from_keys(keys: list, model: str = DEFAULT_MODEL) -> GeminiKeyRotator:
    """
    Creates and saves a new rotator with provided keys.
    Called from the Settings page when user saves keys.
    """
    rotator = GeminiKeyRotator(keys, model)
    st.session_state.gemini_rotator    = rotator
    st.session_state.gemini_api_keys   = keys
    st.session_state.gemini_model      = model
    return rotator


def quick_chat(prompt: str, system: str = "") -> str:
    """
    Convenience function: get a response without managing the rotator.
    Returns error message if Gemini not available.
    """
    rotator = get_gemini_rotator()
    if not rotator:
        return "⚠️ Gemini API not configured. Add your API key in ⚙️ Settings."
    return rotator.generate(prompt, system)


# ─────────────────────────────────────────
# AVAILABILITY CHECK
# ─────────────────────────────────────────

def is_gemini_available() -> bool:
    """Returns True if Gemini is installed AND keys are configured."""
    if not GENAI_AVAILABLE:
        return False
    return get_gemini_rotator() is not None


def get_genai_install_status() -> dict:
    return {
        "installed":   GENAI_AVAILABLE,
        "configured":  is_gemini_available(),
        "key_count":   len(_load_keys_from_sources()),
    }

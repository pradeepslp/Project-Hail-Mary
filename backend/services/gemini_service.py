import os
import google.nerativeai as genai
from typing import Optional

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("NEXT_PUBLIC_GEMINI_API_KEY")
        self.enabled = False
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-2.5-flash")
                self.enabled = True
            except Exception as e:
                print(f"[GeminiService] Error configuring Gemini API: {e}")

    async def generate_response(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.enabled:
            # Try reloading key in case env changed
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("NEXT_PUBLIC_GEMINI_API_KEY")
            if self.api_key:
                try:
                    genai.configure(api_key=self.api_key)
                    self.model = genai.GenerativeModel("gemini-2.5-flash")
                    self.enabled = True
                except Exception as e:
                    return f"[Error] Gemini API configuration failed: {e}"
            else:
                raise ValueError("Gemini API key is not set. Please add GEMINI_API_KEY to your environment/dotenv file.")

        # Call the model
        try:
            if system_instruction:
                # Use system_instruction parameter if supported, or include it in the config/prompt
                model_with_instruction = genai.GenerativeModel(
                    "gemini-2.5-flash",
                    system_instruction=system_instruction
                )
                response = model_with_instruction.generate_content(prompt)
            else:
                response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"[GeminiService] API call failed: {e}")
            raise e

gemini_service = GeminiService()

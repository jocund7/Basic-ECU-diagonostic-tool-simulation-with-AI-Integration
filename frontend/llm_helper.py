import groq
import os


class UDSExplainAI:
    def __init__(self):
        self.client = groq.Client(api_key=os.getenv("GROQ_API_KEY"))
        self.system_prompt = """You are an automotive diagnostics expert specializing in UDS (ISO 14229). 
        Your task is to explain UDS response codes in a concise, user-friendly format.
        1. First line: Response code meaning (max 5 words)
        2. Bullet points: Top 3 causes (emoji + 3-5 words each)
        3. Action steps (numbered)
        4. Standard reference
        5. Keep entire response under 100 words
        6. Format in Markdown"""
    
    def explain_response(self, raw_response: str, context: str = ""):
        try:
            response = self.client.chat.completions.create(
                model="deepseek-r1-distill-llama-70b",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Explain this UDS response: {raw_response}. Context: {context}"}
                ],
                temperature=0.4
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ AI explanation unavailable: {str(e)}"
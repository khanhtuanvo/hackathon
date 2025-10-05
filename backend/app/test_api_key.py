import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# The OpenAI client automatically looks for the OPENAI_API_KEY 
# environment variable, so you don't have to pass it manually.
# It will raise an error if the key is not found.
client = OpenAI()

# Example function to generate content
def generate_text_openai(prompt):
    try:
        completion = client.chat.completions.create(
          model="gpt-3.5-turbo",  # A popular and cost-effective model
          messages=[
            {"role": "user", "content": prompt}
          ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# --- Test the function ---
if __name__ == "__main__":
    user_prompt = "Explain what an API key is in 3 sentences."
    generated_response = generate_text_openai(user_prompt)

    if generated_response:
        print("--- OpenAI Response ---")
        print(generated_response)
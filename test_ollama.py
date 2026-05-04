import ollama

response = ollama.chat(
    model="llama3.2:3b",
    messages=[
        {"role": "user", "content": "Say hello and tell me one interesting fact about Apple stock in two sentences."}
    ]
)

print(response.message.content)
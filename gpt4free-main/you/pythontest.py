import phind
# simple request with links and details
response = phind.Completion.create(
    prompt       = "hello world",
    detailed     = True,
    includelinks = True,)

print(response)

# {
#     "response": "...",
#     "links": [...],
#     "extra": {...},
#         "slots": {...}
#     }
# }

#chatbot

chat = []

while True:
    prompt = input("You: ")
    
    response = phind.Completion.create(
        prompt  = prompt,
        chat    = chat)
    
    print("Bot:", response["response"])
    
    chat.append({"question": prompt, "answer": response["response"]})
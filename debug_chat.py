from app.config import Settings
from app.gemini_client import GeminiClient

settings = Settings.from_env()
print('Using model:', settings.gemini_model)
client = GeminiClient(settings.gemini_api_key or '', settings.gemini_model)
print('Client created:', type(client.client))
print('Chat created:', type(client.chat))

try:
    response = client.chat.send_message('hello there')
    print('RESPONSE TYPE:', type(response))
    print('RESPONSE TEXT:', getattr(response, 'text', None))
    print('FULL RESPONSE:', response)
except Exception as exc:
    import traceback
    traceback.print_exc()

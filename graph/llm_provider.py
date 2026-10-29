"""Optional OpenAI-compatible LLM gateway. Explicit opt-in; no secrets in source."""
import json
import os
import urllib.request
from urllib.parse import urlparse

class LLMError(RuntimeError):
    pass

def chat_json(system: str, payload: dict) -> dict:
    token = os.getenv('SCOUTY_LLM_API_KEY', '')
    if not token:
        raise LLMError('SCOUTY_LLM_API_KEY is not set')
    endpoint = os.getenv('SCOUTY_LLM_ENDPOINT', 'https://api.openai.com/v1/chat/completions')
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise LLMError('LLM endpoint must be a valid HTTPS URL')
    body = json.dumps({'model':os.getenv('SCOUTY_LLM_MODEL', 'gpt-4o-mini'),
                       'temperature':0, 'response_format':{'type':'json_object'},
                       'messages':[{'role':'system','content':system},
                                   {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]}).encode('utf-8')
    req=urllib.request.Request(endpoint, data=body, method='POST', headers={
        'Authorization':'Bearer '+token, 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            result=json.loads(response.read(200000).decode('utf-8'))
        return json.loads(result['choices'][0]['message']['content'])
    except Exception as exc:
        raise LLMError('LLM request failed (check API key, endpoint and model)') from exc

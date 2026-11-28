"""In-process GGUF inference: no account, network call or model server."""
from crewai import BaseLLM
from pydantic import PrivateAttr
from typing import Any


class LocalGGUF(BaseLLM):
    _runtime: Any = PrivateAttr()
    def __init__(self, path):
        super().__init__(model='local/gguf', temperature=0.2)
        from llama_cpp import Llama
        self._runtime = Llama(model_path=path, n_ctx=8192, n_gpu_layers=0, verbose=False)

    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
        if isinstance(messages, str): messages = [{'role': 'user', 'content': messages}]
        result = self._runtime.create_chat_completion(messages=messages, temperature=0.2,
            max_tokens=2048, stop=self.stop_sequences or None)
        return result['choices'][0]['message']['content'] or ''

    def supports_function_calling(self): return False
    def supports_stop_words(self): return True
    def get_context_window_size(self): return 8192

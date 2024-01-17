import asyncio
import functools

from alpha_codium.llm.ai_handler import AiHandler
from alpha_codium.llm.ai_invoker import send_inference


class SimplePrompt:
    def __init__(self, system_prompt="", temperature=0.2, frequency_penalty=0):
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.frequency_penalty = frequency_penalty
        self.ai_handler = AiHandler()

    async def _run(self, model, user_prompt):
        response, finish_reason = await self.ai_handler.chat_completion(
            model=model,
            temperature=self.temperature,
            frequency_penalty=self.frequency_penalty,
            system=self.system_prompt,
            user=user_prompt,
        )
        return response

    async def run(self, user_prompt):
        f = functools.partial(self._run, user_prompt=user_prompt)
        response = await send_inference(f)
        return response


if __name__ == "__main__":
    p = SimplePrompt()
    asyncio.run(p.run("what is the capital city of Israel"))

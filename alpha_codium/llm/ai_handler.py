import logging
import os
from enum import Enum

import litellm
import openai
from aiolimiter import AsyncLimiter
from litellm import acompletion
from litellm import RateLimitError
from litellm.exceptions import APIError
# from openai.error import APIError, RateLimitError, Timeout, TryAgain
from retry import retry

from alpha_codium.settings.config_loader import get_settings
from alpha_codium.log import get_logger

logger = get_logger(__name__)
OPENAI_RETRIES = 5

class Provider(Enum):
    OPENAI = "openai"
    DEEPSEEK_LEGACY = "deepseek-legacy"
    AWSBEDROCK = "awsbedrock"
    UNKNOWN = "unknown"

class AiHandler:
    def __init__(self):
        self.provider = Provider.UNKNOWN
        """
        Initializes the OpenAI API key and other settings from a configuration file.
        Raises a ValueError if the OpenAI key is missing.
        """
        self.limiter = AsyncLimiter(get_settings().config.max_requests_per_minute)
        if get_settings().get("config.model").lower().startswith("bedrock"):
            self.provider = Provider.AWSBEDROCK
        elif "gpt" in get_settings().get("config.model").lower():
            self.provider = Provider.OPENAI
            try:
                openai.api_key = get_settings().openai.key
                litellm.openai_key = get_settings().openai.key
            except AttributeError as e:
                raise ValueError("OpenAI key is required") from e
        elif "deepseek" in get_settings().get("config.model"):
            self.provider = Provider.DEEPSEEK_LEGACY
            litellm.register_prompt_template(
                model="huggingface/deepseek-ai/deepseek-coder-33b-instruct",
                roles={
                    "system": {
                        "pre_message": "",
                        "post_message": "\n"
                    },
                    "user": {
                        "pre_message": "### Instruction:\n",
                        "post_message": "\n### Response:\n"
                    },
                },

            )

        self.azure = False
        litellm.set_verbose=get_settings().get("litellm.set_verbose", False)
        litellm.drop_params=get_settings().get("litellm.drop_params", False)

    @retry(
        exceptions=(AttributeError, RateLimitError),
        tries=OPENAI_RETRIES,
        delay=2,
        backoff=2,
        jitter=(1, 3),
    )
    async def chat_completion(
            self, model: str,
            system: str,
            user: str,
            temperature: float = 0.2,
            frequency_penalty: float = 0.0,
    ):
        try:
            async with self.limiter:
                logger.info("-----------------")
                logger.info(f"Running inference ... provider: {self.provider}, model: {model}")
                logger.debug(f"system:\n{system}")
                logger.debug(f"user:\n{user}")
                if self.provider == Provider.DEEPSEEK_LEGACY:
                    response = await self._deepseek_chat_completion(
                        model=model,
                        system=system,
                        user=user,
                        temperature=temperature,
                        frequency_penalty=frequency_penalty,
                    )
                elif self.provider == Provider.OPENAI:
                    response = await self._openai_chat_completion(
                        model=model,
                        system=system,
                        user=user,
                        temperature=temperature,
                        frequency_penalty=frequency_penalty,
                    )
                else:
                    response = await self._awsbedrock_chat_completion(
                        model=model,
                        system=system,
                        user=user,
                        temperature=temperature
                    )
        except (APIError) as e:
            logging.error("Error during OpenAI inference")
            raise
        except RateLimitError as e:
            logging.error("Rate limit error during OpenAI inference")
            raise
        except Exception as e:
            logging.error("Unknown error during OpenAI inference: ", e)
            raise APIError from e
        if response is None or len(response["choices"]) == 0:
            raise APIError
        resp = response["choices"][0]["message"]["content"]
        finish_reason = response["choices"][0]["finish_reason"]
        logger.debug(f"response:\n{resp}")
        logger.info('done')
        logger.info("-----------------")
        return resp, finish_reason

    async def _deepseek_chat_completion(self, model, system, user, temperature, frequency_penalty):
        response = await acompletion(
            model="huggingface/deepseek-ai/deepseek-coder-33b-instruct",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            api_base=get_settings().get("config.model"),
            temperature=temperature,
            repetition_penalty=frequency_penalty+1, # the scale of TGI is different from OpenAI
            force_timeout=get_settings().config.ai_timeout,
            max_tokens=2000,
            stop=['<|EOT|>'],
        )
        response["choices"][0]["message"]["content"] = response["choices"][0]["message"]["content"].rstrip()
        if response["choices"][0]["message"]["content"].endswith("<|EOT|>"):
            response["choices"][0]["message"]["content"] = response["choices"][0]["message"]["content"][:-7]
        return response

    async def _openai_chat_completion(self, model, system, user, temperature, frequency_penalty):
        deployment_id = get_settings().get("OPENAI.DEPLOYMENT_ID", None)
        if get_settings().config.verbosity_level >= 2:
            logging.debug(
                f"Generating completion with {model}"
                f"{(' from deployment ' + deployment_id) if deployment_id else ''}"
            )
        response = await acompletion(
            model=model,
            deployment_id=deployment_id,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            frequency_penalty=frequency_penalty,
            force_timeout=get_settings().config.ai_timeout,
        )
        return response

    async def _awsbedrock_chat_completion(self, model, system, user, temperature):
        response = await acompletion(
            model=model,
            user=user,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature
        )
        return response
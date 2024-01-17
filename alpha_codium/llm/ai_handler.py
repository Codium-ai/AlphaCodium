import logging
import os

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


class AiHandler:
    """
    This class handles interactions with the OpenAI API for chat completions.
    It initializes the API key and other settings from a configuration file,
    and provides a method for performing chat completions using the OpenAI ChatCompletion API.
    """

    def __init__(self):
        """
        Initializes the OpenAI API key and other settings from a configuration file.
        Raises a ValueError if the OpenAI key is missing.
        """
        self.limiter = AsyncLimiter(get_settings().config.max_requests_per_minute)
        try:
            openai.api_key = get_settings().openai.key
            litellm.openai_key = get_settings().openai.key
            self.azure = False
            if "deepseek" in get_settings().get("config.model"):
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
        except AttributeError as e:
            raise ValueError("OpenAI key is required") from e

    @property
    def deployment_id(self):
        """
        Returns the deployment ID for the OpenAI API.
        """
        return get_settings().get("OPENAI.DEPLOYMENT_ID", None)

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
            deployment_id = self.deployment_id
            if get_settings().config.verbosity_level >= 2:
                logging.debug(
                    f"Generating completion with {model}"
                    f"{(' from deployment ' + deployment_id) if deployment_id else ''}"
                )

            async with self.limiter:
                logger.info("-----------------")
                logger.info("Running inference ...")
                logger.debug(f"system:\n{system}")
                logger.debug(f"user:\n{user}")
                if "deepseek" in get_settings().get("config.model"):
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
                else:
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

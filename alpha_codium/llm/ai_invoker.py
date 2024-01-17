import logging
import traceback
from typing import Callable, List

from alpha_codium.settings.config_loader import get_settings


async def send_inference(f: Callable):
    all_models = _get_all_models()
    all_deployments = _get_all_deployments(all_models)
    # try each (model, deployment_id) pair until one is successful, otherwise raise exception
    for i, (model, deployment_id) in enumerate(zip(all_models, all_deployments)):
        try:
            get_settings().set("openai.deployment_id", deployment_id)
            return await f(model)
        except Exception:
            logging.warning(
                f"Failed to generate prediction with {model}"
                f"{(' from deployment ' + deployment_id) if deployment_id else ''}: "
                f"{traceback.format_exc()}"
            )
            if i == len(all_models) - 1:  # If it's the last iteration
                raise  # Re-raise the last exception


def _get_all_models() -> List[str]:
    model = get_settings().config.model
    fallback_models = get_settings().config.fallback_models
    if not isinstance(fallback_models, list):
        fallback_models = [m.strip() for m in fallback_models.split(",")]
    all_models = [model] + fallback_models
    return all_models


def _get_all_deployments(all_models: List[str]) -> List[str]:
    deployment_id = get_settings().get("openai.deployment_id", None)
    fallback_deployments = get_settings().get("openai.fallback_deployments", [])
    if not isinstance(fallback_deployments, list) and fallback_deployments:
        fallback_deployments = [d.strip() for d in fallback_deployments.split(",")]
    if fallback_deployments:
        all_deployments = [deployment_id] + fallback_deployments
        if len(all_deployments) < len(all_models):
            raise ValueError(
                f"The number of deployments ({len(all_deployments)}) "
                f"is less than the number of models ({len(all_models)})"
            )
    else:
        all_deployments = [deployment_id] * len(all_models)
    return all_deployments

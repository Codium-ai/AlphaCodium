import functools
import logging
from alpha_codium.gen.utils import postprocess_response
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_baseline(self, problem):
    try:
        logging.info("Using baseline prompt")
        f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_baseline")
        response_baseline, _ = await send_inference(f)
        recent_solution =  postprocess_response(response_baseline)
        return recent_solution
    except Exception as e:
        logging.error(f"Error: {e}")
        exit(-1)

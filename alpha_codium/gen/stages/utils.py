from alpha_codium.log import get_logger

logger = get_logger(__name__)


def set_configurations(problem, iteration=0):
    # configurations
    problem = {k: problem.get(k) for k in ["name", "description", "public_tests"]}
    problem['iteration'] = iteration

    # initialize passed tests field
    problem['passed_tests'] = {}
    problem['passed_tests']['inputs'] = []
    problem['passed_tests']['outputs'] = []

    # shorter description, without the input-output examples
    if '\nExample\n' in problem['description']:
        problem['description_short'] = problem['description'].split('\nExample\n')[0].strip()
    elif '\nExamples\n' in problem['description']:
        problem['description_short'] = problem['description'].split('\nExamples\n')[0].strip()
    else:
        logger.info(f"could not split description to short description, description: {problem['description']}")
        problem['description_short'] = problem['description']
    return problem
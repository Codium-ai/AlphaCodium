import logging
import inspect
from functools import wraps

logging.basicConfig(level=logging.DEBUG)

def log_inputs_outputs_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        arg_str = ", ".join([f"{repr(arg)}" for arg in args])
        kwarg_str = ", ".join([f"{key}={repr(value)}" for key, value in kwargs.items()])
        logging.debug(f"Calling {func.__name__} with arguments: {arg_str}, {kwarg_str}")

        try:
            result = func(*args, **kwargs)
            logging.debug(f"{func.__name__} returned: {repr(result)}")
            return result
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            raise  # Re-raise the exception

    return wrapper

def apply_logging_decorator_to_module(module):
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj):
            setattr(module, name, log_inputs_outputs_errors(obj))

# Example usage
import test  # Replace with the actual module name

# Apply the decorator to all functions in the module
apply_logging_decorator_to_module(test)

# Now, when you call functions from my_module, the decorator will log inputs, outputs, and errors

test.main()
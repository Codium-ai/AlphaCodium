import pathlib
from os import listdir
from os.path import abspath, dirname, join, isfile
import glob

from dynaconf import Dynaconf

PR_AGENT_TOML_KEY = "pr-agent"

current_dir = dirname(abspath(__file__))
# setting_dir = join(current_dir, "settings")
setting_dir = current_dir



toml_files = list(pathlib.Path(join(setting_dir)).glob('*.toml')) # includes hidden files
global_settings = Dynaconf(
    envvar_prefix=False,
    merge_enabled=True,
    settings_files=toml_files,
)


def get_settings():
    return global_settings

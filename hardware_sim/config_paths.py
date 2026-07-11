from importlib.resources import files

PACKAGE_NAME = "hardware_sim"
DATA_DIR = "data"
RUNTIME_CONFIG_FILE = "runtime_config.json"
PARTS_CATALOG_FILE = "parts_catalog.json"
WORKLOADS_CONFIG_FILE = "workloads.json"


def runtime_config_resource():
    return files(PACKAGE_NAME).joinpath(DATA_DIR, RUNTIME_CONFIG_FILE)


def parts_catalog_resource():
    return files(PACKAGE_NAME).joinpath(DATA_DIR, PARTS_CATALOG_FILE)


def workloads_config_resource():
    return files(PACKAGE_NAME).joinpath(DATA_DIR, WORKLOADS_CONFIG_FILE)

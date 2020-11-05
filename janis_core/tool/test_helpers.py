from typing import Dict, Union, List, Set
from tabulate import tabulate
from pkg_resources import parse_version

import janis_core as jc
from janis_core.translations.cwl import CwlTranslator
from janis_core.translations.wdl import WdlTranslator


janis_assistant_version_required_min = "0.10.8"


def verify_janis_assistant_installed():
    """
    Check if the correct version of janis assistant is installed
    """
    min_version_required = janis_assistant_version_required_min

    try:
        import janis_assistant

        if parse_version(janis_assistant.__version__) < parse_version(
            min_version_required
        ):
            raise Exception(
                f"to run this test, janis_asisstant >= {min_version_required}"
                f" must be installed. Installed version is {janis_assistant.__version__}"
            )

    except Exception as e:
        raise e


def get_available_engines():
    """
    Get a list of available engines to run the test suite against
    """
    verify_janis_assistant_installed()
    from janis_assistant.engines.enginetypes import EngineType

    engines = {
        EngineType.cromwell.value: WdlTranslator(),
        EngineType.cwltool.value: CwlTranslator(),
    }

    return engines


def get_all_tools(modules: List):
    """
    Get all available tools in the list of modules
    """
    shed = jc.JanisShed
    shed.hydrate(force=True, modules=modules)

    return shed.get_all_tools()


def get_one_tool(tool_id: str, modules: List, version: str = None):
    """
    Get one tool given id and the modules where to search it from
    """
    shed = jc.JanisShed
    shed.hydrate(force=True, modules=modules)

    return shed.get_tool(tool=tool_id, version=version)


def print_test_report(
    failed: Dict[str, str], succeeded: Set, first_column_header: str = "Tool"
):
    """
    Print test report in tabular text format
    """
    headers = [first_column_header, "Status", "Description"]
    formatted_failed = [(tid, "FAILED", terror) for tid, terror in failed.items()]
    formatted_passed = [(tid, "PASSED", "") for tid in succeeded]
    print(tabulate([*formatted_failed, *formatted_passed], headers=headers))

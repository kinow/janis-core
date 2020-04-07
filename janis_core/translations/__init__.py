from typing import Dict

from janis_core.utils import lowercase_dictkeys

from janis_core.__meta__ import GITHUB_URL
from janis_core.translationdeps.exportpath import ExportPathKeywords
from janis_core.translationdeps.supportedtranslations import (
    SupportedTranslations,
    SupportedTranslation,
)
from janis_core.translations.wdl import WdlTranslator
from .cwl import CwlTranslator
from .translationbase import TranslatorBase


def get_translator(translation: SupportedTranslation) -> TranslatorBase:
    if translation == SupportedTranslations.CWL:
        return CwlTranslator()
    elif translation == SupportedTranslations.WDL:
        return WdlTranslator()

    raise NotImplementedError(
        f"The requested translation ('{translation}') has not been implemented yet, "
        f"why not contribute one at '{GITHUB_URL}'."
    )


def translate_workflow(
    workflow,
    translation: SupportedTranslation,
    to_console=True,
    tool_to_console=False,
    with_docker=True,
    with_resource_overrides=False,
    to_disk=False,
    write_inputs_file=True,
    export_path=ExportPathKeywords.default,
    should_validate=False,
    should_zip=True,
    merge_resources=False,
    hints=None,
    allow_null_if_not_optional=True,
    additional_inputs: Dict = None,
    max_cores=None,
    max_mem=None,
    allow_empty_container=False,
    container_override: dict = None,
):
    translator = get_translator(translation)
    return translator.translate(
        workflow,
        to_console=to_console,
        tool_to_console=tool_to_console,
        with_docker=with_docker,
        with_resource_overrides=with_resource_overrides,
        to_disk=to_disk,
        export_path=export_path,
        write_inputs_file=write_inputs_file,
        should_validate=should_validate,
        should_zip=should_zip,
        merge_resources=merge_resources,
        hints=hints,
        allow_null_if_not_optional=allow_null_if_not_optional,
        additional_inputs=additional_inputs,
        max_cores=max_cores,
        max_mem=max_mem,
        allow_empty_container=allow_empty_container,
        container_override=lowercase_dictkeys(container_override),
    )


def translate_code_tool(
    tool,
    translation: SupportedTranslation,
    to_console=True,
    to_disk=False,
    export_path=None,
    with_docker=True,
    allow_empty_container=False,
    container_override: dict = None,
):
    translator = get_translator(translation)
    return translator.translate_code_tool(
        tool,
        to_console=to_console,
        to_disk=to_disk,
        export_path=export_path,
        with_docker=with_docker,
        allow_empty_container=allow_empty_container,
        container_override=lowercase_dictkeys(container_override),
    )


def translate_tool(
    tool,
    translation: SupportedTranslation,
    to_console=True,
    to_disk=False,
    export_path=None,
    with_docker=True,
    with_resource_overrides=False,
    max_cores=None,
    max_mem=None,
    allow_empty_container=False,
    container_override: dict = None,
) -> str:
    translator = get_translator(translation)
    return translator.translate_tool(
        tool,
        to_console=to_console,
        to_disk=to_disk,
        export_path=export_path,
        with_docker=with_docker,
        with_resource_overrides=with_resource_overrides,
        max_cores=max_cores,
        max_mem=max_mem,
        allow_empty_container=allow_empty_container,
        container_override=lowercase_dictkeys(container_override),
    )


def build_resources_input(
    workflow, translation: SupportedTranslation, hints, max_cores=None, max_mem=None
) -> str:
    translator = get_translator(translation)
    return translator.stringify_translated_inputs(
        translator.build_resources_input(
            workflow, hints, max_cores=max_cores, max_mem=max_mem
        )
    )

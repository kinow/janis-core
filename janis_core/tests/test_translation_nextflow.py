import unittest
from typing import List, Dict, Any, Optional

from janis_core.operators.logical import If, IsDefined
from janis_core.operators.standard import ReadContents

from janis_core.tests.testtools import (
    SingleTestTool,
    ArrayTestTool,
    TestTool,
    TestToolV2,
    TestInputQualityTool,
    TestTypeWithSecondary,
    TestWorkflowWithStepInputExpression,
    EchoTestTool,
    FilenameGeneratedTool,
    OperatorResourcesTestTool,
    TestWorkflowWithConditionStep,
    TestWorkflowThatOutputsArraysOfSecondaryFiles,
    TestWorkflowWithAliasSelectorWorkflow,
)


from janis_core.translations.nextflow import NextflowTranslator
from janis_core import (
    WorkflowBuilder,
    ToolInput,
    String,
    InputSelector,
    Array,
    WildcardSelector,
    StringFormatter,
    CommandToolBuilder,
    ToolOutput,
    DataType,
    Float,
    JoinOperator,
)
from janis_core.tool.documentation import InputDocumentation
from janis_core.translations import NextflowTranslator as translator
from janis_core.types import CpuSelector, MemorySelector, Stdout
from janis_core.workflow.workflow import InputNode

from janis_core.operators.standard import FirstOperator
from janis_core import Array, String, Stdout, File, Int, Float, Boolean


class DataTypeWithSecondary(File):
    @staticmethod
    def name() -> str:
        return "test_secondary"

    @staticmethod
    def secondary_files():
        return [".txt"]


class TestNextflowWfToolInputs(unittest.TestCase):
    def test_first_selector(self):

        workflow = TestWorkflowWithConditionStep()
        step_keys = list(workflow.step_nodes.keys())

        step_id = "print"
        tool = workflow.step_nodes[step_id].tool
        inputs = translator.generate_wf_tool_inputs(tool, step_keys)
        expected = {"inp": "[$params.mystring, $get_string.out.out].first()"}

        self.assertEqual(expected, inputs)

    def test_simple(self):
        w1 = TestWorkflowThatOutputsArraysOfSecondaryFiles()
        w1_step_keys = list(w1.step_nodes.keys())

        expected = {"testtool": "$params.inp"}
        self.assertEqual(
            expected,
            translator.generate_wf_tool_inputs(w1.step_nodes["stp"].tool, w1_step_keys),
        )

    def test_with_expression(self):
        w2 = TestWorkflowWithStepInputExpression()
        w2_step_keys = list(w2.step_nodes.keys())

        expected = {
            "inp": "$params.mystring ? $params.mystring : $params.mystring_backup"
        }
        self.assertEqual(
            expected,
            translator.generate_wf_tool_inputs(
                w2.step_nodes["print"].tool, w2_step_keys
            ),
        )

    def test_multi_steps(self):
        w3 = TestWorkflowWithAliasSelectorWorkflow()
        w3_step_keys = list(w3.step_nodes.keys())

        expected1 = {"testtool": "$params.inp"}
        self.assertEqual(
            expected1,
            translator.generate_wf_tool_inputs(
                w3.step_nodes["stp1"].tool, w3_step_keys
            ),
        )

        expected2 = {"inp": "$stp1.out.out"}
        self.assertEqual(
            expected2,
            translator.generate_wf_tool_inputs(
                w3.step_nodes["stp2"].tool, w3_step_keys
            ),
        )


class TestNextflowPrepareInputVars(unittest.TestCase):
    def test_secondary_files(self):
        inp = ToolInput("bam", DataTypeWithSecondary(), prefix="-I")

        res = translator.generate_input_var_definition(inp, "bam")
        expected = "apply_prefix(bam[0], '-I ', 'False')"
        self.assertEqual(res, expected)

    def test_array_with_secondary_files(self):

        inp = ToolInput("bams", Array(DataTypeWithSecondary()), prefix="-I")

        res = translator.generate_input_var_definition(inp, "bams")
        expected = "apply_prefix(get_primary_files(bams).join(' '), '-I ', 'False')"

        self.assertEqual(res, expected)


class TestGenerateWfToolOutputs(unittest.TestCase):
    w1 = TestWorkflowThatOutputsArraysOfSecondaryFiles()
    w2 = TestWorkflowWithStepInputExpression()
    w3 = TestWorkflowWithAliasSelectorWorkflow()

    def test_without_prefix(self):
        assert translator.generate_wf_tool_outputs(self.w1) == {"out": "stp.out.out"}
        assert translator.generate_wf_tool_outputs(self.w2) == {"out": "print.out.out"}
        assert translator.generate_wf_tool_outputs(self.w3) == {"out": "stp1.out.out"}

    def test_with_prefix(self):
        expected1 = {"out": "subworkflow_stp.out.out"}
        self.assertEqual(
            expected1, translator.generate_wf_tool_outputs(self.w1, "subworkflow_")
        )

        expected2 = {"out": "subworkflowprint.out.out"}
        self.assertEqual(
            expected2, translator.generate_wf_tool_outputs(self.w2, "subworkflow")
        )


class TestTranslateStringFormatter(unittest.TestCase):
    any_tool = TestTool()

    def test_string_formatter(self):
        b = StringFormatter("no format")
        res = translator.translate_string_formatter(b, self.any_tool)
        self.assertEqual("no format", res)

    def test_string_formatter_one_string_param(self):
        b = StringFormatter("there's {one} arg", one="a string")
        res = translator.translate_string_formatter(b, self.any_tool)
        self.assertEqual("there's ${'a string'} arg", res)

    def test_string_formatter_one_input_selector_param(self):
        b = StringFormatter("an input {arg}", arg=InputSelector("testtool"))
        res = translator.translate_string_formatter(
            b, self.any_tool, inputs_dict=self.any_tool.inputs_map()
        )
        self.assertEqual("an input ${testtool}", res)

    def test_string_formatter_two_param(self):
        tool = TestInputQualityTool()
        b = StringFormatter(
            "{username}:{password}",
            username=InputSelector("user"),
            password=InputSelector("static"),
        )
        res = translator.translate_string_formatter(
            b, tool, inputs_dict=tool.inputs_map()
        )
        self.assertEqual(
            "${user}:${static}",
            res,
        )

    def test_escaped_characters(self):
        tool = TestInputQualityTool()
        b = StringFormatter(
            "{username}\\t{password}",
            username=InputSelector("user"),
            password=InputSelector("static"),
        )
        res = translator.translate_string_formatter(
            b, tool, inputs_dict=tool.inputs_map()
        )
        self.assertEqual("${user}\\t${static}", res)

        res2 = translator.translate_string_formatter(
            b, tool, inputs_dict=tool.inputs_map(), in_shell_script=True
        )
        self.assertEqual("${user}\\\\t${static}", res2)

    def test_expression_arg(self):
        tool = TestTool()
        b = StringFormatter(
            "{name}:{items}",
            name=InputSelector("testtool"),
            items=JoinOperator(InputSelector("arrayInp"), separator=";"),
        )

        res = translator.translate_string_formatter(
            b, tool, inputs_dict=tool.inputs_map()
        )
        self.assertEqual("${testtool}:${arrayInp.join(';')}", res)


# class TestNextflowIntegration(unittest.TestCase):
#     def test_echo(self):
#         nf = NextflowTranslator.translate_tool_internal(EchoTestTool())
#         print(nf.get_string())
#
#
# class TestCwlTypesConversion(unittest.TestCase):
#     pass
#
#
# class TestCwlMisc(unittest.TestCase):
#     def test_str_tool(self):
#         t = TestTool()
#         actual = t.translate("cwl", to_console=False)
#         self.assertEqual(cwl_testtool, actual)
#
#
# class TestCwlTranslatorOverrides(unittest.TestCase):
#     def setUp(self):
#         self.translator = CwlTranslator()
#
#     def test_stringify_WorkflowBuilder(self):
#         cwlobj = cwlgen.Workflow(
#             id="wid", cwlVersion="v1.0", inputs={}, outputs={}, steps={}
#         )
#         expected = """\
# #!/usr/bin/env cwl-runner
# class: Workflow
# cwlVersion: v1.0
#
# inputs: {}
#
# outputs: {}
#
# steps: {}
# id: wid
# """
#         self.assertEqual(
#             expected, self.translator.stringify_translated_workflow(cwlobj)
#         )
#
#     def test_stringify_tool(self):
#         cwlobj = cwlgen.CommandLineTool(
#             id="tid", inputs={}, outputs={}, cwlVersion="v1.0"
#         )
#         expected = """\
# #!/usr/bin/env cwl-runner
# class: CommandLineTool
# cwlVersion: v1.0
#
# inputs: {}
#
# outputs: {}
# id: tid
# """
#
#         self.assertEqual(expected, self.translator.stringify_translated_tool(cwlobj))
#
#     def test_stringify_inputs(self):
#         d = {"inp1": 1}
#         self.assertEqual("inp1: 1\n", self.translator.stringify_translated_inputs(d))
#
#     def test_workflow_filename(self):
#         w = WorkflowBuilder("wid")
#         self.assertEqual("wid.cwl", self.translator.workflow_filename(w))
#
#     def test_tools_filename(self):
#         self.assertEqual(
#             "TestTranslationtool.cwl", self.translator.tool_filename(TestTool())
#         )
#
#     def test_inputs_filename(self):
#         w = WorkflowBuilder("wid")
#         self.assertEqual("wid-inp.yml", self.translator.inputs_filename(w))
#
#     def test_resources_filename(self):
#         w = WorkflowBuilder("wid")
#         self.assertEqual("wid-resources.yml", self.translator.resources_filename(w))
#
#
# class TestCwlArraySeparators(unittest.TestCase):
#     # Based on https://www.commonwl.org/user_guide/09-array-inputs/index.html
#
#     def test_regular_input_bindingin(self):
#         t = ToolInput("filesA", Array(String()), prefix="-A", position=1)
#         cwltoolinput = cwl.translate_tool_input(t, None, None).save()
#         self.assertDictEqual(
#             {
#                 "id": "filesA",
#                 "label": "filesA",
#                 "type": {"items": "string", "type": "array"},
#                 "inputBinding": {"prefix": "-A", "position": 1},
#             },
#             cwltoolinput,
#         )
#
#     def test_nested_input_binding(self):
#         t = ToolInput(
#             "filesB",
#             Array(String()),
#             prefix="-B=",
#             separate_value_from_prefix=False,
#             position=2,
#             prefix_applies_to_all_elements=True,
#         )
#         cwltoolinput = cwl.translate_tool_input(t, None, None)
#         self.assertDictEqual(
#             {
#                 "id": "filesB",
#                 "label": "filesB",
#                 "type": {
#                     "items": "string",
#                     "type": "array",
#                     "inputBinding": {"prefix": "-B=", "separate": False},
#                 },
#                 "inputBinding": {"position": 2},
#             },
#             cwltoolinput.save(),
#         )
#
#     def test_separated_input_bindingin(self):
#         t = ToolInput(
#             "filesC",
#             Array(String()),
#             prefix="-C=",
#             separate_value_from_prefix=False,
#             position=4,
#             separator=",",
#         )
#         cwltoolinput = cwl.translate_tool_input(t, None, None)
#         self.assertDictEqual(
#             {
#                 "id": "filesC",
#                 "label": "filesC",
#                 "type": {"items": "string", "type": "array"},
#                 "inputBinding": {
#                     "prefix": "-C=",
#                     "itemSeparator": ",",
#                     "separate": False,
#                     "position": 4,
#                 },
#             },
#             cwltoolinput.save(),
#         )
#
#     def test_optional_array_prefixes(self):
#         t = ToolInput(
#             "filesD",
#             Array(String(), optional=True),
#             prefix="-D",
#             prefix_applies_to_all_elements=True,
#         )
#         cwltoolinput = cwl.translate_tool_input(t, None, None)
#
#         self.assertDictEqual(
#             {
#                 "id": "filesD",
#                 "label": "filesD",
#                 "inputBinding": {},
#                 "type": [
#                     {
#                         "inputBinding": {"prefix": "-D"},
#                         "items": "string",
#                         "type": "array",
#                     },
#                     "null",
#                 ],
#             },
#             dict(cwltoolinput.save()),
#         )
#
#
# class TestCwlSelectorsAndGenerators(unittest.TestCase):
#     def test_input_selector_base(self):
#         input_sel = InputSelector("random")
#         self.assertEqual(
#             "$(inputs.random)",
#             cwl.translate_input_selector(input_sel, code_environment=False),
#         )
#
#     def test_input_selector_base_codeenv(self):
#         input_sel = InputSelector("random")
#         self.assertEqual(
#             "inputs.random",
#             cwl.translate_input_selector(input_sel, code_environment=True),
#         )
#
#     def test_input_value_none_codeenv(self):
#         self.assertEqual(
#             "null", cwl.CwlTranslator.unwrap_expression(None, code_environment=True)
#         )
#
#     def test_input_value_none_nocodeenv(self):
#         self.assertEqual(
#             None, cwl.CwlTranslator.unwrap_expression(None, code_environment=False)
#         )
#
#     def test_input_value_string_codeenv(self):
#         self.assertEqual(
#             '"TestString"',
#             cwl.CwlTranslator.unwrap_expression("TestString", code_environment=True),
#         )
#
#     def test_input_value_string_nocodeenv(self):
#         self.assertEqual(
#             "TestString",
#             cwl.CwlTranslator.unwrap_expression("TestString", code_environment=False),
#         )
#
#     def test_input_value_int_codeenv(self):
#         self.assertEqual(
#             "42", cwl.CwlTranslator.unwrap_expression(42, code_environment=True)
#         )
#
#     def test_input_value_int_nocodeenv(self):
#         self.assertEqual(
#             "42", cwl.CwlTranslator.unwrap_expression(42, code_environment=False)
#         )
#
#     # def test_input_value_filename_codeenv(self):
#     #     import uuid
#     #     fn = Filename(guid=str(uuid.uuid4()))
#     #     self.assertEqual(
#     #         '"generated-" + Math.random().toString(16).substring(2, 8) + ""',
#     #         cwl.get_input_value_from_potential_selector_or_generator(fn, code_environment=True)
#     #     )
#     #
#     # def test_input_value_filename_nocodeenv(self):
#     #     import uuid
#     #     fn = Filename(guid=str(uuid.uuid4()))
#     #     self.assertEqual(
#     #         '$("generated-" + Math.random().toString(16).substring(2, 8) + "")',
#     #         cwl.get_input_value_from_potential_selector_or_generator(fn, code_environment=False)
#     #     )
#
#     def test_input_value_inpselect_codeenv(self):
#         inp = InputSelector("threads")
#         self.assertEqual(
#             "inputs.threads",
#             cwl.CwlTranslator.unwrap_expression(inp, code_environment=True),
#         )
#
#     def test_input_value_inpselect_nocodeenv(self):
#         inp = InputSelector("threads")
#         self.assertEqual(
#             "$(inputs.threads)",
#             cwl.CwlTranslator.unwrap_expression(inp, code_environment=False),
#         )
#
#     def test_input_value_wildcard(self):
#         self.assertRaises(
#             Exception, cwl.CwlTranslator.unwrap_expression, value=WildcardSelector("*")
#         )
#
#     # def test_input_value_cpuselect_codeenv(self):
#     #     inp = CpuSelector()
#     #     self.assertEqual(
#     #         "inputs.runtime_cpu",
#     #         cwl.CwlTranslator.unwrap_expression(inp, code_environment=True),
#     #     )
#     #
#     # def test_input_value_cpuselect_nocodeenv(self):
#     #     inp = CpuSelector()
#     #     self.assertEqual(
#     #         "$(inputs.runtime_cpu)",
#     #         cwl.CwlTranslator.unwrap_expression(inp, code_environment=False),
#     #     )
#
#     # def test_input_value_memselect_codeenv(self):
#     #     inp = MemorySelector()
#     #     self.assertEqual(
#     #         "inputs.runtime_memory",
#     #         cwl.CwlTranslator.unwrap_expression(inp, code_environment=True),
#     #     )
#     #
#     # def test_input_value_memselect_nocodeenv(self):
#     #     inp = MemorySelector()
#     #     self.assertEqual(
#     #         "$(inputs.runtime_memory)",
#     #         cwl.CwlTranslator.unwrap_expression(inp, code_environment=False),
#     #     )
#
#     def test_input_value_cwl_callable(self):
#         class NonCallableCwl:
#             def cwl(self):
#                 return "unbelievable"
#
#         self.assertEqual(
#             "unbelievable", cwl.CwlTranslator.unwrap_expression(NonCallableCwl())
#         )
#
#     def test_input_value_cwl_noncallable(self):
#         class NonCallableCwl:
#             def __init__(self):
#                 self.cwl = None
#
#         self.assertRaises(
#             Exception,
#             cwl.CwlTranslator.unwrap_expression,
#             value=NonCallableCwl(),
#             tool_id=None,
#         )
#
#     def test_string_formatter(self):
#         b = StringFormatter("no format")
#         res = cwl.CwlTranslator.unwrap_expression(b)
#         self.assertEqual("no format", res)
#
#     def test_string_formatter_one_string_param(self):
#         b = StringFormatter("there's {one} arg", one="a string")
#         res = cwl.CwlTranslator.unwrap_expression(b, code_environment=False)
#         self.assertEqual('$("there\'s {one} arg".replace(/\{one\}/g, "a string"))', res)
#
#     def test_string_formatter_one_input_selector_param(self):
#         b = StringFormatter("an input {arg}", arg=InputSelector("random_input"))
#         res = cwl.CwlTranslator.unwrap_expression(b, code_environment=False)
#         self.assertEqual(
#             '$("an input {arg}".replace(/\{arg\}/g, inputs.random_input))', res
#         )
#
#     def test_string_formatter_two_param(self):
#         # vardict input format
#         b = StringFormatter(
#             "{tumorName}:{normalName}",
#             tumorName=InputSelector("tumorInputName"),
#             normalName=InputSelector("normalInputName"),
#         )
#         res = cwl.CwlTranslator.unwrap_expression(b, code_environment=False)
#         self.assertEqual(
#             '$("{tumorName}:{normalName}".replace(/\{tumorName\}/g, inputs.tumorInputName).replace(/\{normalName\}/g, inputs.normalInputName))',
#             res,
#         )
#
#     def test_escaped_characters(self):
#         trans = cwl.CwlTranslator
#         translated = trans.translate_tool_internal(TestTool())
#         arg: cwlgen.CommandLineBinding = translated.arguments[0]
#         self.assertEqual('test:\\\\t:escaped:\\\\n:characters"', arg.valueFrom)
#
#
# class TestCwlEnvVar(unittest.TestCase):
#     def test_environment1(self):
#         t = CwlTranslator().translate_tool_internal(tool=TestTool())
#         envvar: cwlgen.EnvVarRequirement = [
#             t for t in t.requirements if t.class_ == "EnvVarRequirement"
#         ][0]
#         envdef: cwlgen.EnvironmentDef = envvar.envDef[0]
#         self.assertEqual("test1", envdef.envName)
#         self.assertEqual("$(inputs.testtool)", envdef.envValue)
#
#
# class TestCwlTranslateInput(unittest.TestCase):
#     def test_translate_input(self):
#         inp = InputNode(
#             None,
#             identifier="testIdentifier",
#             datatype=String(),
#             default="defaultValue",
#             doc=InputDocumentation("docstring"),
#             value=None,
#         )
#         tinp = cwl.translate_workflow_input(inp, None)
#
#         self.assertEqual("testIdentifier", tinp.id)
#         self.assertIsNone(tinp.label)
#         self.assertIsNone(tinp.secondaryFiles)
#         self.assertEqual("docstring", tinp.doc)
#         self.assertIsNone(None, tinp.inputBinding)
#         self.assertEqual("string", tinp.type)
#         self.assertEqual("defaultValue", tinp.default)
#
#     def test_secondary_file_translation(self):
#         inp = InputNode(
#             None,
#             identifier="testIdentifier",
#             datatype=TestTypeWithSecondary(),
#             default=None,
#             value=None,
#         )
#         tinp = cwl.translate_workflow_input(inp, None)
#
#         self.assertEqual("File", tinp.type)
#         self.assertListEqual(["^.txt"], tinp.secondaryFiles)
#
#     def test_array_secondary_file_translation(self):
#         inp = InputNode(
#             None,
#             identifier="testIdentifier",
#             datatype=Array(TestTypeWithSecondary()),
#             default=None,
#             value=None,
#         )
#         tinp = cwl.translate_workflow_input(inp, None)
#         self.assertIsInstance(tinp.type, cwlgen.CommandInputArraySchema)
#         self.assertEqual("File", tinp.type.items)
#         self.assertListEqual(["^.txt"], tinp.secondaryFiles)
#
#
# class TestCwlOutputGeneration(unittest.TestCase):
#     def test_stdout_no_outputbinding(self):
#         out = cwl.translate_tool_output(ToolOutput("out", Stdout), {}, tool=None).save()
#         self.assertDictEqual({"id": "out", "label": "out", "type": "stdout"}, out)
#
#
# class TestCwlGenerateInput(unittest.TestCase):
#     def setUp(self):
#         self.translator = cwl.CwlTranslator()
#
#     def test_input_in_input_value_nooptional_nodefault(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_value_nooptional_nodefault")
#         wf.input("inpId", String(), default="1")
#         self.assertDictEqual({"inpId": "1"}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_value_nooptional_default(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_value_nooptional_default")
#         wf.input("inpId", String(), default="1")
#         self.assertDictEqual({"inpId": "1"}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_value_optional_nodefault(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_value_optional_nodefault")
#         wf.input("inpId", String(optional=True), default="1")
#         self.assertDictEqual({"inpId": "1"}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_value_optional_default(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_value_optional_default")
#         wf.input("inpId", String(optional=True), default="1")
#         self.assertDictEqual({"inpId": "1"}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_novalue_nooptional_nodefault(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_novalue_nooptional_nodefault")
#         wf.input("inpId", String())
#         # included because no value, no default, and not optional
#         self.assertDictEqual({"inpId": None}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_novalue_nooptional_default(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_novalue_nooptional_default")
#         wf.input("inpId", String(), default="2")
#         self.assertDictEqual({"inpId": "2"}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_novalue_optional_nodefault(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_novalue_optional_nodefault")
#         wf.input("inpId", String(optional=True))
#         # self.assertDictEqual({'inpId': None}, self.translator.build_inputs_file(wf))
#         self.assertDictEqual({}, self.translator.build_inputs_file(wf))
#
#     def test_input_in_input_novalue_optional_default(self):
#         wf = WorkflowBuilder("test_cwl_input_in_input_novalue_optional_default")
#         wf.input("inpId", String(optional=True), default="2")
#         self.assertDictEqual({"inpId": "2"}, self.translator.build_inputs_file(wf))
#
#
# class TestCwlMaxResources(unittest.TestCase):
#     def test_cores(self):
#         tool = TestTool()
#         resources = CwlTranslator.build_resources_input(tool.wrapped_in_wf(), {})
#         self.assertEqual(2, resources["testtranslationtool_runtime_cpu"])
#
#     def test_max_cores(self):
#         tool = TestTool()
#         resources = CwlTranslator.build_resources_input(
#             tool.wrapped_in_wf(), {}, max_cores=1
#         )
#         self.assertEqual(1, resources["testtranslationtool_runtime_cpu"])
#
#     def test_memory(self):
#         tool = TestTool()
#         resources = CwlTranslator.build_resources_input(tool.wrapped_in_wf(), {})
#         self.assertEqual(2, resources["testtranslationtool_runtime_memory"])
#
#     def test_max_memory(self):
#         tool = TestTool()
#         resources = CwlTranslator.build_resources_input(
#             tool.wrapped_in_wf(), {}, max_mem=1
#         )
#         self.assertEqual(1, resources["testtranslationtool_runtime_memory"])
#
#
# class TestEmptyContainer(unittest.TestCase):
#     def test_empty_container_raises(self):
#
#         self.assertRaises(
#             Exception, CwlTranslator().translate_tool_internal, SingleTestTool()
#         )
#
#     def test_empty_container(self):
#         c = CwlTranslator().translate_tool_internal(
#             SingleTestTool(), allow_empty_container=True
#         )
#         self.assertNotIn("DockerRequirement", c.requirements)
#
#
# class TestCwlSingleToMultipleInput(unittest.TestCase):
#     def test_add_single_to_array_edge(self):
#         w = WorkflowBuilder("test_add_single_to_array_edge")
#         w.input("inp1", str)
#         w.step("stp1", ArrayTestTool(inputs=w.inp1))
#
#         c, _, _ = CwlTranslator().translate(
#             w, to_console=False, allow_empty_container=True
#         )
#         self.assertEqual(cwl_multiinput, c)
#
#
# class TestPackedWorkflow(unittest.TestCase):
#     def test_simple(self):
#         w = WorkflowBuilder("test_add_single_to_array_edge")
#         w.step("ech", SingleTestTool(inputs="Hello"), doc="Print 'Hello'")
#         c = CwlTranslator.translate_workflow_to_all_in_one(
#             w, allow_empty_container=True
#         )
#         print(CwlTranslator.stringify_translated_workflow(c))
#
#
# class TestContainerOverride(unittest.TestCase):
#     def test_tool_dict_override(self):
#         import ruamel.yaml
#
#         expected_container = "container/override"
#
#         tool = SingleTestTool()
#         d = ruamel.yaml.load(
#             tool.translate(
#                 "cwl",
#                 to_console=False,
#                 container_override={tool.id(): expected_container},
#             ),
#             Loader=ruamel.yaml.Loader,
#         )
#
#         received_container = [
#             req.get("dockerPull")
#             for req in d.get("requirements")
#             if req["class"] == "DockerRequirement"
#         ][0]
#
#         self.assertEqual(expected_container, received_container)
#
#     def test_tool_string_override(self):
#         import ruamel.yaml
#
#         expected_container = "container/override"
#
#         tool = SingleTestTool()
#         d = ruamel.yaml.load(
#             tool.translate(
#                 "cwl", to_console=False, container_override=expected_container
#             ),
#             Loader=ruamel.yaml.Loader,
#         )
#         received_container = [
#             req.get("dockerPull")
#             for req in d.get("requirements")
#             if req["class"] == "DockerRequirement"
#         ][0]
#
#         self.assertEqual(expected_container, received_container)
#
#
# class TestCWLCompleteOperators(unittest.TestCase):
#     def test_step_input(self):
#
#         ret, _, _ = TestWorkflowWithStepInputExpression().translate(
#             "cwl", to_console=False
#         )
#         self.assertEqual(cwl_stepinput, ret)
#
#     def test_array_step_input(self):
#         wf = WorkflowBuilder("cwl_test_array_step_input")
#         wf.input("inp1", Optional[str])
#         wf.input("inp2", Optional[str])
#
#         wf.step(
#             "print",
#             ArrayTestTool(
#                 inputs=[
#                     If(IsDefined(wf.inp1), wf.inp1, "default1"),
#                     If(IsDefined(wf.inp2), wf.inp2 + "_suffix", ""),
#                 ]
#             ),
#         ),
#
#         wf.output("out", source=wf.print)
#
#         ret, _, _ = wf.translate("cwl", allow_empty_container=True, to_console=False)
#         self.assertEqual(cwl_arraystepinput, ret)
#
#
# class WorkflowCwlInputDefaultOperator(unittest.TestCase):
#     def test_string_formatter(self):
#         wf = WorkflowBuilder("wf")
#         wf.input("sampleName", str)
#         wf.input("platform", str)
#
#         wf.input(
#             "readGroupHeaderLine",
#             String(optional=True),
#             default=StringFormatter(
#                 "@RG\\tID:{name}\\tSM:{name}\\tLB:{name}\\tPL:{pl}",
#                 name=InputSelector("sampleName"),
#                 pl=InputSelector("platform"),
#             ),
#         )
#         wf.step("print", EchoTestTool(inp=wf.readGroupHeaderLine))
#         wf.output("out", source=wf.print)
#         d, _ = cwl.CwlTranslator.translate_workflow(
#             wf, with_container=False, allow_empty_container=True
#         )
#         stepinputs = d.save()["steps"][0]["in"]
#         self.assertEqual(4, len(stepinputs))
#         expression = stepinputs[-1]["valueFrom"]
#         expected = (
#             "$((inputs._print_inp_readGroupHeaderLine != null) "
#             "? inputs._print_inp_readGroupHeaderLine "
#             ': "@RG\\\\tID:{name}\\\\tSM:{name}\\\\tLB:{name}\\\\tPL:{pl}".replace(/\\{name\\}/g, inputs._print_inp_sampleName).replace(/\\{pl\\}/g, inputs._print_inp_platform))'
#         )
#         self.assertEqual(expected, expression)
#
#     def test_string_formatter_stepinput(self):
#         wf = WorkflowBuilder("wf")
#         wf.input("sampleName", str)
#         wf.input("platform", str)
#
#         wf.step(
#             "print",
#             EchoTestTool(
#                 inp=StringFormatter(
#                     "@RG\\tID:{name}\\tSM:{name}\\tLB:{name}\\tPL:{pl}",
#                     name=wf.sampleName,
#                     pl=wf.platform,
#                 )
#             ),
#         )
#         wf.output("out", source=wf.print)
#         d, _ = cwl.CwlTranslator.translate_workflow(
#             wf, with_container=False, allow_empty_container=True
#         )
#         stepinputs = d.save()["steps"][0]["in"]
#         self.assertEqual(3, len(stepinputs))
#         expression = stepinputs[-1]["valueFrom"]
#         expected = '$("@RG\\\\tID:{name}\\\\tSM:{name}\\\\tLB:{name}\\\\tPL:{pl}".replace(/\\{name\\}/g, inputs._print_inp_sampleName).replace(/\\{pl\\}/g, inputs._print_inp_platform))'
#         self.assertEqual(expected, expression)
#
#
# class TestCWLFilenameGeneration(unittest.TestCase):
#     def test_1(self):
#         tool = FilenameGeneratedTool()
#         inputsdict = {t.id(): t for t in tool.inputs()}
#         mapped = [cwl.translate_tool_input(i, inputsdict, tool) for i in tool.inputs()]
#         expressions = [
#             mapped[i].save()["inputBinding"]["valueFrom"] for i in range(4, len(mapped))
#         ]
#         self.assertEqual("$(inputs.inp)", expressions[0])
#         self.assertEqual(
#             '$(inputs.inpOptional ? inputs.inpOptional : "generated")', expressions[1]
#         )
#         self.assertEqual(
#             '$(inputs.fileInp.basename.replace(/.txt$/, "")).transformed.fnp',
#             expressions[2],
#         )
#         self.assertEqual(
#             '$(inputs.fileInpOptional ? inputs.fileInpOptional.basename.replace(/.txt$/, "") : "generated").optional.txt',
#             expressions[3],
#         )
#
#
# class TestCWLRunRefs(unittest.TestCase):
#     def test_two_similar_tools(self):
#         w = WorkflowBuilder("testTwoToolsWithSameId")
#
#         w.input("inp", str)
#         w.step("stp1", TestTool(testtool=w.inp))
#         w.step("stp2", TestToolV2(testtool=w.inp))
#
#         wf_cwl, _ = CwlTranslator.translate_workflow(w)
#         stps = {stp.id: stp for stp in wf_cwl.steps}
#
#         self.assertEqual("tools/TestTranslationtool.cwl", stps["stp1"].run)
#         self.assertEqual("tools/TestTranslationtool_v0_0_2.cwl", stps["stp2"].run)
#
#
# class TestCwlResourceOperators(unittest.TestCase):
#     def test_1(self):
#         tool_cwl = CwlTranslator.translate_tool_internal(
#             OperatorResourcesTestTool(), with_resource_overrides=True
#         )
#         resourcereq = [
#             r for r in tool_cwl.requirements if r.class_ == "ResourceRequirement"
#         ][0]
#         self.assertEqual(
#             "$([inputs.runtime_cpu, (2 * inputs.outputFiles), 1].filter(function (inner) { return inner != null })[0])",
#             resourcereq.coresMin,
#         )
#         self.assertEqual(
#             "$(Math.round((953.674 * [inputs.runtime_memory, ((inputs.inputFile.size / 1048576) > 1024) ? 4 : 2, 4].filter(function (inner) { return inner != null })[0])))",
#             resourcereq.ramMin,
#         )
#
#
# class TestReadContentsOperator(unittest.TestCase):
#     def test_read_contents_string(self):
#
#         t = CommandToolBuilder(
#             tool="test_readcontents",
#             base_command=["echo", "1"],
#             inputs=[],
#             outputs=[ToolOutput("out", String, glob=ReadContents(Stdout()))],
#             container=None,
#             version="-1",
#         )
#
#         translated = CwlTranslator.translate_tool_internal(
#             t, allow_empty_container=True
#         )
#         self.assertTrue(translated.outputs[0].outputBinding.loadContents)
#
#     def test_read_contents_as_int(self):
#
#         t = CommandToolBuilder(
#             tool="test_readcontents",
#             base_command=["echo", "1"],
#             inputs=[],
#             outputs=[ToolOutput("out", Float, glob=ReadContents(Stdout()).as_float())],
#             container=None,
#             version="-1",
#         )
#         translated = CwlTranslator.translate_tool_internal(
#             t, allow_empty_container=True
#         )
#         self.assertTrue(translated.outputs[0].outputBinding.loadContents)
#         self.assertEqual("float", translated.outputs[0].type)
#
#
# class TestCWLNotNullOperator(unittest.TestCase):
#     def test_workflow_string_not_null(self):
#         w = WorkflowBuilder("wf")
#         w.input("inp", Optional[str])
#         w.output("out", source=w.inp.assert_not_null())
#
#         cwltool = w.translate("cwl", allow_empty_container=True, to_console=False)[0]
#         print(cwltool)
#
#     def test_commandtool_string(self):
#
#         t = CommandToolBuilder(
#             tool="id",
#             base_command=None,
#             inputs=[ToolInput("inp", Optional[str])],
#             outputs=[
#                 ToolOutput("out", str, glob=InputSelector("inp").assert_not_null())
#             ],
#             version=None,
#             container=None,
#         )
#
#         cwltool = t.translate("cwl", allow_empty_container=True, to_console=False)
#         print(cwltool)
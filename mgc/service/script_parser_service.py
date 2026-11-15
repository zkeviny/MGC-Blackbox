"""
脚本静态解析服务模块

功能：
- 从 Python 脚本中静态提取 argparse 参数定义
- 组装成结构化 argv list（Python list of str）
- JSON 序列化后存储到 ext02 字段
- 运行时由 script_executor_service 通过 json.loads 直接传给 subprocess

依赖：
- ast（Python 标准库）
- json

设计原则：
- 仅做 args 提取，不做语法校验
- 不做引号包裹、路径归一化、ISO T 转换（list 透传无破坏）
- 输出 list of str，序列化由调用方负责
- 支持完整支持 / 降级 / 不支持 三态分类（详见开发计划 §5.3）

数据契约：
- ext02 字段 = JSON 序列化的 argv list（字符串格式）
- 例：'["--start", "2026-08-08 00:00:00", "--verbose"]'
"""

import ast
import json
from typing import List, Optional, Tuple, Any


class ScriptParseResult:
    """解析结果封装"""

    def __init__(
        self,
        argv_list: Optional[List[str]],
        is_degraded: bool = False,
        degrade_reason: str = "",
        has_dynamic_args: bool = False,
        recognized_arg_names: Optional[List[str]] = None,
        unrecognized_arg_names: Optional[List[str]] = None,
    ):
        """
        入参：
            - argv_list: 解析出的 argv 列表（None 表示解析失败）
            - is_degraded: 是否为降级结果（识别到 add_argument 但部分参数无法解析）
            - degrade_reason: 降级原因
            - has_dynamic_args: 是否检测到动态默认值（ast.Name/Call/Attribute 等非字面量）
            - recognized_arg_names: 已成功解析的 --flag 列表（如 ['--query_start', '--days_before']）
            - unrecognized_arg_names: 未识别的 --flag 列表（动态默认值、跳过、degraded 的）
        """
        self.argv_list = argv_list
        self.is_degraded = is_degraded
        self.degrade_reason = degrade_reason
        self.has_dynamic_args = has_dynamic_args
        self.recognized_arg_names: List[str] = recognized_arg_names or []
        self.unrecognized_arg_names: List[str] = unrecognized_arg_names or []


class ScriptParserService:
    """脚本静态解析服务"""

    # 完整支持的写法（详见开发计划 §5.3 A）
    # 支持 action='store_true/false/append/store_const/count'
    # 支持 type=str/int/float/bool + default literal
    # 支持 nargs='+'/'*'/'?'/N
    # 支持 choices + default literal
    # 支持 required=True/False（不影响 ext02）
    # 支持 metavar（不影响 ext02）

    # 降级处理（详见开发计划 §5.3 B）
    DEGRADE_ACTIONS = {
        "extend",  # Py3.9+
        "BooleanOptionalAction",  # argparse.BooleanOptionalAction
        "version",  # action='version'
    }
    DEGRADE_TYPES = {
        "FileType",  # argparse.FileType
        "Path",  # pathlib.Path（自定义类）
    }

    @staticmethod
    def _is_dynamic_default(node: ast.AST) -> bool:
        """
        检查 default 表达式是否属于 '动态' 类型（非字面量）。

        动态：ast.Name / ast.Call / ast.Attribute / 其他复杂表达式
        非动态：ast.Constant / ast.List / ast.Tuple / ast.Dict / ast.UnaryOp（一元算子字面量）

        v1.4.10: 用于识别 '脚本动态 args' 场景（如 default=today.strftime(...)），
        触发 dynamic_args_detected 提示。

        ★ phase5+ Win 修复：把 ast.UnaryOp 视为非动态。
          -42 在 Python AST 中是 UnaryOp(USub, Constant(42))，
          之前被误判为动态表达式，导致整个 add_argument 进 unrec。
          现在 _eval_default 已经能正确求值 -42 → -42.0 等，
          这里也同步归类为非动态字面量。
        """
        if isinstance(node, ast.Constant):
            return False
        if isinstance(node, (ast.List, ast.Tuple, ast.Dict)):
            return False
        # ★ 一元算子：-42 / -3.14 / not x / +42
        #   一元 USub/UAdd 都是纯字面量算子（无副作用）→ 视为非动态
        #   仅在 _eval_default 内层递归可以正确求值数字字面量
        if isinstance(node, ast.UnaryOp):
            return False
        if isinstance(node, ast.Name):
            return True
        if isinstance(node, ast.Call):
            return True
        if isinstance(node, ast.Attribute):
            return True
        # 保守：其他复杂表达式视为动态
        return True

    def parse_and_assemble(self, script_body: str) -> ScriptParseResult:
        """
        解析脚本并组装 argv list。

        入参：
            script_body: Python 脚本源码

        出参：
            ScriptParseResult(argv_list, is_degraded, degrade_reason, has_dynamic_args)
            - argv_list 为 None 表示完全无法识别（应返回 warning='args_not_recognized'）
            - argv_list 非 None 表示成功（或降级但仍组装）
            - is_degraded=True 表示部分写法未识别（仍返回 warning='args_not_recognized'）
            - has_dynamic_args=True 表示检测到动态默认值（触发 dynamic_args_detected）
        """
        # 1. AST 解析
        try:
            tree = ast.parse(script_body)
        except SyntaxError:
            return ScriptParseResult(None, has_dynamic_args=False)

        # 2. 收集所有 add_argument 调用
        (
            arg_specs,
            is_degraded,
            degrade_reason,
            has_dynamic_args,
            recognized_names,
            unrecognized_names,
        ) = self._extract_add_argument_calls(tree)
        if not arg_specs:
            return ScriptParseResult(
                None,
                is_degraded=is_degraded,
                degrade_reason=degrade_reason,
                has_dynamic_args=has_dynamic_args,
                recognized_arg_names=recognized_names,
                unrecognized_arg_names=unrecognized_names,
            )

        # 3. 组装 argv list
        argv_list = self._assemble_argv(arg_specs)

        return ScriptParseResult(
            argv_list=argv_list,
            is_degraded=is_degraded,
            degrade_reason=degrade_reason,
            has_dynamic_args=has_dynamic_args,
            recognized_arg_names=recognized_names,
            unrecognized_arg_names=unrecognized_names,
        )

    def _extract_add_argument_calls(
        self, tree: ast.AST
    ) -> Tuple[List[dict], bool, str, bool, List[str], List[str]]:
        """
        从 AST 中提取所有 parser.add_argument(...) 调用。

        返回 (arg_specs, is_degraded, degrade_reason, has_dynamic_args,
              recognized_arg_names, unrecognized_arg_names)
        - recognized_arg_names: 解析成功的 flag（写入 ext02）
        - unrecognized_arg_names: 跳过的 flag（动态默认值、degraded、位置参数）
        """
        arg_specs = []
        is_degraded = False
        degrade_reason = ""
        has_dynamic_args = False  # v1.4.10: 检测到动态默认值
        recognized_names: List[str] = []
        unrecognized_names: List[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "add_argument":
                continue

            spec, degraded, reason, spec_has_dynamic = self._parse_add_argument_call(node)
            # flag 名仅在 spec 解析后才可用；degraded / 跳过场景里另算
            if spec is not None and spec.get("flag"):
                flag = spec["flag"]
            elif not node.args:
                continue
            else:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    flag = first_arg.value
                else:
                    flag = None

            if spec_has_dynamic:
                has_dynamic_args = True
            if spec is None and not degraded:
                # 跳过位置参数或第一个参数不是字符串 flag
                if flag:
                    unrecognized_names.append(flag)
                continue
            if degraded:
                is_degraded = True
                degrade_reason = degrade_reason or reason
                if flag:
                    unrecognized_names.append(flag)
                continue
            if spec is not None:
                arg_specs.append(spec)
                if flag:
                    if spec_has_dynamic:
                        # default 动态 → 不进 ext02，归类为未识别（需手动录入）
                        unrecognized_names.append(flag)
                    else:
                        # default 字面量 → 进 ext02，归类为已识别
                        recognized_names.append(flag)

        return (
            arg_specs,
            is_degraded,
            degrade_reason,
            has_dynamic_args,
            recognized_names,
            unrecognized_names,
        )

    def _parse_add_argument_call(
        self, node: ast.Call
    ) -> Tuple[Optional[dict], bool, str, bool]:
        """
        解析单个 add_argument(...) 调用。

        返回 (spec, is_degraded, degrade_reason, has_dynamic_default)
        spec 为 None 且 is_degraded=False：跳过（如位置参数）
        spec 为 None 且 is_degraded=True：识别到降级写法
        has_dynamic_default: 该 add_argument 的 default 是否是动态表达式
        """
        # 第一个位置参数：flag 名（如 '--start'）或位置参数名（如 'name'）
        if not node.args:
            return None, False, "", False

        first_arg = node.args[0]
        if not isinstance(first_arg, ast.Constant):
            return None, False, "", False
        if not isinstance(first_arg.value, str):
            return None, False, "", False

        flag_name = first_arg.value
        is_positional = not flag_name.startswith("-")

        # 提取关键字参数
        type_str = "str"
        default_value = None
        has_default = False
        is_flag_action = False
        action_name = ""
        nargs_value = None
        choices = None
        has_dynamic_default = False  # v1.4.10: 当前 add_argument 是否含动态 default

        for kw in node.keywords:
            if kw.arg == "type":
                type_str, degraded, reason = self._eval_type(kw.value)
                if degraded:
                    return None, True, reason, False
            elif kw.arg == "default":
                default_value, has_default, degraded, reason = self._eval_default(kw.value)
                # v1.4.10: 检查 default 是否是动态表达式
                if self._is_dynamic_default(kw.value):
                    has_dynamic_default = True
                if degraded:
                    return None, True, reason, has_dynamic_default
            elif kw.arg == "action":
                action_name, degraded, reason = self._eval_action(kw.value)
                if degraded:
                    return None, True, reason, False
                if action_name in ("store_true", "store_false"):
                    is_flag_action = True
            elif kw.arg == "nargs":
                nargs_value, degraded, reason = self._eval_nargs(kw.value)
                if degraded:
                    return None, True, reason, False
            elif kw.arg == "choices":
                choices, degraded, reason = self._eval_choices(kw.value)
                if degraded:
                    return None, True, reason, False
            elif kw.arg in ("required", "metavar", "help", "dest"):
                # 这些参数不影响 ext02，忽略
                pass

        # 位置参数：不写入 ext02
        if is_positional:
            return None, False, "", False

        # ★ phase5+ Win 修复（PM Win 端实测 regression）：
        #   action='append' / action='count' 且 default=None（或未显式给 default）
        #   静态无法推断运行时值。
        #   之前 assemble 输出裸 --flag，紧跟下一个 option 触发 argparse exit 2。
        #   修复：将其归类为"动态"（与 dynamic_args_detected 一致），上层把 flag
        #   放进 unrecognized_names，不写入 ext02 —— 让用户在动态参数面板手动录入
        #   或运行时显式传值。
        if action_name in ("append", "count") and not has_default:
            return None, False, "", True

        # 构造 spec
        spec = {
            "flag": flag_name,
            "type_str": type_str,
            "default": default_value,
            "has_default": has_default,
            "is_flag_action": is_flag_action,
            "action_name": action_name,
            "nargs": nargs_value,
            "choices": choices,
        }

        return spec, False, "", has_dynamic_default

    def _eval_type(self, node: ast.AST) -> Tuple[str, bool, str]:
        """评估 type 关键字参数"""
        if isinstance(node, ast.Name):
            if node.id in self.DEGRADE_TYPES:
                return "", True, f"unsupported type: {node.id}"
            return node.id, False, ""
        elif isinstance(node, ast.Constant):
            # type=builtin type object 不常见，跳过
            return None, True, "type is a constant (unsupported)"
        else:
            # lambda / 复杂表达式 / FileType
            return "", True, "type is not a simple Name"

    def _eval_default(
        self, node: ast.AST
    ) -> Tuple[Any, bool, bool, str]:
        """
        评估 default 关键字参数。

        返回 (value, has_value, is_degraded, reason)

        ★ phase5+ Win 修复：处理 -42 这种 ast.UnaryOp(USub, Constant) 字面量
          之前只处理 Constant / List / Tuple，-42 被误判为"动态表达式"降级不进 ext02。
        """
        # None
        if isinstance(node, ast.Constant) and node.value is None:
            return None, False, False, ""

        # 字符串/数字/布尔字面量
        if isinstance(node, ast.Constant):
            return node.value, True, False, ""

        # ★ 一元负号字面量：-42 / -3.14 / -1.5e-10
        #   嵌套 UnaryOp（双重负）也兼容：--42 / -(-42) → 递归展开
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner_value, has_value, degraded, reason = self._eval_default(node.operand)
            if has_value and isinstance(inner_value, (int, float)):
                return -inner_value, True, False, ""
            return None, False, True, "unary minus on non-numeric literal"

        # list/tuple 字面量（1 层）
        if isinstance(node, (ast.List, ast.Tuple)):
            try:
                value = ast.literal_eval(node)
                return value, True, False, ""
            except (ValueError, SyntaxError):
                return None, False, True, "default list/tuple is not literal"

        # 其他表达式（os.path.expanduser, f-string, lambda 等）→ 降级
        return None, False, True, "default is not a literal"

    def _eval_action(self, node: ast.AST) -> Tuple[str, bool, str]:
        """评估 action 关键字参数"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            action_name = node.value
            if action_name in self.DEGRADE_ACTIONS:
                return "", True, f"unsupported action: {action_name}"
            return action_name, False, ""
        elif isinstance(node, ast.Attribute):
            # 如 argparse.BooleanOptionalAction
            full_name = ast.unparse(node)
            if full_name in self.DEGRADE_ACTIONS:
                return "", True, f"unsupported action: {full_name}"
            return "", True, f"unsupported action: {full_name}"
        else:
            return "", True, "action is not a string"

    def _eval_nargs(self, node: ast.AST) -> Tuple[Optional[str], bool, str]:
        """评估 nargs 关键字参数"""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return node.value, False, ""
            elif isinstance(node.value, int):
                return node.value, False, ""
        return None, True, "nargs is not a literal"

    def _eval_choices(self, node: ast.AST) -> Tuple[Optional[list], bool, str]:
        """评估 choices 关键字参数"""
        if isinstance(node, (ast.List, ast.Tuple)):
            try:
                value = ast.literal_eval(node)
                return value, False, ""
            except (ValueError, SyntaxError):
                return None, True, "choices is not a literal list"
        return None, True, "choices is not a literal list"

    def _assemble_argv(self, arg_specs: List[dict]) -> List[str]:
        """
        组装 argv list。

        规则（详见开发计划 §5.6.3）：
        - bool flag (store_true/store_false) → [flag]
        - append → [flag]
        - count → [flag, str(default)]
        - store_const → [flag, str(const)]
        - nargs='+' / nargs=int → [flag, *list elements]
        - nargs='*' → [flag]
        - nargs='?' → [flag, str(default)]（if has_default）
        - 普通 flag with default → [flag, str(default)]
        - default=None → []（运行时走 argparse default）
        """
        argv = []
        for spec in arg_specs:
            flag = spec["flag"]
            is_flag = spec["is_flag_action"]
            action = spec["action_name"]
            default = spec["default"]
            has_default = spec["has_default"]
            nargs = spec["nargs"]

            # 布尔标志：无值
            if is_flag:
                argv.append(flag)
                continue

            # append：默认值通常为 []
            if action == "append":
                if has_default and default:
                    argv.extend([flag] + [str(v) for v in default])
                else:
                    argv.append(flag)
                continue

            # count：默认值通常为 0
            if action == "count":
                argv.append(flag)
                if has_default and default is not None:
                    argv.append(str(default))
                continue

            # store_const
            if action == "store_const":
                # const 参数需要单独处理（简化：跳过 const，由用户脚本处理）
                argv.append(flag)
                continue

            # nargs='+' / nargs=int → 拆为多 token
            if nargs == "+" or isinstance(nargs, int):
                argv.append(flag)
                if has_default and default is not None:
                    argv.extend([str(v) for v in default])
                continue

            # nargs='*' → 输出 flag（运行时追加）
            if nargs == "*":
                argv.append(flag)
                continue

            # nargs='?'
            if nargs == "?":
                argv.append(flag)
                if has_default and default is not None:
                    argv.append(str(default))
                continue

            # 普通 flag
            if has_default and default is not None:
                argv.extend([flag, str(default)])
            # else: default=None，跳过（运行时走 argparse default）

        return argv


def parse_script_to_ext02(
    script_body: str,
) -> Tuple[Optional[str], bool, str, bool, List[str], List[str]]:
    """
    便捷函数：解析脚本并返回 JSON 序列化的 ext02。

    返回 (ext02, is_degraded, degrade_reason, has_dynamic_args,
          recognized_arg_names, unrecognized_arg_names)
    - ext02 为 None 表示解析失败（返回 None 给 api 层处理）。
    - has_dynamic_args: True 表示检测到动态默认值（ast.Name/Call/Attribute 等非字面量）。
    - recognized_arg_names: 已识别并写入 ext02 的 --flag 列表
    - unrecognized_arg_names: 未识别的 --flag 列表（动态默认 / 跳过 / degraded）
    """
    service = ScriptParserService()
    result = service.parse_and_assemble(script_body)

    ext02 = (
        json.dumps(result.argv_list, ensure_ascii=False)
        if result.argv_list is not None
        else None
    )
    return (
        ext02,
        result.is_degraded,
        result.degrade_reason,
        result.has_dynamic_args,
        result.recognized_arg_names,
        result.unrecognized_arg_names,
    )
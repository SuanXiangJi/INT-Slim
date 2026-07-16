# -*- coding: utf-8 -*-
"""
Calculator Tool - safe math expression evaluator
"""
import logging
import math
import ast
import operator
from app.tools.base import BaseTool, register_tool

logger = logging.getLogger(__name__)

ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

ALLOWED_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "exp": math.exp, "floor": math.floor, "ceil": math.ceil, "pow": pow,
    "pi": math.pi, "e": math.e, "tau": math.tau,
}


def _safe_eval(expr):
    tree = ast.parse(expr, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Unsupported constant")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in ALLOWED_OPS:
                raise ValueError("Unsupported operator")
            return ALLOWED_OPS[op_type](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in ALLOWED_OPS:
                raise ValueError("Unsupported unary op")
            return ALLOWED_OPS[op_type](_eval(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only named function calls allowed")
            name = node.func.id
            if name not in ALLOWED_FUNCS:
                raise ValueError("Unknown function: " + name)
            args = [_eval(a) for a in node.args]
            return ALLOWED_FUNCS[name](*args)
        if isinstance(node, ast.Name):
            if node.id in ALLOWED_FUNCS:
                v = ALLOWED_FUNCS[node.id]
                if isinstance(v, (int, float)):
                    return v
                raise ValueError(node.id + " is a function")
            raise ValueError("Unknown name: " + node.id)
        raise ValueError("Unsupported node")

    return _eval(tree.body)


@register_tool
class CalculatorTool(BaseTool):
    """Math calculator"""

    @property
    def id(self):
        return "calculator"

    @property
    def name(self):
        return "计算器"

    @property
    def description(self):
        return "安全地计算数学表达式。支持 +,-,*,/,**,%,sqrt,log,sin,cos,tan,pi,e 等。"

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式"
                }
            },
            "required": ["expression"]
        }

    async def execute(self, params, sandbox_path):
        expr = params.get("expression", "").strip()
        if not expr:
            return {"success": False, "error": "expression is required"}
        try:
            result = _safe_eval(expr)
            if isinstance(result, float):
                if result == int(result) and abs(result) < 1e15:
                    formatted = str(int(result))
                else:
                    formatted = "{:.10g}".format(result)
            else:
                formatted = str(result)
            return {
                "success": True,
                "expression": expr,
                "result": result,
                "formatted": formatted,
            }
        except ZeroDivisionError:
            return {"success": False, "error": "Division by zero"}
        except Exception as e:
            return {"success": False, "error": "Cannot evaluate: " + str(e)}

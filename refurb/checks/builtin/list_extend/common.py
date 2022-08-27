from dataclasses import dataclass

from mypy.nodes import (
    CallExpr,
    ExpressionStmt,
    MemberExpr,
    NameExpr,
    Statement,
)

from refurb.error import Error


@dataclass
class ErrorUseListExtend(Error):
    """
    When appending multiple values to a list, you can use the `.extend()`
    method to add an iterable to the end of an existing list. This way, you
    don't have to call `.append()` on every element:

    Bad:

    ```
    nums = [1, 2, 3]

    nums.append(4)
    nums.append(5)
    nums.append(6)
    ```

    Good:

    ```
    nums = [1, 2, 3]

    nums.extend((4, 5, 6))
    ```
    """

    code = 113
    msg: str = "Use `x.extend(...)` instead of repeatedly calling `x.append()`"


@dataclass
class Last:
    name: str = ""
    line: int = 0
    column: int = 0
    did_error: bool = False


def check_stmts(stmts: list[Statement], errors: list[Error]) -> None:
    last = Last()

    for stmt in stmts:
        match stmt:
            case ExpressionStmt(
                expr=CallExpr(
                    callee=MemberExpr(expr=NameExpr(name=name), name="append")
                )
            ):
                if not last.did_error and name == last.name:
                    errors.append(ErrorUseListExtend(last.line, last.column))
                    last.did_error = True

                last.name = name
                last.line = stmt.line
                last.column = stmt.column

            case _:
                last = Last()

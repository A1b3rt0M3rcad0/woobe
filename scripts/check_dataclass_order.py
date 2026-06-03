"""Validate all @dataclass in the project have correct field ordering."""
import ast
import glob
import sys


def check_dataclass_fields(filepath: str, cls_name: str, fields: list[tuple[str, bool]]) -> str | None:
    seen_default = False
    for name, has_default in fields:
        if has_default:
            seen_default = True
        elif seen_default:
            return f'{filepath}: @dataclass {cls_name}: required field "{name}" follows fields with defaults'
    return None


def main() -> int:
    errors: list[str] = []
    for f in sorted(glob.glob("src/**/domain/entities.py", recursive=True)):
        with open(f, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            is_dc = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Name)
                and d.func.id == "dataclass"
                for d in node.decorator_list
            )
            if not is_dc:
                continue

            fields: list[tuple[str, bool]] = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    has_default = item.value is not None
                    if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Attribute) and item.value.func.attr in ("field", "Field"):
                        has_default = True
                    fields.append((item.target.id, has_default))

            err = check_dataclass_fields(f, node.name, fields)
            if err:
                errors.append(err)

    if errors:
        print("ERRORS FOUND:")
        for e in errors:
            print(f"  {e}")
        return 1
    else:
        print("All @dataclass field orderings are correct.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

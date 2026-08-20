"""Guardrails for the generated command."""

import ast
import re

from .logging_utils import Logger


BAD_TOKENS = [
    " rm ",
    " rm\n",
    " rm\t",
    " rm-",
    " mv ",
    " cp ",
    " sudo ",
    " sed -i",
    " truncate ",
    " dd ",
    " :(){:|:&};:",
    " curl ",
    " wget ",
    " chown ",
    " chmod ",
    " mkfs",
    " mount ",
    " tee ",
    " touch ",
    " mkdir ",
]

PYTHON_DANGEROUS_SUBSTRINGS = [
    "os.remove(",
    "os.unlink(",
    "os.rmdir(",
    "os.rename(",
    "os.replace(",
    "os.mkdir(",
    "os.makedirs(",
    "os.chmod(",
    "os.chown(",
    "shutil.rmtree(",
    "shutil.move(",
    "shutil.copy(",
    "shutil.copy2(",
    ".write_text(",
    ".write_bytes(",
    ".unlink(",
    ".rename(",
    ".mkdir(",
    ".rmdir(",
    ".touch(",
    ".chmod(",
    ".chown(",
    "os.system(",
    "subprocess.",
]

# A real Python file mode is 1-4 chars from {r,w,x,a,b,t,U,+} and contains at
# least one write/append/exclusive flag. This is intentionally narrow so
# that quoted keyword strings like 'replace' or 'utf-8' do not false-match.
_PY_MODE_TOKEN = r"['\"][rwxabtU+]*[wax+][rwxabtU+]*['\"]"
PYTHON_WRITE_MODE_RE = re.compile(r"\bopen\s*\(\s*[^,()]+,\s*" + _PY_MODE_TOKEN)
PYTHON_WRITE_MODE_KW_RE = re.compile(r"\bopen\s*\([^)]*mode\s*=\s*" + _PY_MODE_TOKEN)
# Path("/x").open('w') has the mode as the first positional argument.
PYTHON_PATH_OPEN_RE = re.compile(r"\.open\s*\(\s*" + _PY_MODE_TOKEN)

REDIRECT_RE = re.compile(r"(?:^|\s)(?:\d?>>|&>>|&>|>>|>)")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z0-9_]+)\1")
PYTHON_INPUT_HINTS = ("sys.argv", "argparse", "ArgumentParser", "fileinput")

PYTHON_FORBIDDEN_IMPORTS = {"subprocess"}
PYTHON_FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
}
PYTHON_FORBIDDEN_ATTR_PREFIXES = {
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "os.rename",
    "os.replace",
    "os.mkdir",
    "os.makedirs",
    "os.chmod",
    "os.chown",
    "shutil.rmtree",
    "shutil.move",
    "shutil.copy",
    "shutil.copy2",
    "subprocess.",
    "pathlib.Path.write_text",
    "pathlib.Path.write_bytes",
    "pathlib.Path.unlink",
    "pathlib.Path.rename",
    "pathlib.Path.mkdir",
    "pathlib.Path.rmdir",
    "pathlib.Path.touch",
    "pathlib.Path.chmod",
    "pathlib.Path.chown",
}


def _strip_quoted_sections(text: str) -> str:
    out = []
    in_single = False
    in_double = False
    escape = False
    for ch in text:
        if escape:
            out.append(" " if (in_single or in_double) else ch)
            escape = False
            continue
        if ch == "\\" and in_double:
            escape = True
            out.append(" " if in_double else ch)
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(" ")
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(" ")
            continue
        out.append(" " if (in_single or in_double) else ch)
    return "".join(out)


def _mask_heredoc_content(text: str) -> str:
    lines = text.splitlines()
    out_lines = []
    in_heredoc = False
    terminator = None
    for line in lines:
        if in_heredoc:
            if terminator and line.strip() == terminator:
                in_heredoc = False
                terminator = None
                out_lines.append(line)
            else:
                out_lines.append("")
            continue
        match = HEREDOC_RE.search(line)
        if match:
            terminator = match.group(2)
            in_heredoc = True
        out_lines.append(line)
    return "\n".join(out_lines)


def _has_redirection(cmd: str) -> bool:
    scrubbed = cmd.replace("<<", "  ")
    return bool(REDIRECT_RE.search(scrubbed))


def _python_has_unsafe_calls(cmd: str, log: Logger) -> bool:
    for token in PYTHON_DANGEROUS_SUBSTRINGS:
        if token in cmd:
            log.warn(f"Blocked suspicious python token in generated command: {token.strip()}")
            return True
    if PYTHON_WRITE_MODE_RE.search(cmd) or PYTHON_WRITE_MODE_KW_RE.search(cmd):
        log.warn("Blocked python open() call with write/append/execute mode.")
        return True
    if PYTHON_PATH_OPEN_RE.search(cmd):
        log.warn("Blocked python Path.open() call with write/append/execute mode.")
        return True
    return False


def _attr_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    return ".".join(parts)


def _python_ast_is_safe(cmd: str, log: Logger) -> bool:
    try:
        tree = ast.parse(cmd)
    except Exception as exc:
        log.warn(f"Blocked python code that failed to parse: {exc}")
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in PYTHON_FORBIDDEN_IMPORTS:
                    log.warn(f"Blocked forbidden import: {alias.name}")
                    return False
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".", 1)[0] in PYTHON_FORBIDDEN_IMPORTS:
                log.warn(f"Blocked forbidden import: {node.module}")
                return False
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in PYTHON_FORBIDDEN_CALLS:
                    log.warn(f"Blocked forbidden call: {func_name}")
                    return False
                if func_name == "open":
                    if _open_call_has_write_mode(node):
                        log.warn("Blocked python open() call with write/append/execute mode.")
                        return False
            elif isinstance(node.func, ast.Attribute):
                attr = _attr_name(node.func)
                for prefix in PYTHON_FORBIDDEN_ATTR_PREFIXES:
                    if attr == prefix or attr.startswith(prefix):
                        log.warn(f"Blocked forbidden call: {attr}")
                        return False
    return True


def _open_call_has_write_mode(node: ast.Call) -> bool:
    if len(node.args) >= 2:
        mode_node = node.args[1]
        if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
            return any(flag in mode_node.value for flag in ("w", "a", "x", "+"))
    for keyword in node.keywords or []:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            val = keyword.value.value
            if isinstance(val, str):
                return any(flag in val for flag in ("w", "a", "x", "+"))
    return False


def _python_mentions_target(cmd: str, filename: str) -> bool:
    if filename in cmd:
        return True
    return any(hint in cmd for hint in PYTHON_INPUT_HINTS)


def looks_safe(cmd: str, filename: str, log: Logger, language: str = "bash") -> bool:
    if language == "python":
        if _python_has_unsafe_calls(cmd, log):
            return False
        if not _python_ast_is_safe(cmd, log):
            return False
        if not _python_mentions_target(cmd, filename):
            log.warn("Generated python code does not reference the target file; rejecting.")
            return False
        return True

    masked = _strip_quoted_sections(_mask_heredoc_content(cmd))
    s = f" {masked} "
    for bad in BAD_TOKENS:
        if bad in s:
            log.warn(f"Blocked suspicious token in generated command: {bad.strip()}")
            return False
    if _has_redirection(masked):
        log.warn("Blocked output redirection in generated command.")
        return False
    if filename not in cmd:
        log.warn("Generated command does not reference the target file; rejecting.")
        return False
    return True

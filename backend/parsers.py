from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .util import first_line, infer_value_type, json_safe, title_from_key

try:
    import toml as _toml  # type: ignore
except ImportError:  # pragma: no cover
    _toml = None

MAX_STRUCTURED_CHARS = 1_500_000


class ConfigParseError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Shared helpers


def pointer(parts: Sequence[str]) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts if str(part) != ""]
    return "/" + "/".join(escaped)


def _line_of(text: str, position: int) -> int:
    return text.count("\n", 0, max(0, position)) + 1


def _strip_comment_marker(line: str) -> str:
    stripped = line.strip()
    for marker in ("#", "//", ";"):
        if stripped.startswith(marker):
            stripped = stripped[len(marker) :].strip()
            break
    if stripped == ".":
        return ""
    return stripped


def comments_above(text: str, position: int, markers: Optional[Sequence[str]] = None) -> List[str]:
    line_start = text.rfind("\n", 0, position) + 1
    before = text[:line_start]
    lines = before.splitlines()
    collected: List[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            break
        if any(stripped.startswith(marker) for marker in (markers or ("#", "//", ";"))):
            cleaned = _strip_comment_marker(stripped)
            if cleaned:
                collected.append(cleaned)
            continue
        break
    collected.reverse()
    return collected


def _metadata_from_comments(comments: Sequence[str]) -> Dict[str, Any]:
    text = "\n".join(comments)
    description_lines = []
    range_min = None
    range_max = None
    enum = None
    for line in comments:
        stripped = line.strip()
        if re.match(r"(?i)^range\s*:", stripped):
            range_min, range_max = _parse_range(stripped.split(":", 1)[1])
            continue
        if re.match(r"(?i)^(allowed|valid)\s+values?\s*:", stripped):
            values = stripped.split(":", 1)[1].strip()
            parsed = _parse_enum(values)
            if parsed:
                enum = parsed
            continue
        if stripped in (".",):
            continue
        description_lines.append(stripped)
    description = "\n".join(description_lines).strip()
    return {
        "description": description,
        "min": range_min,
        "max": range_max,
        "enum": enum,
    }


def _parse_range(raw: str) -> Tuple[Optional[float], Optional[float]]:
    raw = raw.strip()
    match = re.search(
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(?:~|\.\.)\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
        raw,
    )
    if match:
        return _to_number(match.group(1)), _to_number(match.group(2))
    match = re.search(r"(>=?|<=?)\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", raw)
    if match:
        op, number = match.group(1), _to_number(match.group(2))
        if op.startswith(">"):
            return number, None
        return None, number
    return None, None


def _to_number(raw: str) -> Optional[float]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value.is_integer():
        return int(value)
    return value


def _parse_enum(raw: str) -> Optional[List[Any]]:
    raw = raw.strip().strip("[]")
    if not raw or len(raw) > 500:
        return None
    if "," in raw:
        parts = [part.strip() for part in raw.split(",")]
    elif "|" in raw:
        parts = [part.strip() for part in raw.split("|")]
    else:
        return None
    values = []
    for part in parts:
        part = part.strip().strip("'\"")
        if not part or " " in part and not re.match(r"^[A-Za-z0-9_ .:/-]+$", part):
            return None
        parsed = _parse_scalar(part)
        values.append(parsed)
    if 1 < len(values) <= 64:
        return values
    return None


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none", "~"):
        return None
    if re.fullmatch(r"[-+]?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+|\d+[eE][-+]?\d+|\d+\.\d*[eE][-+]?\d+)", value):
        try:
            number = float(value)
            return number
        except ValueError:
            pass
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        try:
            if value[0] == '"':
                return json.loads(value)
            return value[1:-1].replace("\\'", "'").replace("\\\\", "\\")
        except ValueError:
            return value[1:-1]
    return value


def _json_pointer_for(parts: Sequence[str], seen: Dict[str, int]) -> str:
    base = pointer(parts)
    count = seen.get(base, 0) + 1
    seen[base] = count
    if count > 1:
        return base + "~dup%d" % count
    return base


def _add_field(
    fields: List[Dict],
    seen: Dict[str, int],
    text: str,
    parts: Sequence[str],
    key: str,
    value: Any,
    span: Tuple[int, int],
    origin: str,
    comments: Sequence[str],
    *,
    editable: bool = True,
    multiline: bool = False,
    raw_value: str = "",
    extra: Optional[Dict] = None,
) -> Dict:
    safe_value = json_safe(value)
    value_type = infer_value_type(value)
    meta = _metadata_from_comments(comments)
    enum = meta["enum"]
    if enum:
        enum = [item for item in enum if infer_value_type(item) == value_type]
        if len(enum) < 2:
            enum = None
    if isinstance(value, float) and not math.isfinite(value):
        editable = False
    field = {
        "path": _json_pointer_for(parts, seen),
        "key": key,
        "label": title_from_key(key),
        "section": " › ".join(parts[:-1]),
        "value": safe_value,
        "type": value_type,
        "description": meta["description"],
        "line": _line_of(text, span[0]),
        "editable": editable and value_type != "null",
        "multiline": multiline,
        "raw_value": raw_value,
        "enum": enum,
        "min": meta["min"],
        "max": meta["max"],
        "_span": span,
        "_origin": origin,
    }
    if extra:
        field.update(extra)
    if isinstance(safe_value, float) and (math.isnan(safe_value) or math.isinf(safe_value)):
        field["editable"] = False
    fields.append(field)
    return field


def _empty_result(fmt: str, warnings: Optional[List[str]] = None, raw_only: bool = False) -> Dict:
    return {"format": fmt, "fields": [], "warnings": warnings or [], "note": "", "raw_only": raw_only}


# ---------------------------------------------------------------------------
# TOML


def _scan_toml_value(text: str, start: int) -> int:
    pos = start
    length = len(text)
    stack: List[str] = []
    while pos < length:
        char = text[pos]
        if char in ('"', "'"):
            delimiter = char * 3 if text.startswith(char * 3, pos) else char
            pos += len(delimiter)
            while pos < length:
                if text.startswith(delimiter, pos):
                    pos += len(delimiter)
                    break
                if delimiter != "'''" and delimiter != '"""' and text[pos] == "\\":
                    pos += 2
                    continue
                pos += 1
            continue
        if char == "#":
            newline = text.find("\n", pos)
            if newline < 0:
                pos = length
                break
            if not stack:
                break
            pos = newline
            continue
        if char in "[{":
            stack.append(char)
            pos += 1
            continue
        if char in "]}":
            if stack:
                stack.pop()
            pos += 1
            if not stack:
                # Consume the rest of the line only if there is no comment.
                probe = pos
                while probe < length and text[probe] in " \t\r":
                    probe += 1
                if probe >= length or text[probe] in "\n#":
                    if probe < length and text[probe] == "#":
                        return _trim_span_end(text, start, probe)
                    return _trim_span_end(text, start, probe)
            continue
        if char == "\n":
            if not stack:
                break
            pos += 1
            continue
        pos += 1
    return _trim_span_end(text, start, pos)


def _trim_span_end(text: str, start: int, end: int) -> int:
    while end > start and text[end - 1] in " \t\r\n":
        end -= 1
    return end


def _split_toml_key(key: str) -> List[str]:
    parts = []
    current = []
    quote = None
    for char in key.strip():
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
            continue
        if char == ".":
            parts.append("".join(current).strip().strip("'\""))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip().strip("'\""))
    return [part for part in parts if part]


def _toml_value_from_raw(raw: str) -> Any:
    if _toml is None:
        return _parse_scalar(raw)
    data = _toml.loads("__crafttune_value__ = " + raw)
    return data["__crafttune_value__"]


def _split_top_level(raw: str, separator: str = ",") -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    quote = None
    escaped = False
    for char in raw:
        if quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
        elif char in "[{(":
            depth += 1
            current.append(char)
        elif char in "]})":
            depth -= 1
            current.append(char)
        elif char == separator and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part != ""]


def _lenient_toml_value(raw: str) -> Any:
    """Read Forge's non-standard bare resource locations found in some configs."""
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        values = []
        for part in _split_top_level(inner):
            if part.startswith("[") or part.startswith("{"):
                values.append(_lenient_toml_value(part))
            else:
                values.append(_parse_scalar(part))
        return values
    return _parse_scalar(text)


def parse_toml(text: str) -> Dict:
    fields: List[Dict] = []
    seen: Dict[str, int] = {}
    warnings: List[str] = []
    section_parts: List[str] = []
    array_section_counts: Dict[str, int] = {}
    pos = 0
    length = len(text)
    while pos < length:
        line_end = text.find("\n", pos)
        if line_end < 0:
            line_end = length
        line = text[pos:line_end]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            pos = line_end + 1
            continue
        header = re.match(r"^\s*(\[\[?)(.+?)(\]\]?)\s*(?:#.*)?$", line)
        if header:
            raw_section = header.group(2).strip()
            is_array = header.group(1) == "[["
            section_parts = _split_toml_key(raw_section)
            if is_array:
                token = ".".join(section_parts)
                index = array_section_counts.get(token, 0) + 1
                array_section_counts[token] = index
                if index > 1:
                    section_parts = section_parts + ["#%d" % index]
            pos = line_end + 1
            continue
        key_match = re.match(r"^(\s*)([^=\n#]+?)\s*=\s*", line)
        if not key_match:
            pos = line_end + 1
            continue
        raw_key = key_match.group(2).strip()
        if not raw_key:
            pos = line_end + 1
            continue
        value_start = pos + key_match.end()
        value_end = _scan_toml_value(text, value_start)
        if value_end <= value_start:
            pos = line_end + 1
            continue
        raw_value = text[value_start:value_end].strip()
        comments = comments_above(text, pos)
        try:
            value = _toml_value_from_raw(raw_value)
            editable = True
            lenient = False
        except Exception:
            try:
                value = _lenient_toml_value(raw_value)
                if isinstance(value, str) and value == raw_value:
                    raise ValueError("not lenient")
                editable = True
                lenient = True
            except Exception:
                value = raw_value
                editable = False
                lenient = False
                warnings.append("第 %d 行无法解析为 TOML 值" % _line_of(text, pos))
        key_parts = _split_toml_key(raw_key)
        parts = section_parts + key_parts
        _add_field(
            fields,
            seen,
            text,
            parts,
            key_parts[-1] if key_parts else raw_key,
            value,
            (value_start, value_end),
            "toml",
            comments,
            editable=editable,
            multiline=("\n" in raw_value),
            raw_value=raw_value,
            extra={"lenient": lenient} if lenient else None,
        )
        pos = value_end
        while pos < length and text[pos] in " \t\r":
            pos += 1
        if pos < length and text[pos] == "#":
            newline = text.find("\n", pos)
            pos = length if newline < 0 else newline + 1
        elif pos < length and text[pos] == "\n":
            pos += 1
        elif pos < length:
            newline = text.find("\n", pos)
            pos = length if newline < 0 else newline + 1
    return {"format": "toml", "fields": fields, "warnings": warnings, "note": ""}


# ---------------------------------------------------------------------------
# JSON / JSON5 / HJSON


class _JsonNode:
    __slots__ = ("kind", "value", "start", "end", "entries", "items")

    def __init__(self, kind: str, value: Any, start: int, end: int):
        self.kind = kind
        self.value = value
        self.start = start
        self.end = end
        self.entries: List[Tuple[str, int, "_JsonNode"]] = []
        self.items: List["_JsonNode"] = []


class _Json5Parser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)
        self.depth = 0

    def error(self, message: str) -> ConfigParseError:
        line = _line_of(self.text, self.pos)
        return ConfigParseError("%s（第 %d 行）" % (message, line))

    def skip(self) -> None:
        while self.pos < self.length:
            char = self.text[self.pos]
            if char in " \t\r\n\ufeff":
                self.pos += 1
                continue
            if char == "/" and self.pos + 1 < self.length:
                next_char = self.text[self.pos + 1]
                if next_char == "/":
                    newline = self.text.find("\n", self.pos + 2)
                    self.pos = self.length if newline < 0 else newline + 1
                    continue
                if next_char == "*":
                    end = self.text.find("*/", self.pos + 2)
                    if end < 0:
                        raise self.error("块注释没有结束")
                    self.pos = end + 2
                    continue
            if char == "#":
                newline = self.text.find("\n", self.pos + 1)
                self.pos = self.length if newline < 0 else newline + 1
                continue
            break

    def parse(self) -> _JsonNode:
        self.skip()
        if self.pos >= self.length:
            raise self.error("文件为空")
        node = self.parse_value()
        self.skip()
        if self.pos < self.length:
            raise self.error("结尾存在多余内容")
        return node

    def parse_value(self) -> _JsonNode:
        self.skip()
        if self.pos >= self.length:
            raise self.error("缺少值")
        char = self.text[self.pos]
        if char == "{":
            return self.parse_object()
        if char == "[":
            return self.parse_array()
        if char in ('"', "'"):
            start = self.pos
            value = self.parse_string()
            return _JsonNode("string", value, start, self.pos)
        if char in "-+0123456789.":
            return self.parse_number()
        return self.parse_word()

    def parse_string(self) -> str:
        quote = self.text[self.pos]
        start = self.pos
        self.pos += 1
        out = []
        while self.pos < self.length:
            char = self.text[self.pos]
            if char == quote:
                self.pos += 1
                return "".join(out)
            if char == "\\":
                self.pos += 1
                if self.pos >= self.length:
                    break
                esc = self.text[self.pos]
                mapping = {
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    "b": "\b",
                    "f": "\f",
                    "/": "/",
                    "\\": "\\",
                    '"': '"',
                    "'": "'",
                    "0": "\0",
                }
                if esc in mapping:
                    out.append(mapping[esc])
                    self.pos += 1
                elif esc == "u":
                    hex_value = self.text[self.pos + 1 : self.pos + 5]
                    if len(hex_value) != 4 or not re.fullmatch(r"[0-9a-fA-F]{4}", hex_value):
                        raise self.error("Unicode 转义无效")
                    out.append(chr(int(hex_value, 16)))
                    self.pos += 5
                elif esc == "x":
                    hex_value = self.text[self.pos + 1 : self.pos + 3]
                    if len(hex_value) != 2 or not re.fullmatch(r"[0-9a-fA-F]{2}", hex_value):
                        raise self.error("十六进制转义无效")
                    out.append(chr(int(hex_value, 16)))
                    self.pos += 3
                elif esc in "\r\n":
                    if esc == "\r" and self.text[self.pos : self.pos + 2] == "\r\n":
                        self.pos += 1
                    self.pos += 1
                else:
                    out.append(esc)
                    self.pos += 1
                continue
            if char in "\r\n":
                raise self.error("字符串没有结束")
            out.append(char)
            self.pos += 1
        raise ConfigParseError("字符串没有结束（第 %d 行）" % _line_of(self.text, start))

    def parse_number(self) -> _JsonNode:
        start = self.pos
        match = re.match(
            r"[-+]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)",
            self.text[self.pos :],
        )
        if not match:
            raise self.error("数字格式无效")
        raw = match.group(0)
        self.pos += len(raw)
        try:
            if raw.lower().startswith(("0x", "+0x", "-0x")):
                value = int(raw, 16)
            elif re.fullmatch(r"[-+]?\d+", raw):
                value = int(raw)
            else:
                value = float(raw)
        except ValueError:
            raise self.error("数字格式无效")
        return _JsonNode("number", value, start, self.pos)

    def parse_word(self) -> _JsonNode:
        start = self.pos
        match = re.match(r"[A-Za-z_$][A-Za-z0-9_$.\-]*", self.text[self.pos :])
        if not match:
            raise self.error("无法识别的字符 %r" % self.text[self.pos])
        raw = match.group(0)
        self.pos += len(raw)
        low = raw.lower()
        if low == "true":
            value = True
            kind = "boolean"
        elif low == "false":
            value = False
            kind = "boolean"
        elif low == "null":
            value = None
            kind = "null"
        elif low in ("nan", "+nan", "-nan"):
            value = float("nan")
            kind = "number"
        elif low in ("infinity", "+infinity", "inf", "+inf"):
            value = float("inf")
            kind = "number"
        elif low in ("-infinity", "-inf"):
            value = float("-inf")
            kind = "number"
        else:
            value = raw
            kind = "string"
        return _JsonNode(kind, value, start, self.pos)

    def parse_object(self) -> _JsonNode:
        start = self.pos
        self.pos += 1
        node = _JsonNode("object", {}, start, start)
        self.depth += 1
        if self.depth > 200:
            raise self.error("嵌套层级过深")
        while True:
            self.skip()
            if self.pos >= self.length:
                raise self.error("对象没有结束")
            if self.text[self.pos] == "}":
                self.pos += 1
                break
            if self.text[self.pos] in ('"', "'"):
                key_start = self.pos
                key = self.parse_string()
            else:
                key_start = self.pos
                match = re.match(r"[A-Za-z0-9_#.$/\-]+", self.text[self.pos :])
                if not match:
                    raise self.error("对象键无效")
                key = match.group(0)
                self.pos += len(key)
            self.skip()
            if self.pos >= self.length or self.text[self.pos] != ":":
                raise self.error("对象键后缺少冒号")
            self.pos += 1
            value_node = self.parse_value()
            node.entries.append((key, key_start, value_node))
            node.value[key] = value_node.value
            self.skip()
            if self.pos >= self.length:
                raise self.error("对象没有结束")
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            # HJSON allows newline-separated members without commas.
            if self.text[self.pos] == "}":
                continue
            continue
        self.depth -= 1
        node.end = self.pos
        return node

    def parse_array(self) -> _JsonNode:
        start = self.pos
        self.pos += 1
        node = _JsonNode("array", [], start, start)
        self.depth += 1
        if self.depth > 200:
            raise self.error("嵌套层级过深")
        while True:
            self.skip()
            if self.pos >= self.length:
                raise self.error("数组没有结束")
            if self.text[self.pos] == "]":
                self.pos += 1
                break
            value_node = self.parse_value()
            node.items.append(value_node)
            node.value.append(value_node.value)
            self.skip()
            if self.pos >= self.length:
                raise self.error("数组没有结束")
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.text[self.pos] == "]":
                continue
            # Be permissive for HJSON / JSON with missing commas.
            continue
        self.depth -= 1
        node.end = self.pos
        return node


def _hidden_json_key(key: str) -> bool:
    low = key.lower()
    return key.startswith("#") or low in ("__comment", "_comment", "comment", "readme", "#readme")


def _flatten_json(
    node: _JsonNode,
    parts: List[str],
    text: str,
    fields: List[Dict],
    seen: Dict[str, int],
    comment_pos: Optional[int] = None,
) -> None:
    if node.kind == "object" and node.entries:
        for key, key_start, child in node.entries:
            if _hidden_json_key(key):
                continue
            _flatten_json(child, parts + [key], text, fields, seen, key_start)
        return
    if node.kind in ("object", "array"):
        comments = comments_above(text, comment_pos if comment_pos is not None else node.start, ("//", "#"))
        key = parts[-1] if parts else "value"
        _add_field(
            fields,
            seen,
            text,
            parts or ["value"],
            key,
            node.value,
            (node.start, node.end),
            "json",
            comments,
            multiline=node.kind == "array" and len(node.value) > 3,
            raw_value=text[node.start : node.end],
        )
        return
    comments = comments_above(text, comment_pos if comment_pos is not None else node.start, ("//", "#"))
    key = parts[-1] if parts else "value"
    _add_field(
        fields,
        seen,
        text,
        parts or ["value"],
        key,
        node.value,
        (node.start, node.end),
        "json",
        comments,
        multiline=isinstance(node.value, str) and "\n" in str(node.value),
        raw_value=text[node.start : node.end],
    )


def parse_json(text: str) -> Dict:
    warnings: List[str] = []
    fields: List[Dict] = []
    seen: Dict[str, int] = {}
    try:
        node = _Json5Parser(text).parse()
        _flatten_json(node, [], text, fields, seen)
    except ConfigParseError as exc:
        warnings.append(str(exc))
    except Exception as exc:  # pragma: no cover
        warnings.append("JSON 解析失败：%s" % exc)
    return {"format": "json5", "fields": fields, "warnings": warnings, "note": ""}


# ---------------------------------------------------------------------------
# YAML


def _yaml_split_key(line: str) -> Tuple[Optional[str], str, int]:
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote and (index == 0 or line[index - 1] != "\\"):
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            continue
        if char == ":":
            return line[:index].strip().strip("'\""), line[index + 1 :], index + 1
    return None, "", 0


def _strip_inline_comment(raw: str) -> str:
    quote = None
    for index, char in enumerate(raw):
        if quote:
            if char == quote and (index == 0 or raw[index - 1] != "\\"):
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            continue
        if char == "#" and index > 0 and raw[index - 1] in " \t":
            return raw[:index].rstrip()
    return raw.rstrip()


def parse_yaml(text: str) -> Dict:
    fields: List[Dict] = []
    seen: Dict[str, int] = {}
    warnings: List[str] = []
    stack: List[Tuple[int, str]] = []
    pos = 0
    length = len(text)
    while pos < length:
        line_end = text.find("\n", pos)
        if line_end < 0:
            line_end = length
        line = text[pos:line_end].rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped in ("---", "..."):
            pos = line_end + 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("- "):
            pos = line_end + 1
            continue
        key, rest, colon_end = _yaml_split_key(line)
        if key is None:
            pos = line_end + 1
            continue
        while stack and indent <= stack[-1][0]:
            stack.pop()
        raw_value = _strip_inline_comment(rest.strip())
        if raw_value == "":
            stack.append((indent, key))
            pos = line_end + 1
            continue
        if raw_value in ("|", ">", "|-", ">-"):
            pos = line_end + 1
            continue
        value_start = pos + colon_end
        while value_start < line_end and text[value_start] in " \t":
            value_start += 1
        value_end = value_start + len(raw_value)
        comments = comments_above(text, pos)
        parts = [item[1] for item in stack] + [key]
        if raw_value.startswith(("[", "{")):
            try:
                value = json.loads(raw_value.replace("'", '"'))
                editable = True
            except ValueError:
                value = raw_value
                editable = False
        else:
            value = _parse_scalar(raw_value)
            editable = True
        _add_field(
            fields,
            seen,
            text,
            parts,
            key,
            value,
            (value_start, value_end),
            "yaml",
            comments,
            editable=editable,
            multiline=False,
            raw_value=raw_value,
        )
        pos = line_end + 1
    return {"format": "yaml", "fields": fields, "warnings": warnings, "note": ""}


# ---------------------------------------------------------------------------
# Properties / CFG / generic key-value text


def _typed_cfg_value(prefix: str, raw: str) -> Any:
    if prefix == "B":
        return raw.strip().lower() == "true"
    if prefix in ("I", "S") and prefix == "I":
        try:
            return int(raw.strip())
        except ValueError:
            return raw.strip()
    if prefix == "D":
        try:
            return float(raw.strip())
        except ValueError:
            return raw.strip()
    return raw.strip()


def parse_keyvalue(text: str, fmt: str) -> Dict:
    fields: List[Dict] = []
    seen: Dict[str, int] = {}
    warnings: List[str] = []
    section: List[str] = []
    pos = 0
    length = len(text)
    is_cfg = fmt == "cfg"
    while pos < length:
        line_end = text.find("\n", pos)
        if line_end < 0:
            line_end = length
        line = text[pos:line_end].rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!", ";")):
            pos = line_end + 1
            continue
        section_match = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if section_match:
            section = [section_match.group(1).strip()]
            pos = line_end + 1
            continue
        if is_cfg and re.match(r"^\s*[\w .\-]+\s*\{\s*$", line):
            section.append(line.strip().rstrip("{").strip())
            pos = line_end + 1
            continue
        if is_cfg and stripped == "}":
            if section:
                section.pop()
            pos = line_end + 1
            continue
        typed = None
        if is_cfg:
            typed_match = re.match(r"^\s*([BIDS]):(.*)$", line)
            if typed_match:
                typed = typed_match.group(1)
                line_body = typed_match.group(2)
                sep_index = line_body.find("=")
                if sep_index < 0:
                    pos = line_end + 1
                    continue
                key = line_body[:sep_index].strip()
                raw_value = line_body[sep_index + 1 :].strip()
                value_start = pos + typed_match.start(2) + sep_index + 1
                while value_start < line_end and text[value_start] in " \t":
                    value_start += 1
                value_end = value_start + len(raw_value)
                value = _typed_cfg_value(typed, raw_value)
                comments = comments_above(text, pos)
                _add_field(
                    fields,
                    seen,
                    text,
                    section + [key],
                    key,
                    value,
                    (value_start, value_end),
                    "cfg",
                    comments,
                    raw_value=raw_value,
                    extra={"_prefix": typed, "_sep": "="},
                )
                pos = line_end + 1
                continue
        match = re.match(r"^(\s*)([^=:\s][^=:]*?)\s*([=:])\s*(.*)$", line)
        if not match:
            pos = line_end + 1
            continue
        key = match.group(2).strip()
        separator = match.group(3)
        raw_value = match.group(4).rstrip()
        value_start = pos + match.start(4)
        while value_start < line_end and text[value_start] in " \t":
            value_start += 1
        value_end = value_start + len(raw_value)
        comments = comments_above(text, pos)
        value = _parse_scalar(raw_value)
        _add_field(
            fields,
            seen,
            text,
            section + [key],
            key,
            value,
            (value_start, value_end),
            "keyvalue",
            comments,
            raw_value=raw_value,
            extra={"_sep": separator},
        )
        pos = line_end + 1
    return {"format": fmt, "fields": fields, "warnings": warnings, "note": ""}


# ---------------------------------------------------------------------------
# Public API


def parse_config_text(text: str, fmt: str) -> Dict:
    if not text or not text.strip():
        return _empty_result(fmt, ["文件为空"])
    if len(text) > MAX_STRUCTURED_CHARS:
        return _empty_result(
            fmt,
            ["文件体积较大（约 %.1f MB），已跳过结构化解析，避免界面卡顿。可使用源码模式编辑。" % (len(text) / 1024.0 / 1024.0)],
            raw_only=True,
        )
    try:
        if fmt == "toml":
            return parse_toml(text)
        if fmt in ("json", "json5"):
            result = parse_json(text)
            result["format"] = "json" if fmt == "json" else "json5"
            return result
        if fmt == "yaml":
            return parse_yaml(text)
        if fmt == "properties":
            return parse_keyvalue(text, "properties")
        if fmt == "cfg":
            return parse_keyvalue(text, "cfg")
        if fmt == "text":
            # Some mods use .txt files that actually contain TOML-ish key = value pairs.
            if len(re.findall(r"(?m)^\s*[A-Za-z0-9_.\-]+\s*=", text)) >= 2:
                toml_result = parse_toml(text)
                if len(toml_result["fields"]) >= 1:
                    toml_result["format"] = "toml"
                    toml_result["detected_format"] = "TOML"
                    return toml_result
            if len(re.findall(r"(?m)^\s*[A-Za-z0-9_.\-]+\s*:", text)) >= 2:
                result = parse_keyvalue(text, "text")
                result["format"] = "properties"
                result["detected_format"] = "Key-Value"
                return result
            return _empty_result("text", ["未识别到结构化参数，可使用源码模式直接编辑。"])
        return _empty_result("text", ["该文件格式暂不支持结构化编辑，可使用源码模式直接编辑。"])
    except Exception as exc:  # pragma: no cover - defensive
        return _empty_result(fmt, ["解析失败：%s" % exc])


# ---------------------------------------------------------------------------
# Serialisation / updates


def _format_toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = []
        for key, item in value.items():
            safe_key = key if re.fullmatch(r"[A-Za-z0-9_-]+", str(key)) else json.dumps(str(key), ensure_ascii=False)
            pairs.append("%s = %s" % (safe_key, _format_toml(item)))
        return "{ " + ", ".join(pairs) + " }"
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def _format_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _format_yaml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        if value and re.fullmatch(r"[A-Za-z0-9_./\-\u4e00-\u9fff][A-Za-z0-9_./\- :\u4e00-\u9fff]*", value) and not value.endswith(" "):
            if ": " not in value and " #" not in value and not value.startswith(("-", "?", ":", "!", "&", "*", "@", "`")):
                return value
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def _format_keyvalue(value: Any, field: Dict) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value)
    if "\n" in text or "\r" in text:
        text = text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
    return text


def _coerce(field: Dict, value: Any) -> Any:
    value_type = field.get("type")
    if value_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError("“%s”需要布尔值" % field["label"])
        result = value
    elif value_type == "integer":
        if isinstance(value, bool):
            raise ValueError("“%s”需要整数" % field["label"])
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            raise ValueError("“%s”需要整数" % field["label"])
        result = value
    elif value_type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("“%s”需要数字" % field["label"])
        result = float(value)
    elif value_type == "string":
        if not isinstance(value, str):
            raise ValueError("“%s”需要文本" % field["label"])
        result = value
    elif value_type == "array":
        if not isinstance(value, list):
            raise ValueError("“%s”需要数组" % field["label"])
        result = value
    elif value_type == "object":
        if not isinstance(value, dict):
            raise ValueError("“%s”需要对象" % field["label"])
        result = value
    else:
        raise ValueError("“%s”不支持修改" % field["label"])
    if field.get("enum") and result not in field["enum"]:
        raise ValueError("“%s”只能取：%s" % (field["label"], ", ".join(str(item) for item in field["enum"])))
    if isinstance(result, (int, float)) and not isinstance(result, bool):
        if field.get("min") is not None and result < field["min"]:
            raise ValueError("“%s”不能小于 %s" % (field["label"], field["min"]))
        if field.get("max") is not None and result > field["max"]:
            raise ValueError("“%s”不能大于 %s" % (field["label"], field["max"]))
    return result


def _field_format(field: Dict, value: Any) -> str:
    origin = field.get("_origin")
    if origin == "toml":
        return _format_toml(value)
    if origin == "json":
        return _format_json(value)
    if origin == "yaml":
        return _format_yaml(value)
    if origin in ("keyvalue", "cfg"):
        return _format_keyvalue(value, field)
    return str(value)


def update_config_text(text: str, fmt: str, changes: List[Dict]) -> Tuple[str, List[str]]:
    parsed = parse_config_text(text, fmt)
    fields = {field["path"]: field for field in parsed["fields"]}
    edits: List[Tuple[int, int, str]] = []
    warnings: List[str] = []
    for change in changes:
        path = str(change.get("path") or "")
        field = fields.get(path)
        if not field:
            warnings.append("未找到参数 %s，可能已被外部修改" % path)
            continue
        if not field.get("editable", True):
            warnings.append("参数“%s”不可编辑" % field["label"])
            continue
        try:
            value = _coerce(field, change.get("value"))
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        replacement = _field_format(field, value)
        start, end = field["_span"]
        edits.append((int(start), int(end), replacement))
    if warnings:
        raise ConfigParseError("；".join(warnings))
    edits.sort(key=lambda item: item[0], reverse=True)
    result = text
    last_start = None
    for start, end, replacement in edits:
        if last_start is not None and end > last_start:
            raise ConfigParseError("参数位置重叠，无法安全保存")
        result = result[:start] + replacement + result[end:]
        last_start = start
    return result, warnings


def public_fields(fields: Sequence[Dict]) -> List[Dict]:
    return [{key: value for key, value in field.items() if not key.startswith("_")} for field in fields]

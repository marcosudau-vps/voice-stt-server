"""
Small output-normalisation helpers used by the Kroko-ONNX engine.

The former tensor/device helpers served only the removed Transformers-based
engines (V2 engine cleanup) and were dropped with them.
"""

from collections.abc import Mapping


def attr_or_key(value, name, default=None):
    """
    Returns an attribute or mapping value by name.
    """
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def first_item(value):
    """
    Returns the first sequence item or the value itself.
    """
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def text_from_output(output):
    """
    Extracts display text from common model output shapes.
    """
    output = first_item(output)
    if output is None:
        return ""
    if isinstance(output, str):
        return output.strip()

    text = attr_or_key(output, "text")
    if text is not None:
        return str(text).strip()

    nested_outputs = attr_or_key(output, "outputs")
    nested_output = first_item(nested_outputs)
    nested_text = attr_or_key(nested_output, "text")
    if nested_text is not None:
        return str(nested_text).strip()

    return str(output).strip()

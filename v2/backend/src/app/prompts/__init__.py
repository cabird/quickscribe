"""Jinja2-based prompt template loader for QuickScribe v2."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pathlib import Path

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


def render(template_name: str, **kwargs: object) -> str:
    """Render a prompt template and return the user message text."""
    template = _env.get_template(f"{template_name}.j2")
    return template.render(**kwargs)


def render_messages(template_name: str, **kwargs: object) -> list[dict[str, str]]:
    """Render a prompt template and return a messages list.

    If the template defines a ``system_message`` variable via
    ``{% set system_message %}...{% endset %}``, it is included as the
    first message with role ``system``.  The rendered body becomes the
    ``user`` message.
    """
    template = _env.get_template(f"{template_name}.j2")
    module = template.make_module(vars=kwargs)

    messages: list[dict[str, str]] = []
    if hasattr(module, "system_message") and module.system_message:
        messages.append({"role": "system", "content": module.system_message.strip()})

    user_content = template.render(**kwargs)
    messages.append({"role": "user", "content": user_content})
    return messages

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from .._parse import parse_json_object
from .._transport import Transport
from ..errors import require_params
from ..types import DeleteTemplateResult, Template, TemplateEditor


def _fields(
    name: Optional[str],
    html_text: Optional[str],
    plain_text: Optional[str],
    from_name: Optional[str],
    from_email: Optional[str],
    reply_to: Optional[str],
    editor: Optional[TemplateEditor],
) -> Dict[str, Any]:
    return {
        "name": name,
        "html_text": html_text,
        "plain_text": plain_text,
        "from_name": from_name,
        "from_email": from_email,
        "reply_to": reply_to,
        "editor": editor,
    }


class Templates:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self) -> List[Template]:
        """The brand's templates by name, without their HTML."""
        text = self._transport.text("api/templates/get-templates.php", retryable=True)
        return cast(List[Template], parse_json_object(text, "templates").get("templates") or [])

    def get(self, template_id: int, *, include_content: bool = False) -> Template:
        """One template; ``html_text`` and ``plain_text`` only with ``include_content``."""
        text = self._transport.text(
            "api/templates/get-template.php",
            {"template_id": template_id, "include_content": "yes" if include_content else None},
            retryable=True,
        )
        return cast(Template, parse_json_object(text, "template"))

    def create(
        self,
        *,
        name: str,
        html_text: str,
        plain_text: Optional[str] = None,
        from_name: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        editor: Optional[TemplateEditor] = None,
    ) -> Template:
        """Not retried: a repeat would create a second template.

        ``editor`` is the one the Skrybe dashboard opens it in: ``html`` or
        ``dragdrop``.
        """
        require_params({"name": name, "html_text": html_text}, ["name", "html_text"])
        text = self._transport.text(
            "api/templates/create-template.php",
            _fields(name, html_text, plain_text, from_name, from_email, reply_to, editor),
        )
        return cast(Template, parse_json_object(text, "template"))

    def update(
        self,
        template_id: int,
        *,
        name: Optional[str] = None,
        html_text: Optional[str] = None,
        plain_text: Optional[str] = None,
        from_name: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        editor: Optional[TemplateEditor] = None,
    ) -> Template:
        """Only the fields given change."""
        text = self._transport.text(
            "api/templates/update-template.php",
            {
                "template_id": template_id,
                **_fields(name, html_text, plain_text, from_name, from_email, reply_to, editor),
            },
        )
        return cast(Template, parse_json_object(text, "template"))

    def delete(self, template_id: int) -> DeleteTemplateResult:
        """Campaigns already made from it are unaffected."""
        text = self._transport.text("api/templates/delete-template.php", {"template_id": template_id})
        return cast(DeleteTemplateResult, parse_json_object(text, "delete result"))

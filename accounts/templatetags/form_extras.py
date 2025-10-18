from django import template

register = template.Library()


def _combine_classes(existing: str, new: str) -> str:
    base = existing or ""
    addition = new or ""
    combined = f"{base} {addition}".split()
    return " ".join(dict.fromkeys(combined))


@register.filter(name="add_class")
def add_class(field, css_classes):
    """Render the bound field with additional CSS classes."""
    attrs = field.field.widget.attrs.copy() if hasattr(field.field.widget, "attrs") else {}
    existing_classes = attrs.get("class", "")
    attrs["class"] = _combine_classes(existing_classes, css_classes)
    return field.as_widget(attrs=attrs)

from jinja2 import Environment, FileSystemLoader, select_autoescape

_templates_path = __file__.rsplit("/", 1)[0] + "/admin/templates"

env = Environment(
    loader=FileSystemLoader(_templates_path),
    autoescape=select_autoescape(["html", "xml"]),
)
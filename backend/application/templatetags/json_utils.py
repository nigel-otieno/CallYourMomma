import json
from django import template
from django.utils.html import escapejs

register = template.Library()

@register.filter(name='as_json')
def as_json(value):
    return escapejs(json.dumps(value))

@register.filter(name='parse_json')
def parse_json(value):
    try:
        return json.loads(value)
    except Exception:
        return {}

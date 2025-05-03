from django import template
register = template.Library()

@register.filter
def add(value, arg):
    return int(value) + int(arg)

@register.filter
def sub(value, arg):
    try:
        return int(value) - int(arg)
    except Exception as e:
        print(f"[sub filter error] value={value} ({type(value)}), arg={arg} ({type(arg)})")
        return 0

@register.filter
def to_range(value):
    try:
        return range(1, int(value) + 1)
    except:
        return []

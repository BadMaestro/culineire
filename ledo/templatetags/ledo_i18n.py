from django import template
from ledo.i18n import translate

register = template.Library()
register.simple_tag(translate, name='t')
register.filter('ledo_translate', translate)

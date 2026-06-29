from django import template

register = template.Library()


@register.filter
def opponent_for(battle, author):
    return battle.opponent_for(author)

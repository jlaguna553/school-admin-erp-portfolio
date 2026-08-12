"""
modeltranslation registrations for the tenant registry.

Only genuinely translatable copy is registered. An institution's ``name`` is a
proper noun and is intentionally *not* translated.
"""

from modeltranslation.translator import TranslationOptions, register

from .models import Client


@register(Client)
class ClientTranslationOptions(TranslationOptions):
    # Public-facing marketing/description copy would go here, e.g.:
    # fields = ("tagline",)
    fields = ()

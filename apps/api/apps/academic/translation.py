"""
Translatable database fields for the academic context.

``django-modeltranslation`` adds one column per language per registered field
(``name_es``, ``name_en``, ...). Reading ``obj.name`` returns the value for the
active language, falling back per ``MODELTRANSLATION_FALLBACK_LANGUAGES``.

Codes are deliberately excluded: a registration code must be stable across
languages.
"""

from modeltranslation.translator import TranslationOptions, register

from .models import Program, Subject


@register(Program)
class ProgramTranslationOptions(TranslationOptions):
    fields = ("name", "description")
    required_languages = ("es",)  # Spanish is mandatory; English may be blank.


@register(Subject)
class SubjectTranslationOptions(TranslationOptions):
    fields = ("name", "description")
    required_languages = ("es",)

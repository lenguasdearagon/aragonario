import re


def get_lexicon_languages_from_code(lex_code):
    REGEX = r'^([a-zA-Z]{2,3})-([a-zA-Z]{2,3})$'
    match = re.match(REGEX, lex_code)

    if match is None:
        raise ValueError(
            "Lexicon code format should be 'en-es' where 'en' is the language "
            "source and 'es' is the language destination ISO 639 code."
        )

    return match.groups()

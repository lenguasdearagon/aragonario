from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import Q
from django.db.models import Value as V
from django.db.models.functions import MD5, Concat
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify

from linguatec_lexicon import utils, validators


def annotate_words_slug(lexicon):
    lex_slug = lexicon.slug
    qs = lexicon.words.all()
    return qs.annotate(
        calculated_slug=MD5(
            Concat(V(lex_slug), V("|"), "term")
        )
    )


class LexiconManager(models.Manager):
    def get_by_slug(self, slug):
        try:
            code, topic = slug.split("@")
        except ValueError:
            code = slug
            topic = ''

        src, dst = utils.get_lexicon_languages_from_code(code)

        return self.get(src_language=src, dst_language=dst, topic=topic)


class Lexicon(models.Model):
    """
    The Lexicon class provides a class to define a bilingual dictionary.

    Keep in mind that you define the Lexicon direction choosing the
    source and destination language. This direction is not
    bidirectional, so if you want to have a complete bilingual dictionary
    you have to create two Lexicon, one for each way.

    For example, a lexicon with Spanish as source language and
    Aragonese as destination language stores the translation in Aragonese
    for a collection of words in Spanish.

    """
    name = models.CharField(unique=True, max_length=32)
    description = models.TextField(blank=True)
    # TODO use ISO 639 codes??? https://www.iso.org/iso-639-language-codes.html
    src_language = models.CharField(max_length=2)
    dst_language = models.CharField(max_length=2)
    topic = models.CharField(max_length=32, blank=True, help_text="The subject of the lexicon.")

    objects = LexiconManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['src_language', 'dst_language', 'topic'], name='src-dst-topic')
        ]

    @property
    def code(self):
        return (self.src_language + '-' + self.dst_language)

    @property
    def slug(self):
        if not self.topic:
            return self.code

        topic = slugify(self.topic)
        return f"{self.src_language}-{self.dst_language}@{topic}"

    def __str__(self):
        return self.name

    def get_reverse_pair(self):
        """
        Retrieve reverse lexicon of language pair
        e.g. if current lexicon was Spanish-Aragonese returns Aragonese-Spanish
        """
        return Lexicon.objects.get(dst_language=self.src_language, src_language=self.dst_language, topic=self.topic)


class WordManager(models.Manager):
    TERM_PUNCTUATION_SIGNS = '¡!¿?'

    def _clean_search_query(self, query):
        """Handle characters which breaks or generate issues with regex expression."""
        if query is None:
            return query

        query = query.strip(self.TERM_PUNCTUATION_SIGNS)

        # escape special characters to avoid problems like unbalanced parenthesis
        query = query.replace("(", "\(").replace(")", "\)")

        return query

    def search(self, query, lex=None):
        MIN_SIMILARITY = 0.3
        query = self._clean_search_query(query)
        qs = self._filter_by_lexicon(lex)

        if connection.vendor == 'postgresql':
            iregex = r"\y{0}\y"
        elif connection.vendor == 'sqlite':
            iregex = r"\b{0}\b"
            return qs.filter(term__iregex=iregex.format(query))
        else:
            filter_query = (
                Q(term=query) |
                Q(term__startswith=query) |
                Q(term__endswith=query)
            )
            return qs.filter(filter_query)

        # sort results by trigram similarity
        qs = qs.filter(
            term__iregex=iregex.format(query)
        ).annotate(similarity=TrigramSimilarity('term', query)
                   ).filter(similarity__gt=MIN_SIMILARITY).order_by('-similarity')
        return qs

    def search_near(self, query, lex=None):
        # https://docs.djangoproject.com/en/2.1/ref/contrib/postgres/search/#trigram-similarity
        # https://www.postgresql.org/docs/current/pgtrgm.html
        # 0 means totally different
        # 1 means identical
        MIN_SIMILARITY = 0.2

        qs = self._filter_by_lexicon(lex)
        qs = qs.annotate(
            similarity=TrigramSimilarity('term', query),
        ).filter(similarity__gt=MIN_SIMILARITY).order_by('-similarity')

        return qs

    def _filter_by_lexicon(self, lex):
        if lex is None or lex == '':
            qs = self
        else:
            try:
                lexicon = Lexicon.objects.get_by_slug(lex)
            except Lexicon.DoesNotExist:
                qs = self.none()
            else:
                qs = self.filter(lexicon=lexicon)
        return qs


class Word(models.Model):
    """
    The Word class stores each word (written in the source language)
    that compounds the Lexicon.

    """
    lexicon = models.ForeignKey('Lexicon', on_delete=models.CASCADE, related_name="words")
    term = models.CharField(max_length=64)
    slug = models.SlugField()
    etimol = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['lexicon', 'term'], name='lexicon-term')
        ]

    objects = WordManager()

    def __str__(self):
        return self.term

    def gramcats(self):
        return set(self.entries.values_list('gramcats__abbreviation', flat=True))

    @property
    def admin_panel_url(self):
        return reverse('admin:linguatec_lexicon_word_change', args=(self.pk,))

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.slug = self.calculate_slug()
        if update_fields is not None and "term" in update_fields:
            update_fields = {"slug"}.union(update_fields)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def calculate_slug(self):
        return utils.calculate_slug(self.lexicon.slug, self.term)


class Region(models.Model):
    name = models.CharField(unique=True, max_length=64)

    def __str__(self):
        return self.name


class DiatopicVariation(models.Model):
    name = models.CharField(unique=True, max_length=64)
    abbreviation = models.CharField(unique=True, max_length=64)
    region = models.ForeignKey('Region', on_delete=models.CASCADE, related_name='variations')

    def __str__(self):
        return "{} ({})".format(self.name, self.region)


class Entry(models.Model):
    """
    The Entry class represents each translation (written in the
    destination language) for a word (written in the source language).

    """
    word = models.ForeignKey('Word', on_delete=models.CASCADE, related_name="entries")
    gramcats = models.ManyToManyField('GramaticalCategory', related_name="entries")
    variation = models.ForeignKey('DiatopicVariation', null=True, on_delete=models.CASCADE, related_name="entries")
    translation = models.TextField()
    marked_translation = models.TextField(default='', blank=True)

    class Meta:
        # TODO instead of depend on 'pk' find another method to
        # guarante that the entries are sorted by relevancy.
        # E.g. creating a positive integer field that stores their
        # order in the imported Excel.
        ordering = ['variation', 'pk']
        verbose_name_plural = "entries"
        constraints = [
            models.UniqueConstraint(fields=['word', 'variation', 'translation'], name='unique-entry')
        ]

    def __str__(self):
        return self.translation


class Example(models.Model):
    """
    The Example class stores examples of usage of a Entry.

    """
    entry = models.ForeignKey('Entry', on_delete=models.CASCADE, related_name="examples")
    phrase = models.TextField()

    def __str__(self):
        return self.phrase


class GramaticalCategory(models.Model):
    abbreviation = models.CharField(unique=True, max_length=64)
    title = models.CharField(max_length=128)

    class Meta:
        verbose_name_plural = "gramatical categories"

    def __str__(self):
        return self.abbreviation


class VerbalConjugation(models.Model):
    KEYWORD_MODEL = "modelo. conjug."
    KEYWORD_CONJUGATION = "conjug."

    entry = models.OneToOneField('Entry', on_delete=models.CASCADE, related_name="conjugation")
    raw = models.TextField('Raw imported content.')

    @cached_property
    def parse_raw(self):
        beg = None
        parsed = {}
        raw_lowcase = self.raw.lower()
        if self.KEYWORD_MODEL in raw_lowcase:
            beg = raw_lowcase.find(self.KEYWORD_MODEL)
            model_raw = raw_lowcase.split(self.KEYWORD_MODEL)[1].strip()
            model_parsed = validators.validate_verb_reference_to_model(model_raw)
            parsed["model"], parsed["model_word"] = model_parsed

        elif self.KEYWORD_CONJUGATION in raw_lowcase:
            beg = raw_lowcase.find(self.KEYWORD_CONJUGATION)
            # wordaround to allow partial conjugations see #66
            try:
                conjugation = validators.VerbalConjugationValidator()(self.raw)
            except ValidationError:
                beg = None
            else:
                parsed["conjugation"] = conjugation

        parsed["intro"] = self.raw[:beg].strip()

        return parsed

    @property
    def intro(self):
        return self.parse_raw.get('intro', None)

    @property
    def conjugation(self):
        return self.parse_raw.get('conjugation', None)

    @property
    def model(self):
        return self.parse_raw.get('model', None)

    @property
    def model_word(self):
        return self.parse_raw.get('model_word', None)

    @property
    def model_word_id(self):
        if self.model_word is None:
            return None
        try:
            return Word.objects.get(term=self.model_word, lexicon=self.entry.word.lexicon).pk
        except Word.DoesNotExist:
            # TODO log this error to detect database inconsistency
            return None


class Label(models.Model):
    name = models.CharField(max_length=64)
    entries = models.ManyToManyField(Entry, related_name="labels")
    lexicon = models.ForeignKey('Lexicon', on_delete=models.CASCADE, related_name="labels")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['lexicon', 'name'], name='lexicon-label')
        ]

    def __str__(self):
        return self.name

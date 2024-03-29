import os
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from linguatec_lexicon.models import (DiatopicVariation, Entry, Example,
                                      GramaticalCategory, Lexicon, Region,
                                      VerbalConjugation, Word)


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
APP_BASE_PATH = os.path.join(os.path.dirname(BASE_PATH), 'linguatec_lexicon')


class ImporterTestCase(TestCase):
    LEXICON_NAME = 'es-ar'
    LEXICON_CODE = 'es-ar'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Lexicon.objects.create(
            name=cls.LEXICON_NAME, src_language='es', dst_language='ar',
        )

    def setUp(self):
        # importdata requires that GramaticalCategories are initialized
        sample_path = os.path.join(APP_BASE_PATH, 'fixtures/gramcat-es-ar.csv')
        call_command('importgramcat', sample_path, verbosity=0)

    def test_import_sample(self):
        """
        Input file:
        -----------
        fixtures/sample-input.xlsx

        Expected output exported on file: fixtures/sample-output.json running:
        ---------------------------------------------------------------------
        from django.core.management import call_command
        call_command('dumpdata', 'linguatec_lexicon', indent=4, output='sample-output.json')

        Side effects: creation of the objects into the database
        -----------------------------------------------

        """
        NUMBER_OF_WORDS = 12
        NUMBER_OF_ENTRIES = 16
        NUMBER_OF_EXAMPLES = 2

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-input.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        self.assertEqual(NUMBER_OF_WORDS, Word.objects.count())
        self.assertEqual(NUMBER_OF_ENTRIES, Entry.objects.count())
        self.assertEqual(NUMBER_OF_EXAMPLES, Example.objects.count())

        # TODO make a more depth comparation between
        # call_command('dumpdata', 'linguatec_lexicon', indent=4, output='/tmp/test-output.json')
        # and fixtures/sample-output.json

    def test_missing_letters_as_sheets(self):
        NUMBER_OF_WORDS = 4

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/abcd.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        self.assertEqual(NUMBER_OF_WORDS, Word.objects.count())

    def test_dry_run(self):
        lexicon_initial = Lexicon.objects.count()

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-input.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path, dry_run=True)

        self.assertEqual(lexicon_initial, Lexicon.objects.count())
        self.assertEqual(0, Word.objects.count())
        self.assertEqual(0, Entry.objects.count())
        self.assertEqual(0, Example.objects.count())

    def test_invalid_gramcat_unkown(self):
        out = StringIO()
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(
            base_path, 'fixtures/invalid-gramcat-unknown.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path, stdout=out)

        # data shouldn't be imported if there are any errors
        self.assertEqual(0, Word.objects.count())
        self.assertIn('invalid', out.getvalue())

    def test_invalid_gramcat_empty(self):
        out = StringIO()
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(
            base_path, 'fixtures/invalid-gramcat-empty.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path, stdout=out)

        # data shouldn't be imported if there are any errors
        self.assertEqual(0, Word.objects.count())
        self.assertIn('empty', out.getvalue())

    def test_word_several_gramcats(self):
        NUMBER_OF_WORDS = 6
        NUMBER_OF_ENTRIES = 8

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(
            base_path, 'fixtures/multiple-gramcats.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        self.assertEqual(NUMBER_OF_WORDS, Word.objects.count())
        self.assertEqual(NUMBER_OF_ENTRIES, Entry.objects.count())

    def test_word_with_verbal_conjugation(self):
        NUMBER_OF_WORDS = 2
        NUMBER_OF_CONJUGATIONS = 2

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(
            base_path, 'fixtures/verbal-conjugation.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        self.assertEqual(NUMBER_OF_WORDS, Word.objects.count())
        self.assertEqual(NUMBER_OF_CONJUGATIONS,
                         VerbalConjugation.objects.count())

        # check that conjugation is related to proper entry
        word = Word.objects.get(term="abarcar",
                                lexicon=Lexicon.objects.get(src_language=self.LEXICON_CODE[:2],
                                                            dst_language=self.LEXICON_CODE[3:]))
        entry = word.entries.get(translation__contains="adubir")
        self.assertIsNotNone(entry.conjugation)

    def test_word_with_partial_verbal_conjugation(self):
        NUMBER_OF_WORDS = 3
        NUMBER_OF_CONJUGATIONS = 3

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(
            base_path, 'fixtures/partial-verbal-conjugation.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path, allow_partial=True)

        self.assertEqual(NUMBER_OF_WORDS, Word.objects.count())
        self.assertEqual(NUMBER_OF_CONJUGATIONS,
                         VerbalConjugation.objects.count())

    def test_import_data_to_a_previous_lexicon(self):
        another_lexicon = Lexicon.objects.create(
            name='ar-es',
            src_language='ar',
            dst_language='es',
        )

        NUMBER_OF_WORDS_FIRST_INPUT = 12
        NUMBER_OF_ENTRIES_FIRST_INPUT = 16

        NUMBER_OF_WORDS_SECOND_INPUT = 12
        NUMBER_OF_ENTRIES_SECOND_INPUT = 16

        NUMBER_OF_WORDS_THIRD_INPUT = 4
        NUMBER_OF_ENTRIES_THIRD_INPUT = 4

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-input.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        sample_path = os.path.join(base_path, 'fixtures/sample-input.xlsx')
        call_command('importdata', another_lexicon.code, sample_path)

        sample_path = os.path.join(base_path, 'fixtures/abcd.xlsx')
        call_command('importdata', another_lexicon.code, sample_path)

        self.assertEqual(NUMBER_OF_WORDS_FIRST_INPUT + NUMBER_OF_WORDS_SECOND_INPUT + NUMBER_OF_WORDS_THIRD_INPUT,
                         Word.objects.count())
        self.assertEqual(NUMBER_OF_ENTRIES_FIRST_INPUT + NUMBER_OF_ENTRIES_SECOND_INPUT + NUMBER_OF_ENTRIES_THIRD_INPUT,
                         Entry.objects.count())

        self.assertEqual(NUMBER_OF_WORDS_FIRST_INPUT,
                         Word.objects.filter(lexicon=(Lexicon.objects.get(src_language=self.LEXICON_CODE[:2],
                                                                          dst_language=self.LEXICON_CODE[3:]))).count())
        self.assertEqual(NUMBER_OF_WORDS_SECOND_INPUT + NUMBER_OF_WORDS_THIRD_INPUT,
                         Word.objects.filter(lexicon=another_lexicon).count())
        self.assertEqual(2, Lexicon.objects.count())

    def test_invalid_duplicated_gramcat_and_translation(self):
        stderr = StringIO()
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-duplicated-term.xlsx')

        self.assertRaises(CommandError, call_command, 'importdata',
                          self.LEXICON_CODE, sample_path, stderr=stderr)
        self.assertEqual(0, Word.objects.count())
        self.assertIn('Duplicated', stderr.getvalue())

    def test_valid_diff_gramcat_same_translation(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-same-translation-different-gramcat.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        self.assertEqual(2, Word.objects.count())
        self.assertEqual(4, Entry.objects.count())

        word_one = Word.objects.get(term="bien")
        self.assertEqual(
            [('bien', 's. m.'), ('bien', 'adv. m.')],
            list(word_one.entries.values_list('translation', 'gramcats__abbreviation')),
        )

        entry_three = Entry.objects.filter(word__term="cantar")[0]
        self.assertEqual(
            ['s. m.'],
            list(entry_three.gramcats.values_list('abbreviation', flat=True)),
        )

        entry_four = Entry.objects.filter(word__term="cantar")[1]
        self.assertEqual(
            ['v. intr.', 'v. tr.'],
            list(entry_four.gramcats.values_list('abbreviation', flat=True)),
        )

    def test_duplicated_diff_word(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-same-translation-gramcat-diff-word.xlsx')
        call_command('importdata', self.LEXICON_CODE, sample_path)

        self.assertEqual(3, Word.objects.count())
        self.assertEqual(3, Entry.objects.count())


class ImportGramCatTestCase(TestCase):
    NUMBER_OF_GRAMCATS = 79

    def test_import(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(APP_BASE_PATH, 'fixtures/gramcat-es-ar.csv')
        call_command('importgramcat', sample_path)

        self.assertEqual(self.NUMBER_OF_GRAMCATS,
                         GramaticalCategory.objects.count())

    def test_purge_and_import(self):
        GramaticalCategory.objects.create(abbreviation="f.", title="foo")
        existing_gramcats = GramaticalCategory.objects.count()

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(APP_BASE_PATH, 'fixtures/gramcat-es-ar.csv')
        call_command('importgramcat', sample_path, purge=True)

        self.assertNotEqual(self.NUMBER_OF_GRAMCATS + existing_gramcats,
                            GramaticalCategory.objects.count())


class ImportVariationTestCase(TestCase):
    NUMBER_OF_ENTRIES = 115

    @classmethod
    def get_fixture_path(cls, name):
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, 'fixtures/{}'.format(name))

    @classmethod
    def setUpTestData(cls):
        lexicon = Lexicon.objects.create(
            name='es-ar', src_language='es', dst_language='ar',
        )

        # Create Regions
        ribagorza = Region.objects.create(name="Ribagorza")

        # Create DiatopicVariation
        DiatopicVariation.objects.create(
            name="benasqués",
            abbreviation="Benas.",
            region=ribagorza,
        )

        # initialize GramaticalCategories
        sample_path = os.path.join(APP_BASE_PATH, 'fixtures/gramcat-es-ar.csv')
        call_command('importgramcat', sample_path, verbosity=0)

        # initialize words on main language
        sample_path = cls.get_fixture_path('variation-sample-common.xlsx')
        call_command('importdata', lexicon.code, sample_path)

    def test_import(self):
        sample_path = self.get_fixture_path('variation-sample-benasques.xlsx')
        call_command('importvariation', 'es-ar', sample_path,
                     variation='benasqués', verbosity=4)

        qs = Entry.objects.filter(variation__isnull=False).values(
            'word__id').order_by('word__id').distinct('word__id')
        self.assertEqual(self.NUMBER_OF_ENTRIES, qs.count())

    def test_import_invalid_empty_row(self):
        out = StringIO()
        sample_path = self.get_fixture_path('variation-empty-row.xlsx')
        try:
            call_command('importvariation', 'es-ar', sample_path,
                         variation='benasqués', verbosity=3, stdout=out)
        except TypeError:
            pass

        qs = Entry.objects.filter(variation__isnull=False).values(
            'word__id').order_by('word__id').distinct('word__id')
        self.assertEqual(0, qs.count())
        self.assertIn('error', out.getvalue())

    def test_import_ignore_extra_cols(self):
        FIXTURE_NUMBER_OF_ENTRIES = 4

        sample_path = self.get_fixture_path('variation-sample-benasques-extra-cols.xlsx')
        call_command('importvariation', 'es-ar', sample_path,
                     variation='benasqués', verbosity=4)

        qs = Entry.objects.filter(variation__isnull=False).values(
            'word__id').order_by('word__id').distinct('word__id')
        self.assertEqual(FIXTURE_NUMBER_OF_ENTRIES, qs.count())

    def test_import_variation_optional_on_dry_run(self):
        sample_path = self.get_fixture_path('variation-sample-benasques.xlsx')
        call_command('importvariation', 'es-ar', sample_path, dry_run=True, verbosity=4)

        qs = Entry.objects.filter(variation__isnull=False).values(
            'word__id').order_by('word__id').distinct('word__id')
        self.assertEqual(0, qs.count())

    def test_import_invalid_unkown_gramcat(self):
        out = StringIO()
        sample_path = self.get_fixture_path('variation-unkown-gramcat.xlsx')
        call_command('importvariation', 'es-ar', sample_path,
                     dry_run=True, verbosity=3, stdout=out)

        self.assertIn('error', out.getvalue())

    def test_import_missing_gramcat(self):
        VARIATION_NAME = 'benasqués'
        out = StringIO()
        sample_path = self.get_fixture_path('variation-missing-gramcat.xlsx')
        call_command('importvariation', 'es-ar', sample_path,
                     variation=VARIATION_NAME, verbosity=3, stdout=out)

        self.assertNotIn('error', out.getvalue())

        # should provide default value --> 'v.' (same as common entry)
        common_entry = Word.objects.get(term='abarrancar',
                                        lexicon=Lexicon.objects.get(src_language='es', dst_language='ar'))

        variation_entry = Entry.objects.get(variation__name=VARIATION_NAME, word__term='abarrancar')

        self.assertListEqual(
            list(common_entry.gramcats()),
            list(variation_entry.gramcats.values_list('abbreviation', flat=True))
        )

    def test_import_invalid_missing_translation(self):
        out = StringIO()
        sample_path = self.get_fixture_path('variation-missing-translation.xlsx')
        call_command('importvariation', 'es-ar', sample_path,
                     dry_run=True, verbosity=3, stdout=out)

        self.assertIn('error', out.getvalue())

    def test_import_dry_run_and_variation(self):
        # regression test: call with dry-run & variation parameters
        out = StringIO()
        sample_path = self.get_fixture_path('variation-sample-benasques.xlsx')
        call_command('importvariation', 'es-ar', sample_path,
                     variation='benas', dry_run=True, verbosity=3, stdout=out)
        self.assertNotIn('error', out.getvalue())

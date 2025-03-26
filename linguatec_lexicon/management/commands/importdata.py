import json
import pprint
import sys

import pandas as pd
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils.functional import cached_property

from linguatec_lexicon import utils
from linguatec_lexicon.models import (Entry, Example, GramaticalCategory,
                                      Label, Lexicon, VerbalConjugation, Word)
from linguatec_lexicon.validators import validate_column_verb_conjugation

# gramcat auto correction (very common mistakes that could be autocorrected)
GRAMCAT_AUTO_CORRECTION = {
    "s.f.": "s. f.",
    "s.m.": "s. m.",
}


def split_data_frame_list(df, target_column):
    # thanks src https://gist.github.com/jlln/338b4b0b55bd6984f883#gistcomment-2676729
    """
    Splits a column with lists into rows

    Keyword arguments:
        df -- dataframe
        target_column -- name of column that contains lists
    """

    # create a new dataframe with each item in a seperate column, dropping rows with missing values
    col_df = pd.DataFrame(df[target_column].dropna(
    ).tolist(), index=df[target_column].dropna().index)

    # create a series with columns stacked as rows
    stacked = col_df.stack()

    # rename last column to 'idx'
    index = stacked.index.rename(names="idx", level=-1)
    new_df = pd.DataFrame(stacked, index=index, columns=[target_column])
    return new_df


def extract_gramcats(db):
    db_s = split_data_frame_list(db, 1)
    # src https://datascience.stackexchange.com/questions/29840/how-to-count-grouped-occurrences/29842#29842
    gramcats = db_s.groupby([1]).size().to_frame('count').reset_index()
    print('=========================')
    print('Gramatical categories')
    print(gramcats)
    print('=========================')
    return gramcats


def is_verb(gramcats):
    for gramcat in gramcats:
        if (gramcat.abbreviation.startswith('v.')
                or gramcat.abbreviation in ['expr.', 'per. vl.', 'loc. vl.']):
            return True
    return False


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'lexicon_code', type=str,
            help="Select the lexicon where data will be imported",
        )
        parser.add_argument('input_file', type=str)
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry_run',
            help="Just validate input file; don't actually import to database.",
        )
        parser.add_argument(
            '--allow-partial', action='store_true', dest='allow_partial',
            help="Allow verbs with partial or unknown format conjugations. USE WITH CAUTION",
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.verbosity = options['verbosity']
        self.input_file = options['input_file']
        self.allow_partial = options['allow_partial']
        self.lexicon_code = options['lexicon_code']

        # check that GramaticalCategories are initialized
        if not GramaticalCategory.objects.all().exists():
            raise CommandError(
                "There isn't any GramaticalCategory in the database. "
                "Gramatical Categories should be initialized before importing "
                "data for example running manage.py importgramcat."
            )

        # check that a lexicon with that code exist
        try:
            self.lexicon = Lexicon.objects.get_by_slug(self.lexicon_code)
        except Lexicon.DoesNotExist:
            raise CommandError('Error: There is not a lexicon with that code: ' + self.lexicon_code)

        self.stdout.write(self.style.NOTICE(f"INFO\tinput file: {self.input_file}\n"))

        db = self.read_input_file()

        # TODO add arg to print (or not gramcats)
        # gramcats = extract_gramcats(db)

        self.populate_models(db)

        if self.verbosity >= 2 and self.cleaned_labels:
            self.stdout.write(f"Labels of {self.lexicon.slug}")
            self.stdout.write("; ".join(self.cleaned_labels))

        if self.errors:
            self.stdout.write(self.style.ERROR(f"Detected {len(self.errors)} errors!"))
            if self.verbosity >= 2:
                error_messages_by_type = {}
                for error in self.errors:
                    message = error["message"]
                    word = error["word"]

                    if message not in error_messages_by_type:
                        error_messages_by_type[message] = []
                    error_messages_by_type[message].append(word)

                formatted_output = pprint.pformat(error_messages_by_type, indent=2, width=100)
                self.stdout.write(formatted_output)

        elif not self.dry_run:
            # Write data into the database
            self.write_to_database()

    def read_input_file(self):
        df = pd.DataFrame()

        xlsx = pd.ExcelFile(self.input_file)

        data = []
        for sheet in xlsx.sheet_names:
            # we define na_values and keep_default_na because defaults na_values
            # includes empty string. We don't want that pandas replaces empty
            # cells with 'nan'
            partial = xlsx.parse(sheet, header=None, usecols='A:F')
            # names=['colA', 'colB', 'colC', 'colD', 'colE', 'colF'])
            data.append(partial)

        df = pd.concat(data)
        df_obj = df.select_dtypes(['object'])
        df[df_obj.columns] = df_obj.apply(lambda x: x.str.strip())
        df = df.fillna('')  # replace NaN with blank string

        return df

    def get_or_create_word(self, term):
        try:
            return (False, self.cleaned_data[term])
        except KeyError:
            new_word = Word(term=term, lexicon_id=self.lexicon.pk)
            new_word.clean_entries = []
            return (True, new_word)

    def populate_word(self, w_str):
        # avoid duplicated word.term
        created, word = self.get_or_create_word(w_str)
        if created:
            word.slug = utils.calculate_slug(self.lexicon.slug, word.term)
            self.cleaned_data[word.term] = word

        return word

    def populate_gramcats(self, word, g_str):
        gramcats = []
        if not g_str:
            self.errors.append({
                "word": word.term,
                "column": "B",
                "message": "missing gramatical category"
            })
        else:
            for abbr in g_str.split("//"):
                abbr = abbr.strip()
                try:
                    gramcats.append(self.retrieve_gramcat(abbr))
                except GramaticalCategory.DoesNotExist:
                    self.errors.append({
                        "word": word.term,
                        "column": "B",
                        "message": "unkown gramatical category '{}'".format(abbr)
                    })
        word.is_verb = is_verb(gramcats)
        return gramcats

    def retrieve_gramcat(self, abbr):
        try:
            return self._gramcats[abbr]
        except KeyError:
            pass

        # if fails, try with auto_correction
        try:
            auto_correction = GRAMCAT_AUTO_CORRECTION[abbr]
            return self._gramcats[auto_correction]
        except KeyError:
            pass

        raise GramaticalCategory.DoesNotExist()

    @cached_property
    def _gramcats(self):
        # one big query vs N queries where N is the number of entries
        return {g.abbreviation: g for g in GramaticalCategory.objects.all()}

    def populate_entries(self, word, gramcats, entries_str):
        for translation in entries_str.split('//'):
            entry = Entry(translation=translation.strip())
            entry.clean_gramcats = gramcats
            entry.clean_examples = []
            entry.word_term = word.term  # term is unique for a lexicon
            word.clean_entries.append(entry)
            self.cleaned_entries.append(entry)

    def populate_examples(self, word, ex_str):
        if pd.isnull(ex_str) or ex_str == '':
            return

        ex_strs = [x.strip() for x in ex_str.split('//')]
        if len(word.clean_entries) < len(ex_strs):
            self.errors.append({
                "word": word.term,
                "column": "E",
                "message": "there are more examples '{}' than entries'{}'".format(
                    len(ex_strs), len(word.clean_entries))
            })
            # invalid format, don't try to extract it!
            return

        for i, value in enumerate(ex_strs):  # subelement
            we = word.clean_entries[i]  # word entry
            if value:
                # TODO could be several examples separated by ';'
                we.clean_examples.append(Example(phrase=value))

    def populate_verbal_conjugation(self, word, gramcats, conjugation_str):
        # check if word is a verb
        if conjugation_str and not word.is_verb:
            gramcats = [x.abbreviation for x in gramcats]
            self.errors.append({
                "word": word.term,
                "column": "F",
                "message": "only verbs can have verbal conjugation data (found {})".format(gramcats),
            })
            return

        raw_conjugations = [x.strip()
                            for x in conjugation_str.split('//')]

        # check number of conjugations VS number of entries
        if len(word.clean_entries) < len(raw_conjugations):
            self.errors.append({
                "word": word.term,
                "column": "F",
                "message": "there are more conjugations '{}' than entries'{}'".format(
                    len(word.clean_entries), len(conjugation_str))
            })
            # invalid format, don't try to extract it!
            return

        for i, raw_conjugation in enumerate(raw_conjugations):
            if raw_conjugation:
                try:
                    validate_column_verb_conjugation(raw_conjugation)
                except ValidationError as e:
                    if not self.allow_partial:
                        self.errors.append({
                            "word": word.term,
                            "column": "F",
                            "message": str(e.message),
                        })
                    partial = True
                else:
                    partial = False
                # workaround issue 66 allow partial conjugations (or unformated data)
                if not partial or partial and self.allow_partial:
                    word.clean_entries[i].clean_conjugation = VerbalConjugation(
                        raw=raw_conjugation)

    def populate_models(self, db):
        self.errors = []
        self.cleaned_data = {}
        self.cleaned_entries = []
        self.cleaned_labels = set()
        for row in db.itertuples(name=None):
            # itertuples by default return the index as the first element of the tuple.

            # filter empty rows
            # TODO how to ignore empty rows in an elegant way?
            if pd.isnull(row) or pd.isna(row[1]) or pd.isnull(row[1]) or row[1] == '':
                continue

            # column A is word (required)
            word = self.populate_word(row[1])

            # column B is gramcat (required)
            gramcats = self.populate_gramcats(word, row[2])

            # column C is entry (required)
            self.populate_entries(word, gramcats, row[3])

            # column D is label or category (optional)
            try:
                label_str = row[4]
            except IndexError:
                continue
            self.populate_label(word, label_str)

            # column E is example (optional)
            try:
                ex_str = row[5]
            except IndexError:
                continue
            self.populate_examples(word, ex_str)

            # column F is verb conjugation
            try:
                conjugation_str = row[6]
            except IndexError:
                continue
            self.populate_verbal_conjugation(word, gramcats, conjugation_str)

    def populate_label(self, word, label_str):
        # support multiple label (separated by "//")
        row_labels = []
        for label in label_str.split("//"):
            label = label.strip()

            # discard empty `labels`
            if label:
                self.cleaned_labels.add(label)

            # add empty label to keep offset of multiple label ("//")
            row_labels.append(label)

        # by default if only one label, apply to all entries
        # this way we avoid that the user needs to duplicate it
        if len(word.clean_entries) > len(row_labels):
            for entry in word.clean_entries:
                entry.label = row_labels[0]

        # match each label with the entry
        else:
            for i, entry in enumerate(word.clean_entries):
                entry.label = row_labels[i]

    @transaction.atomic
    def write_to_database(self):
        count_words = 0
        count_entries = 0
        count_examples = 0

        try:
            Word.objects.bulk_create(self.cleaned_data.values(), batch_size=100)
        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(
                "Error: Already exists term '{}' on lexicon '{}'".format(e, self.lexicon_code)
            ))
            sys.exit(1)

        # retrieve words to get its PK
        words = {w[0]: w[1] for w in Word.objects.filter(lexicon=self.lexicon).values_list('term', 'id')}
        count_words = len(self.cleaned_data)

        for entry in self.cleaned_entries:
            word_pk = words[entry.word_term]
            entry.word_id = word_pk
        Entry.objects.bulk_create(self.cleaned_entries, batch_size=100)

        for entry in self.cleaned_entries:
            entry.gramcats.set(entry.clean_gramcats)
            count_entries += 1

            for example in entry.clean_examples:
                example.entry_id = entry.pk
                example.save()
                count_examples += 1

            try:
                entry.clean_conjugation.entry_id = entry.pk
                entry.clean_conjugation.save()
            except AttributeError:
                pass

        # store labels & create relations with entries
        # NOTE only create not existing labels. For example ar-es
        # content is splited on several XLSX files so labels may
        # already exist.
        existing_labels = self.lexicon.labels.values_list("name", flat=True)
        new_labels = self.cleaned_labels - set(existing_labels)
        Label.objects.bulk_create([
            Label(name=label, lexicon=self.lexicon) for label in new_labels
        ], batch_size=200)

        # cache labels to optimize get query
        all_labels = {label.name: label for label in self.lexicon.labels.all()}
        for entry in self.cleaned_entries:
            if getattr(entry, "label", None):
                label_model = all_labels[entry.label]
                label_model.entries.add(entry)

        self.validate_unique_together()

        self.stdout.write("Imported: %s words, %s entries, %s examples" %
                          (count_words, count_entries, count_examples))

    def validate_unique_together(self):
        """
        Detect duplicated term(translation, gramcats) and add error if any
        """
        unique_together = ['word', 'translation', 'gramcats']
        qs = Entry.objects.filter(word__lexicon=self.lexicon).order_by(*unique_together)
        qs_distinct = qs.distinct(*unique_together)

        if qs.count() > qs_distinct.count():
            dupes = qs.exclude(pk__in=qs_distinct.values_list('pk', flat=True))

            for e in dupes.select_related('word'):
                self.stderr.write(self.style.ERROR(
                    json.dumps({
                        "word": e.word.term,
                        "column": "B & C",
                        "message": "Duplicated pair translation and gramcat '{}'".format(e.translation)
                    })
                ))

            raise CommandError()

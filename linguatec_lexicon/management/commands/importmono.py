import json

from django.core.management import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from linguatec_lexicon.models import Entry, Lexicon, Word


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'lexicon_code', type=str,
            help="Select the lexicon where data will be imported",
        )
        parser.add_argument('input_file', type=str)

    @transaction.atomic
    def handle(self, *args, **options):
        self.input_file = options['input_file']
        self.lexicon_code = options['lexicon_code']

        # check that a lexicon with that code exist
        try:
            self.lexicon = Lexicon.objects.get_by_slug(self.lexicon_code)
        except Lexicon.DoesNotExist:
            raise CommandError('Error: There is not a lexicon with that code: ' + self.lexicon_code)

        # self.xlsx = pd.read_excel(self.input_file, sheet_name=None, header=None, usecols="A:E",
        #                           names=["term", "url", "etimol", "def", "def2"])

        # use temp lexicon and if everything is ok, then change to the real one
        self._lexicon = self.lexicon
        self.lexicon = Lexicon.objects.create(name="Temp Lexicon", src_language="99", dst_language="99")

        self.xlsx = load_workbook(self.input_file, read_only=True)
        sheet = self.xlsx.active

        errors = []
        for i, row in enumerate(sheet.iter_rows()):
            if i == 0:
                continue

            row_number = i + 1
            wrow = self.validate_row(row, row_number)
            if not wrow.is_valid():
                errors.append({
                    "row": row_number,
                    "term": wrow.term,
                    "errors": wrow.errors,
                })
                continue

            word = Word(
                lexicon=self.lexicon,
                term=wrow.term,
                etimol=wrow.etimol,
            )
            word.save()
            entries = [Entry(word=word, translation=wrow.definition)]
            if wrow.definition2:
                entries.append(Entry(word=word, translation=wrow.definition2))
            word.entries.bulk_create(entries)

            # TODO: think how to handle too many errors
            if len(errors) >= 100:
                break

        if errors:
            self.lexicon.delete()
            self.print_errors(errors, format="json")
        else:
            self.lexicon.words.update(lexicon=self._lexicon)
            self.lexicon.delete()
            self.lexicon = self._lexicon

    def validate_row(self, row, row_number):
        instance = Row(row, row_number)
        instance.is_valid()
        return instance

    def print_errors(self, errors, format="json"):
        for error in errors:
            if format == "json":
                for key, value in error["errors"].items():
                    self.stdout.write(self.style.ERROR(
                        json.dumps({
                            "word": f"#{error['row']}: {error['term']}",
                            "column": key,
                            "message": value,
                        })
                    ))

                continue

            # extended output
            self.stdout.write(self.style.ERROR(f"Row: {error['row']}"))
            self.stdout.write(self.style.ERROR(f"Term: {error['term']}"))
            for key, value in error["errors"].items():
                self.stdout.write(self.style.ERROR(f"  * {key}: {value}"))
            self.stdout.write("\n")


class Row:
    def __init__(self, row, row_number):
        self.term = row[0].value
        self.url = row[1].value
        self.etimol = row[2].value or ""
        self.definition = row[3].value
        self.definition2 = row[4].value
        self.row_number = row_number

    def is_valid(self):
        self.errors = {}
        if not self.term:
            self.errors["term"] = "Term is required"
        if not self.definition:
            self.errors["definition"] = "Definition is required"

        self.validate_unique()

        return False if self.errors else True

    def validate_unique(self):
        if Word.objects.filter(term=self.term).exists():
            self.errors["term"] = "This term already exists"
            return False
        return True

import os
import unittest
from io import StringIO
import filecmp
import tempfile
import csv
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from linguatec_lexicon.models import (DiatopicVariation, Entry, Example,
                                      GramaticalCategory, Lexicon, Region,
                                      VerbalConjugation, Word)

class ExporterDataTestCase(TestCase):
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
        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/gramcat-es-ar.csv')
        call_command('importgramcat', sample_path, verbosity=0)

    def test_export_data(self):
        

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/sample-input.xlsx')
        call_command('importdata', sample_path, self.LEXICON_NAME)


        with tempfile.TemporaryDirectory() as tmpdirname:
            call_command('exportdata', self.LEXICON_CODE, tmpdirname + '/test-output-data-file.csv')
            sample_path = os.path.join(base_path, 'fixtures/export_test_files/export_data_expected_result.csv')

            result=[]
            with open(sample_path) as resultfile:
                reader = csv.reader(resultfile, delimiter=';')
                for i, row in enumerate(reader):
                    result.insert(i,row)
            with open(tmpdirname + '/test-output-data-file.csv') as outfile:
                reader = csv.reader(outfile, delimiter=';')
                for i, row in enumerate(reader):
    
                    self.assertEqual(result[i],row)



class ExporterVariationTestCase(TestCase):

    LEXICON_CODE = 'es-ar'

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
        sample_path = cls.get_fixture_path('gramcat-es-ar.csv')
        call_command('importgramcat', sample_path, verbosity=0)

        # initialize words on main language
        sample_path = cls.get_fixture_path('variation-sample-common.xlsx')
        call_command('importdata', sample_path, lexicon.name)

    def test_export_variation(self):
        

        base_path = os.path.dirname(os.path.abspath(__file__))
        sample_path = os.path.join(base_path, 'fixtures/variation-sample-benasques.xlsx')
        call_command('importvariation', sample_path, self.LEXICON_CODE, variation='benasqués')

        with tempfile.TemporaryDirectory() as tmpdirname:
            call_command('exportvariation', self.LEXICON_CODE, 'benasqués',tmpdirname + '/test-output-data-file.csv')
            sample_path = os.path.join(base_path, 'fixtures/export_test_files/export_variation_expected_result.csv')

            result=[]
            with open(sample_path) as resultfile:
                reader = csv.reader(resultfile, delimiter=';')
                for i, row in enumerate(reader):
                    result.insert(i,row)

            with open(tmpdirname + '/test-output-data-file.csv') as outfile:
                reader = csv.reader(outfile, delimiter=';')
                for i, row in enumerate(reader):
                    for j in range(0,len(row)):
                        self.assertEqual(result[i][j],row[j])

from rest_framework import serializers

from .models import (DiatopicVariation, Entry, Example, GramaticalCategory,
                     Lexicon, VerbalConjugation, Word)


class ExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Example
        fields = ('phrase',)


class VerbalConjugationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerbalConjugation
        fields = ('intro', 'model', 'model_word',
                  'model_word_id', 'conjugation')


class GramaticalCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GramaticalCategory
        fields = ('abbreviation', 'title')


class DiatopicVariationSerializer(serializers.ModelSerializer):
    region = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = DiatopicVariation
        fields = ('name', 'abbreviation', 'region')


class EntrySerializer(serializers.ModelSerializer):
    gramcats = GramaticalCategorySerializer(many=True, read_only=True)
    labels = serializers.SlugRelatedField(slug_field='name', read_only=True, many=True)
    examples = ExampleSerializer(many=True, read_only=True)
    conjugation = VerbalConjugationSerializer()
    variation = DiatopicVariationSerializer()

    class Meta:
        model = Entry
        fields = ('id', 'variation', 'gramcats', 'translation', 'marked_translation',
                  'labels', 'examples', 'conjugation')


class WordSerializer(serializers.ModelSerializer):
    lexicon = serializers.SlugRelatedField(slug_field='slug', read_only=True)
    entries = EntrySerializer(many=True, read_only=True)
    gramcats = serializers.ListField(read_only=True)

    class Meta:
        model = Word
        fields = ('id', 'slug', 'url', 'lexicon', 'term', 'etimol', 'gramcats', 'entries', 'admin_panel_url')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context['request'].user
        if not (user.is_authenticated and user.is_staff):
            self.fields.pop('admin_panel_url')


class WordNearSerializer(serializers.ModelSerializer):
    class Meta:
        model = Word
        fields = ('id', 'slug', 'url', 'term')


class LexiconSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lexicon
        fields = ('id', 'code', 'name', 'src_language', 'dst_language', 'topic', 'slug')

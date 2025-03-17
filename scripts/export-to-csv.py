import csv
from django.utils.timezone import now

from linguatec_lexicon.models import Lexicon


def dump_lexicon_to_csv(slug):
    today = now().strftime("%Y-%m-%d")
    header = ['id', "slug", 'term']
    lexicon = Lexicon.objects.get_by_slug(slug)
    data = lexicon.words.values(*header)
    filename = f"terms-{lexicon.slug}-{today}.csv"
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


dump_lexicon_to_csv("ar-es")
dump_lexicon_to_csv("es-ar")

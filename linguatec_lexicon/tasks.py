# from django_q.tasks import async_task

# async_task("dgames.tasks.notify_new_reward_to_make", reward.id)
from io import StringIO

from django.core.management import call_command

from linguatec_lexicon.models import Lexicon


def validate_mono(lexicon_slug, xlsx_file):
    out = StringIO()
    call_command('importmono', lexicon_slug, xlsx_file, no_color=True, verbosity=3, stdout=out, stderr=out)
    return out

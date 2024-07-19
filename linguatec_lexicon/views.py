import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django_q.tasks import async_task, result
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from linguatec_lexicon import tasks

from .forms import ValidatorForm
from .models import GramaticalCategory, Lexicon, Word
from .serializers import (GramaticalCategorySerializer, LexiconSerializer,
                          WordNearSerializer, WordSerializer)
from .validators import validate_lexicon_slug


class DataValidatorView(TemplateView):
    template_name = "linguatec_lexicon/datavalidator.html"
    title = "Data validator"

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        form = ValidatorForm(request.POST, request.FILES)

        if form.is_valid():
            xlsx_file = form.cleaned_data['input_file']

            # store uploaded file as a temporal file
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.xlsx')
            f = os.fdopen(tmp_fd, 'wb')  # open the tmp file for writing
            f.write(xlsx_file.read())  # write the tmp file
            f.close()

            # validate uploaded file and handle errors (if any)
            out = self.validate(tmp_file)
            errors = []
            for line in out.getvalue().split('\n'):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                errors.append(data)

            context.update({
                'errors': errors,
                'input_file': xlsx_file,
            })
            return self.render_to_response(context)

        context['form'] = form
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form':  ValidatorForm(),
            'title': self.title,
        })
        return context

    def validate(self, xlsx_file):
        out = StringIO()
        # TODO(@slamora) lexicon paramenter is required since multilexicon support is added
        default_lexicon = 'es-ar'   # TODO XXX XXX
        call_command('importdata', default_lexicon, xlsx_file, dry_run=True, no_color=True, verbosity=3, stdout=out)
        return out


class DiatopicVariationValidatorView(DataValidatorView):
    title = "Diatopic variation validator"

    def validate(self, xlsx_file):
        out = StringIO()
        call_command('importvariation', xlsx_file, dry_run=True, no_color=True, verbosity=3, stdout=out)
        return out


class MonoValidatorView(FormView):
    title = "Monolingual validator"
    lexicon = 'an-an'
    form_class = ValidatorForm
    template_name = "linguatec_lexicon/datavalidator.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title,
        })
        return context

    def form_valid(self, form):
        print("H")

        xlsx_file = form.cleaned_data['input_file']

        # store uploaded file as a temporal file
        tmp_fd, tmp_file = tempfile.mkstemp(suffix='.xlsx')
        with open(tmp_file, 'wb') as f:
            f.write(xlsx_file.read())

        # run the validation async

        task_id = async_task(tasks.validate_mono, self.lexicon, tmp_file)

        self.task_id = task_id

        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("task-detail", kwargs={"task_id": self.task_id})


class TaskDetailView(TemplateView):
    template_name = "linguatec_lexicon/task-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        task_id = kwargs.get('task_id')
        task_result = result(task_id)
        data = []

        # NOTE: when the task has not yet be run, r is None
        # NOTE: we don't have way to differentiate between a task that has not been run and non existing task
        if task_result is not None:
            content = task_result.getvalue()
            for line in content.split('\n'):
                if line == '':
                    continue

                line = json.loads(line)
                data.append(line)

        context.update({
            'task_id': task_id,
            'task_result': data,
            'task_finished': task_result is not None,
        })

        return context


class DefaultLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 30
    max_limit = 100


class LexiconViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows lexicons to be viewed.
    """
    queryset = Lexicon.objects.all().order_by('src_language', 'dst_language')
    serializer_class = LexiconSerializer
    pagination_class = DefaultLimitOffsetPagination


class WordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows words to be viewed.
    """
    queryset = Word.objects.all().order_by('term')
    serializer_class = WordSerializer
    pagination_class = DefaultLimitOffsetPagination

    @action(detail=False)
    def near(self, request):
        self.serializer_class = WordNearSerializer
        query = self.request.query_params.get('q', None)
        lex = self.request.query_params.get('l', '')
        lex = lex.strip()
        queryset = Word.objects.search_near(query, lex)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def search(self, request):
        query = self.request.query_params.get('q', None)
        lex = self.request.query_params.get('l', '')
        if query is not None:
            query = query.strip()
        lex = lex.strip()
        queryset = Word.objects.search(query, lex)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def exact(self, request):
        lex = self.request.query_params.get('l', '')
        term = self.request.query_params.get('q')

        try:
            validate_lexicon_slug(lex)
        except ValueError as e:
            return Response(
                data={"code": 400, "message": "Bad Requset", "details": str(e)},
                status=400,
            )

        try:
            lexicon = Lexicon.objects.get_by_slug(lex)
            instance = lexicon.words.get(term=term)
        except (Lexicon.DoesNotExist, Word.DoesNotExist):
            raise Http404()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class WordDetailBySlug(generics.RetrieveAPIView):
    queryset = Word.objects.all()
    lookup_field = 'slug'
    serializer_class = WordSerializer


class GramaticalCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows words to be retrieved.
    """
    queryset = GramaticalCategory.objects.all().order_by('abbreviation')
    serializer_class = GramaticalCategorySerializer
    pagination_class = DefaultLimitOffsetPagination

    @action(detail=False, )
    def show(self, request):
        abbr = self.request.query_params.get('abbr', None)

        gramcat = get_object_or_404(self.queryset, abbreviation=abbr)

        serializer = self.get_serializer(gramcat)
        return Response(serializer.data)

from django.urls import include, path
from rest_framework import routers

from . import views

# Wire up our API using automatic URL routing.
router = routers.DefaultRouter()
router.register(r'lexicons', views.LexiconViewSet)
router.register(r'words', views.WordViewSet)
router.register(r'gramcats', views.GramaticalCategoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('words/slug/<str:slug>/', views.WordDetailBySlug.as_view(), name='word-detail-by-slug'),
    path('validator/', views.DataValidatorView.as_view(), name='validator'),
    path('validator-diatopic-variation/', views.DiatopicVariationValidatorView.as_view(), name='validator-variation'),
    path('validator-mono/', views.MonoValidatorView.as_view(), name='validator-mono'),
    path('tasks/<str:task_id>/', views.TaskDetailView.as_view(), name='task-detail'),
]

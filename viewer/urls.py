from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/upload/', views.upload_drawing, name='upload_drawing'),
    path('api/drawing/<uuid:drawing_id>/', views.get_drawing_data, name='get_drawing_data'),
    path('api/drawing/<uuid:drawing_id>/calibrate/', views.calibrate_scale, name='calibrate_scale'),
    path('api/drawing/<uuid:drawing_id>/add-component/', views.add_manual_component, name='add_manual_component'),
    path('api/sample/<str:sample_type>/', views.load_sample, name='load_sample'),
    path('api/drawings/', views.list_drawings, name='list_drawings'),
]

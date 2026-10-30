from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Projects
    path('projects/', views.projects_list_view, name='projects_list'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('projects/<int:project_id>/delete/', views.project_delete_view, name='project_delete'),
    
    # Inspections & Gallery
    path('inspections/', views.inspections_list_view, name='inspections_list'),
    path('inspections/new/', views.inspection_create_view, name='inspection_create'),
    path('inspections/<int:inspection_id>/', views.inspection_detail_view, name='inspection_detail'),
    path('inspections/<int:inspection_id>/delete/', views.inspection_delete_view, name='inspection_delete'),
    path('gallery/', views.defects_gallery_view, name='defects_gallery'),
    
    # APIs
    path('api/inspections/<int:inspection_id>/status/', views.inspection_update_status_api, name='api_inspection_status'),
    path('api/inspections/<int:inspection_id>/overlay/', views.inspection_update_overlay_api, name='api_inspection_overlay'),
    path('api/milestones/<int:status_id>/update/', views.api_room_milestone_update, name='api_room_milestone_update'),
    path('api/floors/<int:floor_id>/rooms/', views.api_floor_rooms, name='api_floor_rooms'),
    path('api/projects/<int:project_id>/floors/', views.api_project_floors, name='api_project_floors'),
    path('api/floors/preview/', views.api_floor_preview, name='api_floor_preview'),

    # Floor & Apartment Management (Dynamic Unit Generation)
    path('projects/<int:project_id>/floors/new/', views.floor_create_view, name='floor_create'),
    path('floors/<int:floor_id>/edit/', views.floor_edit_view, name='floor_edit'),
    path('floors/<int:floor_id>/delete/', views.floor_delete_view, name='floor_delete'),
    path('floors/<int:floor_id>/common-areas/add/', views.add_common_areas_view, name='add_common_areas'),
    path('floors/<int:floor_id>/rooms/new/', views.room_create_view, name='room_create'),
    path('rooms/<int:room_id>/statuses/', views.room_status_detail_view, name='room_status_detail'),
    path('rooms/<int:room_id>/edit/', views.room_edit_view, name='room_edit'),
    path('rooms/<int:room_id>/delete/', views.room_delete_view, name='room_delete'),
    path('milestones/new/', views.milestone_create_view, name='milestone_create'),

    # Room Status APIs
    path('api/rooms/<int:room_id>/statuses/', views.api_room_statuses, name='api_room_statuses'),
    path('api/rooms/<int:room_id>/bulk-status/', views.api_room_bulk_status, name='api_room_bulk_status'),

    # Demo Seed
    path('seed-demo-data/', views.seed_demo_data_view, name='seed_demo_data'),
]

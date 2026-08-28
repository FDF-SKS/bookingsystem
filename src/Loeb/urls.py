from django.urls import path, include
from rest_framework import routers

from . import api, views

router = routers.DefaultRouter()
router.register('Loeb', api.LoebViewSet)
router.register('PhysicalStation', api.PhysicalStationViewSet)
router.register('Task', api.TaskViewSet)
router.register('Hold', api.HoldViewSet)
router.register('TaskSubmission', api.TaskSubmissionViewSet)

urlpatterns = [
    path('api/v1/', include(router.urls)),

    path('Loeb/', views.LoebListView.as_view(), name='Loeb_Loeb_list'),
    path('Loeb/create/', views.LoebCreateView.as_view(), name='Loeb_Loeb_create'),
    path('Loeb/detail/<int:pk>/', views.LoebDetailView.as_view(), name='Loeb_Loeb_detail'),
    path('Loeb/update/<int:pk>/', views.LoebUpdateView.as_view(), name='Loeb_Loeb_update'),
    path('Loeb/delete/<int:pk>/', views.LoebDeleteView.as_view(), name='Loeb_Loeb_delete'),

    path('PhysicalStation/', views.PhysicalStationListView.as_view(), name='Loeb_PhysicalStation_list'),
    path('PhysicalStation/create/', views.PhysicalStationCreateView.as_view(), name='Loeb_PhysicalStation_create'),
    path('PhysicalStation/detail/<int:pk>/', views.PhysicalStationDetailView.as_view(), name='Loeb_PhysicalStation_detail'),
    path('PhysicalStation/update/<int:pk>/', views.PhysicalStationUpdateView.as_view(), name='Loeb_PhysicalStation_update'),
    path('PhysicalStation/delete/<int:pk>/', views.PhysicalStationDeleteView.as_view(), name='Loeb_PhysicalStation_delete'),

    path('Task/', views.TaskListView.as_view(), name='Loeb_Task_list'),
    path('Task/create/', views.TaskCreateView.as_view(), name='Loeb_Task_create'),
    path('Task/detail/<int:pk>/', views.TaskDetailView.as_view(), name='Loeb_Task_detail'),
    path('Task/update/<int:pk>/', views.TaskUpdateView.as_view(), name='Loeb_Task_update'),
    path('Task/delete/<int:pk>/', views.TaskDeleteView.as_view(), name='Loeb_Task_delete'),
    path('Task/move-up/<int:pk>/', views.move_task_up, name='Loeb_Task_move_up'),
    path('Task/move-down/<int:pk>/', views.move_task_down, name='Loeb_Task_move_down'),

    path('Hold/', views.HoldListView.as_view(), name='Loeb_Hold_list'),
    path('Hold/create/', views.HoldCreateView.as_view(), name='Loeb_Hold_create'),
    path('Hold/detail/<int:pk>/', views.HoldDetailView.as_view(), name='Loeb_Hold_detail'),
    path('Hold/update/<int:pk>/', views.HoldUpdateView.as_view(), name='Loeb_Hold_update'),
    path('Hold/delete/<int:pk>/', views.HoldDeleteView.as_view(), name='Loeb_Hold_delete'),
    path('Station/<str:qr_code>/', views.station_qr, name='Loeb_Station_qr'),
    path('Loeb/<int:loeb_pk>/hold-login/', views.hold_login, name='Loeb_Hold_login'),
    path('Loeb/<int:loeb_pk>/hold-dashboard/', views.hold_dashboard, name='Loeb_Hold_dashboard'),
    path('Loeb/<int:loeb_pk>/hold-logout/', views.hold_logout, name='Loeb_Hold_logout'),

    path('TaskSubmission/', views.TaskSubmissionListView.as_view(), name='Loeb_TaskSubmission_list'),
    path('TaskSubmission/create/', views.TaskSubmissionCreateView.as_view(), name='Loeb_TaskSubmission_create'),
    path('TaskSubmission/detail/<int:pk>/', views.TaskSubmissionDetailView.as_view(), name='Loeb_TaskSubmission_detail'),
    path('TaskSubmission/update/<int:pk>/', views.TaskSubmissionUpdateView.as_view(), name='Loeb_TaskSubmission_update'),
    path('TaskSubmission/delete/<int:pk>/', views.TaskSubmissionDeleteView.as_view(), name='Loeb_TaskSubmission_delete'),
]

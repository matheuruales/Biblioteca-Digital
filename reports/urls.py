from django.urls import path

from .views import DashboardSummaryView, ExportReportView, ReportsView


urlpatterns = [
    path('dashboard/', DashboardSummaryView.as_view(), name='dashboard_summary'),
    path('reports/', ReportsView.as_view(), name='reports'),
    path('reports/export/<str:file_format>/', ExportReportView.as_view(), name='reports_export'),
]

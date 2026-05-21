from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsLibrarian

from .services import (
    REPORT_LABELS,
    all_reports,
    dashboard_summary,
    render_csv,
    render_pdf,
    report_rows,
)


class DashboardSummaryView(APIView):
    permission_classes = (IsLibrarian,)

    def get(self, request):
        return Response(dashboard_summary(), status=status.HTTP_200_OK)


class ReportsView(APIView):
    permission_classes = (IsLibrarian,)

    def get(self, request):
        limit = _positive_int(request.query_params.get('limit'), default=10, maximum=50)
        return Response(all_reports(limit), status=status.HTTP_200_OK)


class ExportReportView(APIView):
    permission_classes = (IsLibrarian,)

    def get(self, request, file_format):
        report_name = request.query_params.get('report', 'loans_by_month')
        if report_name not in REPORT_LABELS:
            return Response(
                {'detail': 'Reporte no soportado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit = _positive_int(request.query_params.get('limit'), default=50, maximum=500)
        rows = report_rows(report_name, limit)
        filename = f'{report_name}.{file_format}'

        if file_format == 'csv':
            response = HttpResponse(render_csv(report_name, rows), content_type='text/csv')
        elif file_format == 'pdf':
            response = HttpResponse(render_pdf(report_name, rows), content_type='application/pdf')
        else:
            return Response(
                {'detail': 'Formato no soportado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def admin_dashboard(request):
    return render(request, 'reports/admin_dashboard.html')


def _positive_int(value, default, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(number, maximum))

from django.urls import path

from . import views


app_name = 'library_web'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('lector/', views.reader_dashboard_view, name='reader_dashboard'),
    path('lector/libros/', views.ReaderBookListView.as_view(), name='reader_book_list'),
    path('lector/reservas/', views.ReaderReservationListView.as_view(), name='reader_reservation_list'),
    path('lector/reservas/nueva/', views.ReservationCreateView.as_view(), name='reader_reservation_create'),
    path('lector/reservas/<int:pk>/cancelar/', views.cancel_reservation_view, name='reader_reservation_cancel'),
    path('lector/prestamos/', views.ReaderLoanListView.as_view(), name='reader_loan_list'),
    path('lector/sanciones/', views.ReaderSanctionListView.as_view(), name='reader_sanction_list'),

    path('bibliotecario/', views.librarian_dashboard_view, name='librarian_dashboard'),
    path('bibliotecario/reportes/', views.librarian_reports_view, name='report_list'),
    path('bibliotecario/reportes/export/<str:file_format>/', views.export_report_view, name='export_report'),
    path('bibliotecario/usuarios/', views.UserListView.as_view(), name='user_list'),
    path('bibliotecario/usuarios/nuevo/', views.UserCreateView.as_view(), name='user_create'),
    path('bibliotecario/usuarios/<int:pk>/editar/', views.UserUpdateView.as_view(), name='user_update'),
    path('bibliotecario/usuarios/<int:pk>/eliminar/', views.UserDeleteView.as_view(), name='user_delete'),
    path('bibliotecario/autores/', views.LibrarianAuthorListView.as_view(), name='author_list'),
    path('bibliotecario/autores/nuevo/', views.AuthorCreateView.as_view(), name='author_create'),
    path('bibliotecario/autores/<int:pk>/editar/', views.AuthorUpdateView.as_view(), name='author_update'),
    path('bibliotecario/autores/<int:pk>/eliminar/', views.AuthorDeleteView.as_view(), name='author_delete'),
    path('bibliotecario/categorias/', views.LibrarianCategoryListView.as_view(), name='category_list'),
    path('bibliotecario/categorias/nueva/', views.CategoryCreateView.as_view(), name='category_create'),
    path('bibliotecario/categorias/<int:pk>/editar/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('bibliotecario/categorias/<int:pk>/eliminar/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('bibliotecario/libros/', views.LibrarianBookListView.as_view(), name='book_list'),
    path('bibliotecario/libros/nuevo/', views.BookCreateView.as_view(), name='book_create'),
    path('bibliotecario/libros/<int:pk>/editar/', views.BookUpdateView.as_view(), name='book_update'),
    path('bibliotecario/libros/<int:pk>/eliminar/', views.BookDeleteView.as_view(), name='book_delete'),
    path('bibliotecario/reservas/', views.LibrarianReservationListView.as_view(), name='reservation_list'),
    path('bibliotecario/reservas/nueva/', views.ReservationCreateView.as_view(), name='reservation_create'),
    path('bibliotecario/reservas/<int:pk>/cancelar/', views.cancel_reservation_view, name='reservation_cancel'),
    path('bibliotecario/prestamos/', views.LibrarianLoanListView.as_view(), name='loan_list'),
    path('bibliotecario/prestamos/nuevo/', views.LoanCreateView.as_view(), name='loan_create'),
    path('bibliotecario/prestamos/<int:pk>/devolver/', views.return_loan_view, name='loan_return'),
    path('bibliotecario/sanciones/', views.LibrarianSanctionListView.as_view(), name='sanction_list'),
]

# Biblioteca Digital - Matheu

Backend Django REST para autenticacion, usuarios, catalogo de libros y busqueda avanzada.

## Alcance

Esta entrega cubre la parte de Matheu:

- Registro e inicio de sesion con JWT.
- Recuperacion de contrasena por correo en consola.
- Roles de usuario: lector y bibliotecario.
- Estados de usuario: activo y bloqueado.
- CRUD de usuarios.
- CRUD de autores, categorias y libros.
- Busqueda avanzada y filtros de libros.

La parte de reportes, graficos, CSV, PDF y dashboard administrativo queda cubierta en la seccion de Dev 3.

## Préstamos, Reservas y Sanciones (Dev 2)

### Endpoints

- `GET /api/reservations/` (lector: propias / bibliotecario: todas)
- `POST /api/reservations/` `{ "book_id": <id> }`
- `POST /api/reservations/{id}/cancel/`
- `GET /api/loans/` (lector: propios / bibliotecario: todos)
- `POST /api/loans/` (solo bibliotecario) `{ "book_id": <id>, "user_id": <id>, "due_at": "2026-05-19T10:00:00Z" }`
- `POST /api/loans/{id}/return/` (solo bibliotecario)
- `GET /api/sanctions/` (lector: propias / bibliotecario: todas)
- `GET /api/books/{book_id}/state/` estado agregado del libro (`disponible`, `reservado`, `prestado`, `retrasado`)

### Tarea automática de correos / sanciones

Ejecuta mantenimiento de circulación (expira reservas, marca vencidos, genera sanciones y envía correos de vencimiento/retraso):

```bash
python manage.py circulation_maintenance
```

## Instalacion

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

## Endpoints De Autenticacion

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset-confirm/`

## Endpoints De Usuarios

- `GET /api/users/me/`
- `GET /api/users/`
- `POST /api/users/`
- `GET /api/users/{id}/`
- `PATCH /api/users/{id}/`
- `DELETE /api/users/{id}/`

## Endpoints De Catalogo

- `GET /api/authors/`
- `POST /api/authors/`
- `GET /api/authors/{id}/`
- `PATCH /api/authors/{id}/`
- `DELETE /api/authors/{id}/`
- `GET /api/categories/`
- `POST /api/categories/`
- `GET /api/categories/{id}/`
- `PATCH /api/categories/{id}/`
- `DELETE /api/categories/{id}/`
- `GET /api/books/`
- `POST /api/books/`
- `GET /api/books/{id}/`
- `PATCH /api/books/{id}/`
- `DELETE /api/books/{id}/`

## Filtros De Libros

`GET /api/books/` acepta estos parametros:

- `search`: busca por titulo, ISBN, autor o categoria.
- `title`: filtra por nombre del libro.
- `author`: filtra por ID de autor.
- `category`: filtra por ID de categoria.
- `availability`: acepta `available` o `unavailable`.

Ejemplo:

```bash
curl "http://127.0.0.1:8000/api/books/?search=garcia&availability=available"
```

## Pruebas

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

## Dashboard, Reportes y Exportaciones (Dev 3)

### Frontend administrativo

- `GET /admin-dashboard/`

La pantalla administrativa consume las APIs de reportes con un token JWT de bibliotecario, muestra metricas generales, alertas operativas, graficos, tablas y acciones de exportacion.

### Endpoints

- `GET /api/dashboard/` resumen administrativo: libros, usuarios, prestamos, reservas, sanciones, inventario y alertas.
- `GET /api/reports/` reportes agregados: libros mas reservados, autores mas leidos, prestamos por mes y usuarios con mas prestamos.
- `GET /api/reports/export/csv/?report=loans_by_month`
- `GET /api/reports/export/pdf/?report=loans_by_month`

Reportes soportados para exportacion:

- `most_reserved_books`
- `most_read_authors`
- `loans_by_month`
- `top_users_by_loans`

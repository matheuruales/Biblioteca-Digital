# Biblioteca Digital - Matheu

Aplicacion web Django para gestion de biblioteca digital con autenticacion, roles, CRUD, prestamos, reservas, sanciones, dashboard, graficos y exportaciones.

## Alcance

El sistema incluye:

- Registro, inicio de sesion y cierre de sesion web.
- Autenticacion API con JWT.
- Recuperacion de contrasena por correo en consola.
- Roles de usuario: lector y bibliotecario.
- Estados de usuario: activo y bloqueado.
- CRUD web y API de usuarios.
- CRUD de autores, categorias y libros.
- Reservas, prestamos, devoluciones y sanciones por retraso.
- Busqueda avanzada y filtros de libros.
- Dashboard con graficos dinamicos.
- Reportes y exportacion CSV/PDF.
- Conexion PostgreSQL/Supabase mediante `DATABASE_URL`.

## Rutas Web Principales

- `/` redirige a login o a la interfaz correcta segun rol.
- `/login/` inicio de sesion.
- `/register/` registro de lectores.
- `/logout/` cierre de sesion.
- `/lector/` portal lector.
- `/lector/libros/` catalogo y busqueda.
- `/lector/reservas/` reservas del lector.
- `/lector/prestamos/` prestamos del lector.
- `/lector/sanciones/` sanciones del lector.
- `/bibliotecario/` dashboard administrativo con graficos.
- `/bibliotecario/libros/` CRUD y busqueda de libros.
- `/bibliotecario/autores/` CRUD de autores.
- `/bibliotecario/categorias/` CRUD de categorias.
- `/bibliotecario/usuarios/` CRUD de usuarios.
- `/bibliotecario/reservas/` gestion de reservas.
- `/bibliotecario/prestamos/` gestion de prestamos.
- `/bibliotecario/sanciones/` consulta de sanciones.
- `/bibliotecario/reportes/` reportes y exportaciones.

## Credenciales De Prueba

```text
Bibliotecario
usuario: matheu_admin
password: Biblioteca2026!
```

```text
Lector
usuario: matheu_lector
password: Biblioteca2026!
```

Para recrearlas:

```bash
.venv/bin/python manage.py create_test_users
```

Para crear libros, autores, categorias, reservas, prestamos y sanciones de demostracion:

```bash
.venv/bin/python manage.py seed_demo_data
```

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
.venv/bin/python manage.py create_test_users
.venv/bin/python manage.py seed_demo_data
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Si existe `.env` con `DATABASE_URL`, Django usa Supabase/PostgreSQL. Si no existe, usa `db.sqlite3`.

## Despliegue En Vercel

La app esta preparada para Vercel con:

- `api/index.py` como entrada WSGI.
- `vercel.json` con rewrite global hacia Django.
- `pyproject.toml` con Python 3.12 y dependencias.
- WhiteNoise para servir archivos estaticos.

Variables necesarias en Vercel Production:

- `DATABASE_URL`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_DB_PASSWORD`

Deploy:

```bash
vercel --prod --yes
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

## Dashboard, Reportes y Exportaciones

### Frontend administrativo web

- `GET /bibliotecario/`
- `GET /bibliotecario/reportes/`
- `GET /admin-dashboard/` redirige a `/bibliotecario/`

La pantalla administrativa usa sesion Django, muestra metricas generales, alertas operativas, graficos, tablas y acciones de exportacion. El lector tiene una interfaz separada en `/lector/` y no ve navegacion administrativa.

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

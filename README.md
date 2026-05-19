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

No incluye prestamos, reservas, sanciones, reportes, graficos, CSV ni PDF.

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

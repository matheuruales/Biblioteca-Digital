from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Author, Book, Category


User = get_user_model()


class CatalogApiTests(APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password='StrongPass123!',
        )
        self.librarian = User.objects.create_user(
            username='librarian',
            email='librarian@example.com',
            password='StrongPass123!',
            role=User.ROLE_LIBRARIAN,
        )
        self.author = Author.objects.create(name='Gabriel Garcia Marquez')
        self.category = Category.objects.create(name='Novela')

    def test_reader_can_list_but_not_create_catalog(self):
        self.client.force_authenticate(self.reader)

        list_response = self.client.get('/api/authors/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            '/api/authors/',
            {'name': 'Isabel Allende'},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_user_cannot_read_catalog(self):
        response = self.client.get('/api/books/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_librarian_can_create_update_and_delete_book(self):
        self.client.force_authenticate(self.librarian)

        create_response = self.client.post(
            '/api/books/',
            {
                'title': 'Cien anos de soledad',
                'isbn': '9780307474728',
                'description': 'Novela latinoamericana.',
                'author_ids': [self.author.id],
                'category_ids': [self.category.id],
                'total_copies': 3,
                'available_copies': 2,
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['availability'], 'available')

        book_id = create_response.data['id']
        patch_response = self.client.patch(
            f'/api/books/{book_id}/',
            {'available_copies': 0},
            format='json',
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['availability'], 'unavailable')

        delete_response = self.client.delete(f'/api/books/{book_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_book_validates_copies_and_unique_isbn(self):
        self.client.force_authenticate(self.librarian)

        invalid_response = self.client.post(
            '/api/books/',
            {
                'title': 'Libro invalido',
                'isbn': '111',
                'author_ids': [self.author.id],
                'category_ids': [self.category.id],
                'total_copies': 1,
                'available_copies': 2,
            },
            format='json',
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

        first_response = self.client.post(
            '/api/books/',
            {
                'title': 'Libro valido',
                'isbn': '222',
                'author_ids': [self.author.id],
                'category_ids': [self.category.id],
                'total_copies': 1,
                'available_copies': 1,
            },
            format='json',
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            '/api/books/',
            {
                'title': 'Libro duplicado',
                'isbn': '222',
                'author_ids': [self.author.id],
                'category_ids': [self.category.id],
                'total_copies': 1,
                'available_copies': 1,
            },
            format='json',
        )
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_book_filters_by_author_category_availability_title_and_search(self):
        other_author = Author.objects.create(name='Julio Cortazar')
        other_category = Category.objects.create(name='Cuento')
        available_book = Book.objects.create(
            title='Rayuela',
            isbn='333',
            total_copies=2,
            available_copies=1,
        )
        available_book.authors.add(other_author)
        available_book.categories.add(other_category)

        unavailable_book = Book.objects.create(
            title='El coronel no tiene quien le escriba',
            isbn='444',
            total_copies=1,
            available_copies=0,
        )
        unavailable_book.authors.add(self.author)
        unavailable_book.categories.add(self.category)

        self.client.force_authenticate(self.reader)

        author_response = self.client.get(f'/api/books/?author={other_author.id}')
        self.assertEqual(len(author_response.data), 1)
        self.assertEqual(author_response.data[0]['title'], 'Rayuela')

        category_response = self.client.get(f'/api/books/?category={self.category.id}')
        self.assertEqual(len(category_response.data), 1)
        self.assertEqual(category_response.data[0]['isbn'], '444')

        availability_response = self.client.get('/api/books/?availability=available')
        self.assertEqual(len(availability_response.data), 1)
        self.assertEqual(availability_response.data[0]['isbn'], '333')

        title_response = self.client.get('/api/books/?title=coronel')
        self.assertEqual(len(title_response.data), 1)
        self.assertEqual(title_response.data[0]['isbn'], '444')

        search_response = self.client.get('/api/books/?search=Cortazar')
        self.assertEqual(len(search_response.data), 1)
        self.assertEqual(search_response.data[0]['title'], 'Rayuela')

from rest_framework import serializers

from .models import Author, Book, Category


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = (
            'id',
            'name',
            'biography',
            'birth_date',
            'death_date',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'created_at', 'updated_at')
        read_only_fields = ('id', 'slug', 'created_at', 'updated_at')


class BookSerializer(serializers.ModelSerializer):
    authors = AuthorSerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    author_ids = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(),
        many=True,
        source='authors',
        write_only=True,
        required=False,
    )
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        source='categories',
        write_only=True,
        required=False,
    )
    availability = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = (
            'id',
            'title',
            'isbn',
            'description',
            'publication_date',
            'authors',
            'categories',
            'author_ids',
            'category_ids',
            'total_copies',
            'available_copies',
            'availability',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'availability', 'created_at', 'updated_at')

    def get_availability(self, obj):
        return 'available' if obj.is_available else 'unavailable'

    def validate(self, attrs):
        total_copies = attrs.get(
            'total_copies',
            self.instance.total_copies if self.instance else 1,
        )
        available_copies = attrs.get(
            'available_copies',
            self.instance.available_copies if self.instance else 1,
        )

        if total_copies < 0:
            raise serializers.ValidationError(
                {'total_copies': 'El total de copias no puede ser negativo.'}
            )

        if available_copies < 0:
            raise serializers.ValidationError(
                {'available_copies': 'Las copias disponibles no pueden ser negativas.'}
            )

        if available_copies > total_copies:
            raise serializers.ValidationError(
                {'available_copies': 'Las copias disponibles no pueden superar el total.'}
            )

        return attrs

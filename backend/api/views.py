import csv

from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from recipes.models import (Favorite, Ingredient, IngredientRecipe, 
                            Recipe, ShoppingCart, Tag)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from users.models import Subscribe, User

from .filters import IngredientFilter, RecipeFilter
from .mixins import RetrieveListViewSet
from .permissions import IsAuthorAdminOrReadOnly
from .serializers import (CustomUserSerializer, FavoriteSerializer,
                          IngredientSerializer, PasswordSerializer,
                          RecipeCreateSerializer, RecipeListSerializer,
                          ShoppingCartSerializer, SubscribeSerializer,
                          TagSerializer)

from .utils import get_shopping_cart


class CustomUserViewSet(UserViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer

    @action(detail=False,
            methods=['get'],
            permission_classes=(IsAuthenticated, ))
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(following__user=user)
        if queryset:
            pages = self.paginate_queryset(queryset)
            serializer = SubscribeSerializer(
                pages,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        return Response('Вы ни на кого не подписаны.',
                        status=status.HTTP_400_BAD_REQUEST)

    @action(
        methods=['get', 'delete'],
        detail=True,
        permission_classes=(IsAuthenticated, )
    )
    def subscribe(self, request, id):
        user = self.request.user
        author = get_object_or_404(User, id=id)
        subscribe = Subscribe.objects.filter(user=user, author=author)
        if user.is_anonymous:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        if request.method == 'GET':
            if subscribe.exists():
                data = {
                    'errors': ('Вы подписаны на этого автора, '
                               'или пытаетесь подписаться на себя.')}
                return Response(data=data, status=status.HTTP_400_BAD_REQUEST)
            Subscribe.objects.create(user=user, author=author)
            serializer = SubscribeSerializer(
                author,
                context={'request': request}
            )
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)
        if not subscribe.exists():
            data = {'errors': 'Вы не подписаны на данного автора.'}
            return Response(data=data, status=status.HTTP_400_BAD_REQUEST)
        subscribe.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagsViewSet(RetrieveListViewSet):
    queryset = Tag.objects.all()
    http_method_names = ["get"]
    serializer_class = TagSerializer
    permission_classes = (AllowAny, )
    pagination_class = None


class IngredientsViewSet(RetrieveListViewSet):
    queryset = Ingredient.objects.all()
    http_method_names = ["get"]
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny, )
    filter_backends = (DjangoFilterBackend, )
    filterset_class = IngredientFilter
    pagination_class = None


class RecipesViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    http_method_names = ["get", "post", "put", "delete"]
    serializer_class = RecipeListSerializer
    permission_classes = (IsAuthorAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend, )
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return RecipeListSerializer
        return RecipeCreateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def create_object(self, **pull_data):
        user = pull_data.get('request').user
        model =  pull_data.get('model')
        recipe = get_object_or_404(Recipe, pk=pull_data.get('pk'))
        get_data =model.objects.filter(
            user=user,
            recipe=recipe
        )
        if not get_data:
            data = model.objects.create(
                        user=user,
                        recipe=recipe
                    )
            serializer =  pull_data.get('serializers')(data.recipe)
            return Response(
                data=serializer.data,
                status=status.HTTP_201_CREATED
            )
        return Response(
                    data={'errors': f'Рецепт уже в {model.__name__}'},
                    status=status.HTTP_400_BAD_REQUEST
            )
    
    def delete_object(self, request, pk, model):
        user = request.user
        recipe = Recipe.objects.get(pk=pk) 
        del_data = get_object_or_404(model, user=user, recipe=recipe)
        del_data.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



    def _create_or_destroy(self, http_method, recipe, key, model, serializer):
        if http_method == 'GET':
            return self.create_object(request=recipe, pk=key, serializers=serializer, model=model)
        return self.delete_object(request=recipe, pk=key, model=model)
        

    @action(
        detail=True,
        methods=["get", "delete"],
        permission_classes=[IsAuthenticated, ],
    )
    def favorite(self, request, pk=None):
        return self._create_or_destroy(
            request.method, request, pk, Favorite, FavoriteSerializer
            )

    @action(
        detail=True,
        methods=["get", "delete"],
        permission_classes=[IsAuthenticated, ],
    )
    def shopping_cart(self, request, pk=None):
        return self._create_or_destroy(
            request.method, request, pk, ShoppingCart, ShoppingCartSerializer
            )

    @action(
        methods=['get'],
        detail=False,
        permission_classes=[IsAuthenticated, ],
    )
    def download_shopping_cart(self, request):
        """Скачать список покупок."""
        user = self.request.user
        if user.is_anonymous:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        ingredients = IngredientRecipe.objects.filter(
            recipe__shopping_cart__user=request.user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(ingredient_amount=Sum('amount')).values_list(
            'ingredient__name', 'ingredient__measurement_unit',
            'ingredient_amount')
        filename = 'shopping_cart.txt'
        data = '\n'.join([' '.join(map(str, list(ing))) for ing in ingredients])
        print(data)
        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = (f'attachment; filename={filename}')
        return response
 


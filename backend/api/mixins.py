from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

class RetrieveListViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    pass


class CreateDestroy:
    def create_object(self, **pull_data):
        user = pull_data.get('request').user
        model =  pull_data.get('model')
        search_model = pull_data.get('search_model')
        search_req = get_object_or_404(search_model, pk=pull_data.get('pk'))
        if search_model.__name__ == 'User':
            get_data = model.objects.filter(
                user=user,
                author=search_req
            )
            data_for_response = {'errors': 'Вы подписаны на этого автора,'
                                           'или пытаетесь подписаться на себя.'}
        else:
            get_data =model.objects.filter(
                user=user,
                recipe=search_req
            )
            data_for_response = {'errors': f'Рецепт уже в {model.__name__}'}

        if not get_data:
            if search_model.__name__ == 'User':
                data = model.objects.create(
                            author=search_req,
                            user=user
                                                    )
                serializer =  pull_data.get('serializers')(search_req, {'request': pull_data.get('request')})
                return Response(
                    data={'notification': f'Вы подписались на {search_req}'},
                    status=status.HTTP_201_CREATED
                )
            else:
                data = model.objects.create(
                            user=user,
                            recipe=search_req
                        )
                serializer =  pull_data.get('serializers')(data.recipe)
                return Response(
                    data=serializer.data,
                    status=status.HTTP_201_CREATED
                )
        return Response(
                    data=data_for_response,
                    status=status.HTTP_400_BAD_REQUEST
            )

    def delete_object(self, request, pk, model, search_model):
        user = request.user
        get_data = search_model.objects.get(pk=pk) 
        if search_model.__name__ == 'User':
            del_data = get_object_or_404(model, user=user, author=get_data)
        else:
            del_data = get_object_or_404(model, user=user, recipe=get_data)
        del_data.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _create_or_destroy(self, http_method, recipe, search_model, key, model, serializer):
        if http_method == 'GET':
            return self.create_object(request=recipe,
                                      pk=key,
                                      serializers=serializer,
                                      model=model,
                                      search_model=search_model)
        return self.delete_object(request=recipe,
                                  pk=key,
                                  model=model,
                                  search_model=search_model)
        

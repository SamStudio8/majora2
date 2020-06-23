from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from majora2 import models

class RestyArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraArtifact
        fields = ('id', 'dice_name', 'artifact_kind',)

class RestyBiosourceSamplingProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BiosourceSamplingProcess
        fields = (
                'collection_date',
                'received_date',
                'source_age',
                'source_sex',
                'collection_location_country',
                'collection_location_adm1',
                'collection_location_adm2',
                'private_collection_location_adm2',
        )
        extra_kwargs = {
                'private_collection_location_adm2': {'write_only': True},
        }
class RestyBiosampleArtifactSerializer(RestyArtifactSerializer):
    collection = RestyBiosourceSamplingProcessSerializer(source="created")
    class Meta:
        model = models.BiosampleArtifact
        fields = RestyArtifactSerializer.Meta.fields + (
                'central_sample_id',
                'sender_sample_id',
                'root_sample_id',
                'collection')
        extra_kwargs = {
                'root_sample_id': {'write_only': True},
                'sender_sample_id': {'write_only': True}
        }

   #def create(self, validated_data):
   #    modela_data = validated_data.pop('model_a')
   #    model_b = ModelB.objects.create(**validated_data)
   #    ModelA.objects.create(model_b=model_b, **modela_data)
   #    return model_b

class RestyArtifactSerializer(PolymorphicSerializer):
    resource_type_field_name = 'artifact_model'
    model_serializer_mapping = {
        models.MajoraArtifact: RestyArtifactSerializer,
        models.BiosampleArtifact: RestyBiosampleArtifactSerializer,
    }

class RestyPublishedArtifactGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PublishedArtifactGroup
        fields = ('id', 'published_name', 'published_date',)


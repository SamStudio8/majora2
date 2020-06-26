from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from majora2 import models

class BaseRestyProcessRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraArtifactProcessRecord

class BaseRestyProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraArtifactProcess
        fields = ('id', 'when', 'who', 'process_kind')
class RestyBiosourceSamplingProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BiosourceSamplingProcess
        fields = BaseRestyProcessSerializer.Meta.fields + (
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
class RestyProcessSerializer(PolymorphicSerializer):
    resource_type_field_name = 'process_model'
    model_serializer_mapping = {
        models.MajoraArtifactProcess: BaseRestyProcessSerializer,
        models.BiosourceSamplingProcess: RestyBiosourceSamplingProcessSerializer,
    }




class BaseRestyArtifactSerializer(serializers.ModelSerializer):
    created = RestyProcessSerializer()
    class Meta:
        model = models.MajoraArtifact
        fields = ('id', 'dice_name', 'artifact_kind', 'created')

class RestyGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraArtifactGroup
        fields = ('id', 'dice_name', 'group_kind', 'physical')


class RestyBiosampleSourceSerializer(serializers.ModelSerializer):
    created = RestyBiosourceSamplingProcessSerializer()
    class Meta:
        model = models.BiosampleSource
        fields = RestyGroupSerializer.Meta.fields + (
                'source_type',
                'secondary_id',
        )

class RestyBiosampleArtifactSerializer(BaseRestyArtifactSerializer):
    class Meta:
        model = models.BiosampleArtifact
        fields = BaseRestyArtifactSerializer.Meta.fields + (
                'central_sample_id',
                'sender_sample_id',
                'root_sample_id',
        )
        extra_kwargs = {
                'root_sample_id': {'write_only': True},
                'sender_sample_id': {'write_only': True}
        }

class RestyArtifactSerializer(PolymorphicSerializer):
    resource_type_field_name = 'artifact_model'
    model_serializer_mapping = {
        models.MajoraArtifact: BaseRestyArtifactSerializer,
        models.BiosampleArtifact: RestyBiosampleArtifactSerializer,
    }



class RestyPublishedArtifactGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PublishedArtifactGroup
        fields = ('id', 'published_name', 'published_date',)


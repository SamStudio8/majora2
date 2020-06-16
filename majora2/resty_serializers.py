from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from majora2 import models

class RestyArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraArtifact
        fields = ('id', 'dice_name', 'artifact_kind',)

class RestyBiosampleArtifactSerializer(RestyArtifactSerializer):
    class Meta:
        model = models.BiosampleArtifact
        fields = RestyArtifactSerializer.Meta.fields + ('central_sample_id',)

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


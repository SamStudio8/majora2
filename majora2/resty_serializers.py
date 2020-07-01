from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from majora2 import models

class BaseRestyProcessRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraArtifactProcessRecord

class BaseRestyProcessSerializer(serializers.ModelSerializer):
    who = serializers.CharField(source='who.username')
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
class RestyDNASequencingProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DNASequencingProcess
        fields = BaseRestyProcessSerializer.Meta.fields + (
            'run_name',
            'instrument_make',
            'instrument_model',
            'flowcell_type',
            'flowcell_id',
        )
class RestyProcessSerializer(PolymorphicSerializer):
    resource_type_field_name = 'process_model'
    model_serializer_mapping = {
        models.MajoraArtifactProcess: BaseRestyProcessSerializer,
        models.BiosourceSamplingProcess: RestyBiosourceSamplingProcessSerializer,
        models.DNASequencingProcess: RestyDNASequencingProcessSerializer,
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

class RestyDigitalResourceArtifactSerializer(BaseRestyArtifactSerializer):
    class Meta:
        model = models.DigitalResourceArtifact
        fields = BaseRestyArtifactSerializer.Meta.fields + (
                'current_path',
                'current_name',
                'current_hash',
                'current_size',
                'current_extension',
                'current_kind',
        )

class RestyArtifactSerializer(PolymorphicSerializer):
    resource_type_field_name = 'artifact_model'
    model_serializer_mapping = {
        models.MajoraArtifact: BaseRestyArtifactSerializer,
        models.BiosampleArtifact: RestyBiosampleArtifactSerializer,
        models.DigitalResourceArtifact : RestyDigitalResourceArtifactSerializer,
    }



class RestyPublishedArtifactGroupSerializer(serializers.ModelSerializer):
    artifacts = RestyArtifactSerializer(source="tagged_artifacts", many=True)
    processes = serializers.SerializerMethodField()

    class Meta:
        model = models.PublishedArtifactGroup
        fields = (
                'id',
                'published_name',
                'published_date',
                'is_public',
                "artifacts",
                "processes",
        )

    def get_processes(self, obj):
        leaf_cls = self.context.get('leaf_cls', None)
        if leaf_cls:
            #leaf_cls, kind = leaf_cls.split('.', 1)
            try:
                model = apps.get_model('majora2', leaf_cls)
            except:
                #TODO Need to return an error message to the Response
                return []

            artifact = obj.tagged_artifacts.filter(
                Q(polymorphic_ctype_id=ContentType.objects.get_for_model(model))
            ).first() #TODO
            if artifact:
                return RestyProcessSerializer(artifact.process_tree_up(), many=True).data
        return []

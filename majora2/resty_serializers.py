from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from majora2 import models


class DynamicDataviewModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)

        # Instantiate the superclass normally
        super(DynamicDataviewModelSerializer, self).__init__(*args, **kwargs)
        if hasattr(self.Meta, "majora_children"):
            for f, s in self.Meta.majora_children.items():
                self.fields[f] = s[0](context=self.context, **s[1])

        try:
            mdv = models.MajoraDataview.objects.get(code_name=self.context.get("mdv"))
            fields = mdv.fields.filter(model_name=self.Meta.model.__name__).values_list('model_field', flat=True)
        except:
            fields = []
            #TODO Return a very sad response here?

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

class BaseRestyProcessSerializer(DynamicDataviewModelSerializer):
    who = serializers.CharField(source='who.username')
    class Meta:
        model = models.MajoraArtifactProcess
        fields = ('id', 'when', 'who', 'process_kind', 'records')

class RestyCOGUK_BiosourceSamplingProcessSupplement(DynamicDataviewModelSerializer):
    class Meta:
        model = models.COGUK_BiosourceSamplingProcessSupplement
        fields = (
            'is_surveillance',
        )
class RestyGroupSerializer(DynamicDataviewModelSerializer):
    class Meta:
        model = models.MajoraArtifactGroup
        fields = ('id', 'dice_name', 'group_kind', 'physical')


class RestyBiosampleSourceSerializer(DynamicDataviewModelSerializer):
    biosample_source_id = serializers.CharField(source='secondary_id')
    class Meta:
        model = models.BiosampleSource
        fields = RestyGroupSerializer.Meta.fields + (
                'source_type',
                'biosample_source_id',
        )
class RestyBiosourceSamplingProcessSerializer(DynamicDataviewModelSerializer):
    adm0 = serializers.CharField(source='collection_location_country')
    adm1 = serializers.CharField(source='collection_location_adm1')
    adm2 = serializers.CharField(source='collection_location_adm2')
    biosources = serializers.SerializerMethodField()

    class Meta:
        model = models.BiosourceSamplingProcess
        majora_children = {
            "coguk_supp": (RestyCOGUK_BiosourceSamplingProcessSupplement, {})
        }
        fields = BaseRestyProcessSerializer.Meta.fields + (
                'collection_date',
                'received_date',
                'source_age',
                'source_sex',
                'adm0',
                'adm1',
                'adm2',
                'private_collection_location_adm2',
                'coguk_supp',
                'biosources',
        )
        extra_kwargs = {
                'private_collection_location_adm2': {'write_only': True},
        }

    def get_biosources(self, obj):
        source_ids = obj.records.filter(biosourcesamplingprocessrecord__isnull=False).values_list('in_group', flat=True)
        return RestyBiosampleSourceSerializer(models.BiosampleSource.objects.filter(id__in=source_ids), many=True, context=self.context).data

class RestyDNASequencingProcessSerializer(DynamicDataviewModelSerializer):
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
class BaseRestyProcessRecordSerializer(DynamicDataviewModelSerializer):
    class Meta:
        model = models.MajoraArtifactProcessRecord
        #majora_children = {
        #    "process": (RestyProcessSerializer, {})
        #}
        fields = (
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['process'] = RestyProcessSerializer(context=self.context)

class RestyLibraryPoolingProcessRecord(BaseRestyProcessRecordSerializer):
    class Meta:
        model = models.LibraryPoolingProcessRecord
        fields = BaseRestyProcessRecordSerializer.Meta.fields + (
                'barcode',
                'library_strategy',
                'library_source',
                'library_selection',
                'library_primers',
                'library_protocol',
        )

class RestyProcessRecordSerializer(PolymorphicSerializer):
    resource_type_field_name = 'processrecord_model'
    model_serializer_mapping = {
        models.MajoraArtifactProcessRecord: BaseRestyProcessRecordSerializer,
        models.LibraryPoolingProcessRecord: RestyLibraryPoolingProcessRecord,
    }

class BaseRestyArtifactSerializer(DynamicDataviewModelSerializer):
    class Meta:
        model = models.MajoraArtifact
        #majora_children = {
        #      "created": (RestyProcessSerializer, {})
        #}
        fields = ('id', 'dice_name', 'artifact_kind')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['created'] = RestyProcessSerializer(context=self.context)


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



class RestyPublishedArtifactGroupSerializer(DynamicDataviewModelSerializer):
    process_records = serializers.SerializerMethodField()

    class Meta:
        model = models.PublishedArtifactGroup
        majora_children = {
            "artifacts": (RestyArtifactSerializer, {"source":"tagged_artifacts", "many":True})
        }
        fields = (
                'id',
                'published_name',
                'published_date',
                'is_public',
                #"artifacts",
                "process_records",
        )

    #def __init__(self, *args, **kwargs):
    #    super().__init__(*args, **kwargs)
    #    self.fields['artifacts'] = RestyArtifactSerializer(source="tagged_artifacts", many=True, context=self.context)

    def get_process_records(self, obj):
        ids = obj.tagged_artifacts.values_list('id', flat=True)
        models.MajoraArtifactProcessRecord.objects.filter(Q(in_artifact__id__in=ids) | Q(out_artifact__id__in=ids))
        wide_ids = []
        for d in models.MajoraArtifactProcessRecord.objects.filter(Q(in_artifact__id__in=ids) | Q(out_artifact__id__in=ids)).values('in_artifact', 'out_artifact', 'in_group', 'out_group'):
            wide_ids.extend(d.values())
        return RestyProcessRecordSerializer(models.MajoraArtifactProcessRecord.objects.filter(Q(in_artifact__id__in=wide_ids) | Q(out_artifact__id__in=wide_ids)), many=True, context=self.context).data


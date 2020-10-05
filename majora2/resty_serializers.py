from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from django.apps import apps
from django.db.models import Q

from majora2 import models


class DynamicDataviewModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)

        # Instantiate the superclass normally
        super(DynamicDataviewModelSerializer, self).__init__(*args, **kwargs)
        if hasattr(self.Meta, "majora_children"):
            # This ensures the correct context is passed through to downstream serializers
            for f, s in self.Meta.majora_children.items():
                self.fields[f] = s[0](context=self.context, **s[1])

        try:
            fields = self.context.get('mdv_fields', {}).get(self.Meta.model.__name__, [])
            #TODO Implement extra language here? '*' '-field' etc.
        except:
            fields = []
            #TODO Return a very sad response here?

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        self.read_only_fields = self.fields

class RestyMetaRecord(serializers.ModelSerializer):
    class Meta:
        model = models.MajoraMetaRecord
        fields = ('meta_tag', 'meta_name', 'value')

class BaseRestyProcessSerializer(DynamicDataviewModelSerializer):
    who = serializers.CharField(source='who.username')
    #records = serializers.SerializerMethodField()
    class Meta:
        model = models.MajoraArtifactProcess
        fields = ('id', 'when', 'who', 'process_kind', 'records')

    #def get_records(self, obj):
    #    return RestyProcessRecordSerializer(obj.records.all(), many=True, context=self.context)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context["backward"] = True
        #self.fields['records'] = RestyProcessRecordSerializer(many=True, context=self.context)
     

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
    submission_org_code = serializers.SerializerMethodField()

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
                'submission_org',
                'submission_org_code',
                'biosources',
        )
        #extra_kwargs = {
        #        'private_collection_location_adm2': {'write_only': True},
        #}

    def get_submission_org_code(self, obj):
        return obj.submission_org.code if obj.submission_org else None

    def get_biosources(self, obj):
        return RestyBiosampleSourceSerializer([x.in_group for x in obj.records.filter(in_group__biosamplesource__isnull=False).order_by('id').prefetch_related('in_group')], many=True, context=self.context).data

class RestyDNASequencingProcessSerializer(DynamicDataviewModelSerializer):
    libraries = serializers.SerializerMethodField()
    sequencing_org_code = serializers.SerializerMethodField()
    sequencing_submission_date = serializers.SerializerMethodField()
    sequencing_uuid = serializers.CharField(source="id")

    class Meta:
        model = models.DNASequencingProcess
        fields = BaseRestyProcessSerializer.Meta.fields + (
            'run_name',
            'instrument_make',
            'instrument_model',
            'flowcell_type',
            'flowcell_id',
            'libraries',
            'start_time',
            'end_time',
            'duration',
            'sequencing_org_code',
            'sequencing_submission_date',
            'sequencing_uuid',
        )

    def get_sequencing_submission_date(self, obj):
        return obj.when.strftime("%Y-%m-%d") if obj.when else None

    def get_sequencing_org_code(self, obj):
        try:
            return obj.who.profile.institute.code if obj.who.profile.institute else None
        except:
            return None

    def get_libraries(self, obj):
        return RestyLibraryArtifactSerializer([a.in_artifact for a in obj.records.filter(in_artifact__libraryartifact__isnull=False).prefetch_related('in_artifact__metadata')], many=True, context=self.context).data

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
        if not self.context.get("backward"):
            self.fields['process'] = RestyProcessSerializer(context=self.context)

class RestyLibraryPoolingProcessRecordSerializer(BaseRestyProcessRecordSerializer):
    #biosample = serializers.SerializerMethodField()
    class Meta:
        model = models.LibraryPoolingProcessRecord
        fields = BaseRestyProcessRecordSerializer.Meta.fields + (
                #'biosample',
                'barcode',
                'library_strategy',
                'library_source',
                'library_selection',
                'library_primers',
                'library_protocol',
        )

    #def get_biosample(self, obj):
    #    return RestyArtifactSerializer(obj.in_artifact, context=self.context).data

class RestyProcessRecordSerializer(PolymorphicSerializer):
    resource_type_field_name = 'processrecord_model'
    model_serializer_mapping = {
        models.MajoraArtifactProcessRecord: BaseRestyProcessRecordSerializer,
        models.LibraryPoolingProcessRecord: RestyLibraryPoolingProcessRecordSerializer,
    }

class BaseRestyArtifactSerializer(DynamicDataviewModelSerializer):
    published_as = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()

    class Meta:
        model = models.MajoraArtifact
        #majora_children = {
        #    "majora_metadata": (RestyMetaRecord, {"many": True})
        #}
        fields = ('id', 'dice_name', 'artifact_kind', 'published_as', 'metadata')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['created'] = RestyProcessSerializer(context=self.context)

    def get_published_as(self, obj):
        return ",".join([pag.published_name for pag in obj.groups.filter(Q(PublishedArtifactGroup___is_latest=True))])

    def get_metadata(self, obj):
        return RestyMetaRecord(obj.metadata.all(), many=True).data

class RestyBiosampleArtifactSerializer(BaseRestyArtifactSerializer):
    class Meta:
        model = models.BiosampleArtifact
        fields = BaseRestyArtifactSerializer.Meta.fields + (
                'central_sample_id',
                'sender_sample_id',
                'root_sample_id',
        )
        extra_kwargs = {
                #'root_sample_id': {'write_only': True},
                #'sender_sample_id': {'write_only': True}
        }

class RestyLibraryArtifactSerializer(BaseRestyArtifactSerializer):
    library_name = serializers.CharField(source="dice_name")
    records = serializers.SerializerMethodField()
    biosamples = serializers.SerializerMethodField()

    class Meta:
        model = models.LibraryArtifact
        fields = BaseRestyArtifactSerializer.Meta.fields + (
                'library_name',
                'layout_config',
                'layout_read_length',
                'layout_insert_length',
                'seq_kit',
                'seq_protocol',
                'records',
                'biosamples',
        )

    def get_records(self, obj):
        if obj.created:
           return RestyLibraryPoolingProcessRecordSerializer(obj.created.records.filter(in_artifact__biosampleartifact__isnull=False).order_by('id'), many=True, context=self.context).data
        return {}
    def get_biosamples(self, obj):
        if obj.created:
            return RestyBiosampleArtifactSerializer([x.in_artifact for x in obj.created.records.filter(in_artifact__biosampleartifact__isnull=False).order_by('id').prefetch_related('in_artifact__created')], many=True, context=self.context).data
        return {}


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


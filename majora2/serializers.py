import serpy
from majora2 import models # gross

class ArtifactSerializer(serpy.Serializer):
    id = serpy.StrField()
    dice_name = serpy.StrField()
    artifact_kind = serpy.StrField()
    metadata = serpy.MethodField('get_metadata_as_struct')
    metrics = serpy.MethodField('get_metrics_as_struct')
    def get_metadata_as_struct(self, artifact, flat=False):
        metadata = {}
        for m in artifact.metadata.all():
            if not flat:
                if m.meta_tag not in metadata:
                    metadata[m.meta_tag] = {}
                metadata[m.meta_tag][m.meta_name] = m.value
            else:
                metadata["%s.%s" % (m.meta_tag, m.meta_name)] = m.value
        return metadata
    def get_metrics_as_struct(self, artifact, flat=False):
        metrics = {}
        for metric in artifact.temporarymajoraartifactmetric_set.all():
            s = metric.get_serializer()
            metrics[metric.metric_kind.lower()] = s(metric).data
        return metrics

class MetricSerializer(serpy.Serializer):
    namespace = serpy.StrField() 
class MetricSerializer_ThresholdCycle(MetricSerializer):
    min_ct = serpy.FloatField(required=False)
    max_ct = serpy.FloatField(required=False)

class COGUK_BiosourceSamplingProcessSupplementSerializer(serpy.Serializer):
    is_surveillance = serpy.BoolField(required=False)
    is_hcw = serpy.BoolField(required=False)
    employing_hospital_name = serpy.StrField(required=False)
    employing_hospital_trust_or_board = serpy.StrField(required=False)
    is_hospital_patient = serpy.BoolField(required=False)
    is_icu_patient = serpy.BoolField(required=False)
    admission_date = serpy.MethodField('serialize_admission_date')
    admitted_hospital_name = serpy.StrField(required=False)
    admitted_hospital_trust_or_board = serpy.StrField(required=False)
    is_care_home_worker = serpy.BoolField(required=False)
    is_care_home_resident = serpy.BoolField(required=False)
    anonymised_care_home_code = serpy.StrField(required=False)
    admitted_with_covid_diagnosis = serpy.BoolField(required=False)

    def serialize_admission_date(self, supp):
        if supp.admission_date:
            return supp.admission_date.isoformat()

class BiosampleArtifactSerializer(ArtifactSerializer):
    central_sample_id = serpy.StrField()
    sample_type_collected = serpy.StrField()
    sample_type_received = serpy.StrField(attr="sample_type_current")
    swab_site = serpy.StrField(attr="sample_site")
    # metadata

    # Collection stuff
    def serialize_collection_collection_date(self, biosample):
        if biosample.created and biosample.created.collection_date:
            return biosample.created.collection_date.isoformat()
    def serialize_collection_received_date(self, biosample):
        if biosample.created and biosample.created.received_date:
            return biosample.created.received_date.isoformat()
    def translate_adm1(self, biosample):
         value = biosample.created.collection_location_adm1
         countries = {
             "UK-ENG": "England",
             "UK-WLS": "Wales",
             "UK-SCT": "Scotland",
             "UK-NIR": "Northern_Ireland",
         }
         if value in countries:
             return countries[value]
         return value

    collection_date = serpy.MethodField('serialize_collection_collection_date')
    received_date = serpy.MethodField('serialize_collection_received_date')

    submission_user = serpy.StrField(attr='created.submission_user.username')
    submission_org = serpy.StrField(attr='created.submission_org.name')
    submission_org_code = serpy.StrField(attr='created.submission_org.code')
    submission_org_lab_or_name = serpy.MethodField('serialize_org_lab_or_name')

    source_sex = serpy.StrField(attr="created.source_sex", required=False)
    source_age = serpy.IntField(attr="created.source_age", required=False)

    collected_by = None

    adm0 = serpy.StrField(attr="created.collection_location_country")
    adm1 = serpy.StrField(attr="created.collection_location_adm1")
    adm1_trans = serpy.MethodField('translate_adm1')
    adm2 = serpy.StrField(attr="created.collection_location_adm2")
    adm2_private = None

    supplement_coguk = serpy.MethodField('serialize_coguk_supp')

    def serialize_org_lab_or_name(self, collection):
        if collection.created.submission_org.gisaid_lab_name:
            return collection.created.submission_org.gisaid_lab_name
        else:
            return collection.created.submission_org.name
    def serialize_coguk_supp(self, biosample):
        if hasattr(biosample.created, "coguk_supp"):
            return COGUK_BiosourceSamplingProcessSupplementSerializer(biosample.created.coguk_supp).data

    
class DigitalResourceArtifactSerializer(ArtifactSerializer):
    current_path = serpy.StrField()
    current_hash = serpy.StrField()
    current_size = serpy.IntField()
    current_name = serpy.StrField()
    current_kind = serpy.StrField()

class PAGAccessionSerializer(serpy.Serializer):
    service = serpy.StrField()
    primary_accession = serpy.StrField()
    secondary_accession = serpy.StrField(required=False)
    tertiary_accession = serpy.StrField(required=False)

class QCGroupSerializer(serpy.Serializer):
    id = serpy.StrField()
    is_pass = serpy.StrField()
    test_name = serpy.StrField(attr='test_group.slug')

class PAGSerializer(serpy.Serializer):
    id = serpy.StrField()
    published_name = serpy.StrField()
    published_version = serpy.IntField()
    published_date = serpy.MethodField('serialize_published_date')
    artifacts = serpy.MethodField('serialize_tagged_artifacts')

    #accessions = PAGAccessionSerializer(attr='accessions.all', many=True, call=True)
    accessions = serpy.MethodField('serialize_accessions')
    qc_reports = QCGroupSerializer(attr='quality_groups.all', many=True, call=True)

    owner = serpy.StrField(attr='owner.username')
    owner_org_code = serpy.StrField(attr='owner.profile.institute.code')
    owner_org_name = serpy.StrField(attr='owner.profile.institute.name')
    owner_org_gisaid_opted = serpy.BoolField(attr='owner.profile.institute.gisaid_opted')
    owner_org_gisaid_user = serpy.StrField(attr='owner.profile.institute.gisaid_user')
    owner_org_gisaid_mail = serpy.StrField(attr='owner.profile.institute.gisaid_mail')
    owner_org_gisaid_lab_name = serpy.MethodField('serialize_owner_org_gisaid_lab_name')
    owner_org_gisaid_lab_addr = serpy.MethodField('serialize_owner_org_gisaid_lab_addr')
    owner_org_gisaid_lab_list = serpy.MethodField('serialize_owner_org_gisaid_lab_list')

    owner_org_ena_opted = serpy.BoolField(attr='owner.profile.institute.ena_opted')

    owner_org_lab_or_name = serpy.MethodField('serialize_owner_org_lab_or_name')

    def serialize_owner_org_gisaid_lab_name(self, pag):
        a = pag.tagged_artifacts.values_list('id', flat=True)
        try:
            credit_code = models.MajoraMetaRecord.objects.get(artifact__id__in=a, meta_tag='majora', meta_name='credit').value
            name = models.InstituteCredit.objects.get(institute=pag.owner.profile.institute, credit_code=credit_code).lab_name
        except:
            name = pag.owner.profile.institute.gisaid_lab_name
        return name

    def serialize_owner_org_gisaid_lab_addr(self, pag):
        a = pag.tagged_artifacts.values_list('id', flat=True)
        try:
            credit_code = models.MajoraMetaRecord.objects.get(artifact__id__in=a, meta_tag='majora', meta_name='credit').value
            addr = models.InstituteCredit.objects.get(institute=pag.owner.profile.institute, credit_code=credit_code).lab_addr
        except:
            addr = pag.owner.profile.institute.gisaid_lab_addr
        return addr

    def serialize_owner_org_gisaid_lab_list(self, pag):
        a = pag.tagged_artifacts.values_list('id', flat=True)
        l = None
        try:
            credit_code = models.MajoraMetaRecord.objects.get(artifact__id__in=a, meta_tag='majora', meta_name='credit').value
            l = models.InstituteCredit.objects.get(institute=pag.owner.profile.institute, credit_code=credit_code).lab_list
        except:
            l = pag.owner.profile.institute.gisaid_list

        if l:
            return l.replace('\t', ' ').replace('\r', '').replace('\n', ',').replace(",,", ',').replace(' ,', ',') # sigh
        return ""


    def serialize_owner_org_lab_or_name(self, pag):
        if pag.owner.profile.institute.gisaid_lab_name:
            return pag.owner.profile.institute.gisaid_lab_name
        else:
            return pag.owner.profile.institute.name

    def serialize_tagged_artifacts(self, pag):
        a = {}
        for artifact in pag.tagged_artifacts.all():
            if artifact.artifact_kind not in a:
                a[artifact.artifact_kind] = []
            s = artifact.get_serializer()
            a[artifact.artifact_kind].append( s(artifact).data )
        return a

    def serialize_accessions(self, pag):
        a = {}
        for accession in pag.accessions.all():
            a[accession.service] = PAGAccessionSerializer(accession).data
        return a

    def serialize_published_date(self, pag):
        return pag.published_date.isoformat()

class PAGQCSerializer(serpy.Serializer):
    id = serpy.StrField()
    is_pass = serpy.StrField()
    pag = PAGSerializer()

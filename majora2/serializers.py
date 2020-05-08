import serpy
class ArtifactSerializer(serpy.Serializer):
    id = serpy.StrField()
    dice_name = serpy.StrField()
    artifact_kind = serpy.StrField()

class DigitalResourceArtifactSerializer(ArtifactSerializer):
    current_path = serpy.StrField()
    current_name = serpy.StrField()
    current_kind = serpy.StrField()

class PAGAccessionSerializer(serpy.Serializer):
    service = serpy.StrField()
    primary_accession = serpy.StrField()
    secondary_accesison = serpy.StrField()
    tertiary_accession = serpy.StrField()

class QCGroupSerializer(serpy.Serializer):
    id = serpy.StrField()
    is_pass = serpy.StrField()
    test_name = serpy.StrField(attr='test_group.slug')

class PAGSerializer(serpy.Serializer):
    id = serpy.StrField()
    published_name = serpy.StrField()
    published_version = serpy.IntField()
    published_date = serpy.MethodField('serialize_published_date')
    tagged_artifacts = serpy.MethodField('serialize_tagged_artifacts')

    accessions = PAGAccessionSerializer(attr='accessions.all', many=True, call=True)
    qc_reports = QCGroupSerializer(attr='quality_groups.all', many=True, call=True)

    owner = serpy.StrField(attr='owner.username')
    owner_org_code = serpy.StrField(attr='owner.profile.institute.code')
    owner_org_gisaid_user = serpy.StrField(attr='owner.profile.institute.gisaid_user')
    owner_org_gisaid_mail = serpy.StrField(attr='owner.profile.institute.gisaid_mail')
    owner_org_gisaid_lab_name = serpy.StrField(attr='owner.profile.institute.gisaid_lab_name')
    owner_org_gisaid_lab_addr = serpy.StrField(attr='owner.profile.institute.gisaid_lab_addr')
    owner_org_gisaid_lab_list = serpy.StrField(attr='owner.profile.institute.gisaid_list')

    def serialize_tagged_artifacts(self, pag):
        a = []
        for artifact in pag.tagged_artifacts.all():
            s = artifact.get_serializer()
            a.append(s(artifact).data)
        return a

    def serialize_published_date(self, pag):
        return pag.published_date.isoformat()

class PAGQCSerializer(serpy.Serializer):
    id = serpy.StrField()
    is_pass = serpy.StrField()
    pag = PAGSerializer()

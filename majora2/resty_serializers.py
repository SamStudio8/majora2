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

    """
    def create(self, validated_data):
        collection_data = validated_data.pop('created')
        
        collection_data["collected_by"] = collection_data["collecting_org"]
        collection_data["when"] = collection_data["collection_date"] if collection_data["collection_date"] else collection_data["received_date"]
        sample_p = models.BiosourceSamplingProcess.objects(**collection_data)


        if not sample_p.who:
            sample_p.who = user
            sample_p.when = collection_date if collection_date else received_date
            sample_p.submitted_by = submitted_by
            sample_p.submission_user = user
            sample_p.submission_org = form.cleaned_data.get("submitting_org")
            sample_p.save()
            #signals.new_sample.send(sender=None, sample_id=sample.central_sample_id, submitter=sample.created.submitted_by)
            # fuck
            if source:
                for record in sample_p.records.all():
                    if record.out_artifact == sample:
                        record.in_group = source
                        record.save()

        sample_p.collection_location_country = form.cleaned_data.get("country")
        sample_p.collection_location_adm1 = form.cleaned_data.get("adm1")
        sample_p.collection_location_adm2 = form.cleaned_data.get("adm2").upper() # capitalise the county for now?
        sample_p.private_collection_location_adm2 = form.cleaned_data.get("adm2_private")
        sample_p.source_age = form.cleaned_data.get("source_age")
        sample_p.source_sex = form.cleaned_data.get("source_sex")

        sampling_rec = models.BiosourceSamplingProcessRecord(
            process=sample_p,
            in_group=source,
            out_artifact=sample,
        )
        sampling_rec.save()
        sample.created = sample_p # Set the sample collection process
        sample.save()

       modela_data = validated_data.pop('model_a')
       model_b = ModelB.objects.create(**validated_data)
       ModelA.objects.create(model_b=model_b, **modela_data)
       return model_b
        """

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


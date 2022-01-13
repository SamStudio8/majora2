import uuid
import os
import builtins

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.db.models import Q

from django.utils import timezone

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.fields import GenericRelation

from polymorphic.models import PolymorphicModel
from .submodels import *

from oauth2_provider.settings import oauth2_settings
OAUTH_APPLICATION_MODEL = oauth2_settings.APPLICATION_MODEL

class MajoraArtifact(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # 
    dice_name = models.CharField(max_length=96, blank=True, null=True, unique=True)
    meta_name = models.CharField(max_length=96, blank=True, null=True)

    root_artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.PROTECT, related_name="descendants")
    quarantined = models.BooleanField(default=False)

    primary_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="child_artifacts")
    groups = models.ManyToManyField('MajoraArtifactGroup', related_name="tagged_artifacts", blank=True) # represents 'tagged' ResourceGroups

    # Trying something different... again...
    created = models.ForeignKey("MajoraArtifactProcess", blank=True, null=True, on_delete=models.PROTECT, related_name="artifacts_created")

    is_pagged = models.BooleanField(default=False)

    history = GenericRelation("tatl.TatlVerb")

    class Meta:
        permissions = [
            ("view_majoraartifact_info", "Can view basic information of any artifact"),
        ]

    @classmethod
    def construct_test_object(cls):
        raise NotImplementedError(cls.__name__)

    @property
    def artifact_kind(self):
        return 'Artifact'
    @property
    def kind(self):
        return self.artifact_kind
    @property
    def path(self):
        return ""
    @property
    def name(self):
        if self.meta_name:
            return self.meta_name
        else:
            return self.dice_name
    @property
    def process_history(self):
        return (self.before_process.all() | self.after_process.all()).order_by('-process__when').get_real_instances()

    @property
    def process_tree(self):
        return self.process_tree_up([])
    def process_tree_up(self, seen=set([])):
        a = []
        seen = set(seen)

        for proc in self.after_process.all().order_by('-process__when'):
            if proc in seen:
                continue

            if proc.in_group:
                if proc.process not in a:
                    a.append(proc.process)
                a.extend(proc.in_group.process_tree_up(seen))
            if proc.in_artifact:
                if proc.process not in a:
                    a.append(proc.process)
                a.extend(proc.in_artifact.process_tree_up(seen))
            seen.add(proc)
        return reversed(a)
    @property
    def process_leaf(self):
        a = []
        seen = set([])
        a.extend(self.before_process.all().order_by('-process__when'))
        for proc in a:
            if proc.out_artifact:
                if proc.in_artifact and proc.in_artifact.id != proc.out_artifact.id:# or proc.in_group:
                    if proc.out_artifact not in seen:
                        seen.add(proc.out_artifact)
                        a.extend(proc.out_artifact.process_leaf)
        return a

    @property
    def process_tree_down(self):
        return self.build_process_tree_down(set([self]), set([self]))
    def build_process_tree_down(self, seen, crossed_bridges):
        a = []
        add = 0

        # Detect whether we can cross any bridges
        current_bridges = set([])
        for proc in self.before_process.all().order_by('-process__when'):
            if proc.out_artifact and proc.bridge_artifact:
                current_bridges.add(proc.bridge_artifact)
        can_cross = False
        for b in current_bridges:
            if b in crossed_bridges:
                can_cross = True

        # Go through each process record attached to this artifact
        for proc in self.before_process.all().order_by('-process__when'):
            add = 0
            children = []
            if proc.out_artifact:
                # If this record produces an artifact to share...
                if proc.out_artifact not in seen:
                    # ...and we have not already added this artifact to the process tree
                    if (proc.bridge_artifact is None) or (proc.bridge_artifact in crossed_bridges) or not can_cross:
                        # ...and this artifact is not the other side of a bridge that should not be crossed
                        #children.append(proc)
                        children.extend( proc.out_artifact.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges) )
                        #seen.add(proc.out_artifact)
                        add = 1

            # Delve one group deep
            child_ = {}
            c_add = 0
            if proc.out_group and proc.out_group not in seen:
                #child_[d_proc] = child_proc.out_group.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges)
                children.extend( proc.out_group.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges) )
                add = 1
                seen.add(proc.out_group)
                #if proc.out_group not in seen:
                #    if proc.bridge_group is None or proc.bridge_group in seen:
                #        for child_proc in proc.out_group.before_process.all().order_by('-process__when'):
                #            child_[child_proc] = child_proc.out_artifact.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges)
                #            c_add = 1
                #        seen.add(proc.out_group)

            if c_add:
                a.append({proc: [children, child_]})
            elif add:
                a.append({proc: children})
        return a

    @property
    def is_quarantined(self):
        if self.quarantined:
            return self
        else:
            if self.root_artifact:
                if self.root_artifact.quarantined:
                    return self.root_artifact
            else:
                for process in self.process_tree:
                    if process.in_artifact and process.in_artifact != self:
                        if process.in_artifact.quarantined:
                            return process.in_artifact
                    if process.out_artifact and process.out_artifact != self:
                        if process.out_artifact.quarantined:
                            return process.out_artifact
        return False
    @property
    def quarantined_reason(self):
        if self.is_quarantined:
            try:
                return MajoraArtifactProcessRecord.objects.filter(Q(in_artifact=self.is_quarantined, instance_of=MajoraArtifactQuarantinedProcessRecord)).order_by("-process__when").last().note
            except:
                return "Unknown"
        else:
            return ""
    @property
    def artifact_tree(self):
        a = []
        for proc in self.process_leaf:
            if proc.out_artifact:
                if proc.out_artifact not in a:
                    a.append(proc.out_artifact)
        for proc in self.process_tree:
            if proc.in_artifact:
                if proc.in_artifact not in a:
                    a.append(proc.in_artifact)
        return a

    @classmethod
    def sorto(cls, a):
        return a

    @property
    def clones(self):
        return []
    @property
    def siblings(self):
        #Return tubes that had the same input to their last process
        if self.modified and self.modified.in_artifact:
            return [x.out_artifact for x in MajoraArtifactProcessRecord.objects.filter(in_artifact=self.modified.in_artifact) if x.out_artifact and x.out_artifact.id != self.id]
    @property
    def children(self):
        return [x.out_artifact for x in MajoraArtifactProcessRecord.objects.filter(in_artifact=self) if x.out_artifact and x.out_artifact.id != self.id]
    @property
    def observed(self):
        try:
            return self.process_history[-1]
        except:
            return None
    @property
    def modified(self):
        # Assume by default that last seen was last modified
        return self.observed

    @property
    def created_on(self):
        return self.created.process.when
    @property
    def observed_on(self):
        return self.observed.process.when
    @property
    def modified_on(self):
        return self.modified.process.when

    def get_metadatum(self, tag, name, group_tree=False, process_tree=False):
        m = self.metadata.filter(meta_tag=tag, meta_name=name)
        if m.count() > 0:
            return m

        # Try and traverse group tree
        #TODO What about non-primary groups
        if group_tree:
            m = self.primary_group.get_metadatum(tag, name)
            if m.count() > 0:
                return m

        # Try and traverse process tree
        if process_tree:
            #TODO in order from bottom to top?
            for a in self.process_tree:
                try:
                    m = a.in_artifact.get_metadatum(tag, name)
                    if m.count() > 0:
                        return m

                    m = a.out_artifact.get_metadatum(tag, name)
                    if m.count() > 0:
                        return m

                except AttributeError:
                        pass

        return None

    def get_metadata_as_struct(self, flat=False):
        metadata = {}
        for m in self.metadata.all():
            if m.restricted:
                continue

            if not flat:
                if m.meta_tag not in metadata:
                    metadata[m.meta_tag] = {}
                metadata[m.meta_tag][m.meta_name] = m.value
            else:
                metadata["%s.%s" % (m.meta_tag, m.meta_name)] = m.value
        return metadata

    def get_metrics_as_struct(self, flat=False):
        metrics = {}
        for m in self.metrics.all():
            if m.namespace not in metrics:
                metrics[m.namespace] = m.as_struct() #TODO flat or not
        return metrics

    def get_pags(self, include_suppressed=False):
        if not include_suppressed:
            return self.groups.filter(Q(PublishedArtifactGroup___is_latest=True, PublishedArtifactGroup___is_suppressed=False))
        else:
            return self.groups.filter(Q(PublishedArtifactGroup___is_latest=True))

    def as_struct(self):
        return {}
    def get_serializer(self):
        from . import serializers
        return serializers.ArtifactSerializer

    @property
    def tatl_history(self):
        return self.history.filter(~Q(verb="RETRIEVE")).order_by('-request__timestamp')

    @property
    def info(self):
        info = {
            "id": str(self.id),
            "kind": self.kind,
            "name": self.name,
            "path": self.path,
            "metadata": self.get_metadata_as_struct(flat=True),
        }

        return info

class MajoraArtifactGroupLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    link_name = models.CharField(max_length=128, unique=True)
    from_group = models.ForeignKey('MajoraArtifactGroup', on_delete=models.PROTECT, related_name="out_glinks")
    to_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="in_glinks")
    to_artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.PROTECT, related_name="in_glinks")

# TODO This will become the MajoraGroup
class MajoraArtifactGroup(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    unique_name = models.CharField(max_length=128, blank=True, null=True, unique=True) #TODO graduate away from meta_name, needs to be project unique rather than global, but it will work here 

    dice_name = models.CharField(max_length=96, blank=True, null=True, unique=True) 
    meta_name = models.CharField(max_length=96, blank=True, null=True) # TODO force unique?

    group_path = models.CharField(max_length=1024, blank=True, null=True, unique=True)
    temp_kind = models.CharField(max_length=48, blank=True, null=True)

    root_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="descendants")
    parent_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="children")
    groups = models.ManyToManyField('MajoraArtifactGroup', related_name="tagged_groups", blank=True) # represents 'tagged' ResourceGroups
    processes = models.ManyToManyField('MajoraArtifactProcessGroup', related_name="tagged_processes", blank=True) # represents 'tagged' ResourceGroups
    physical = models.BooleanField(default=False)

    #links = models.ManyToManyField('MajoraArtifactGroupLink', related_name="from_groups", blank=True)
    history = GenericRelation("tatl.TatlVerb")

    def __str__(self):
        return "%s (%s)" % (self.name, self.id)

    def nuke_tree(self):
        self.groups.clear()
        for g in self.children.all():
            g.nuke_tree()
        self.delete()
    @property
    def group_kind(self):
        return 'Artifact Group'
    @property
    def kind(self):
        return self.group_kind
    @property
    def name(self):
        if self.meta_name:
            return self.meta_name
        elif self.unique_name:
            return self.unique_name
        return str(self.id)
    @property
    def full_name(self):
        return self.name
    @property
    def n_child_artifacts(self):
        return self.child_artifacts.count()
    @property
    def n_tagged_artifacts(self):
        return self.tagged_artifacts.count()
    @property
    def hierarchy(self):
        tree = []
        tail = self
        while tail:
            tree.append(tail)
            tail = tail.parent_group
        tree.reverse()
        return tree
    def get_metadatum(self, tag, name):
        m = self.metadata.filter(meta_tag=tag, meta_name=name)
        if m.count() > 0:
            return m

        tail = self.parent_group
        while tail:
            m = tail.metadata.filter(meta_tag=tag, meta_name=name, inheritable=True)
            if m.count() > 0:
                return m
            tail = tail.parent_group
        return m

    def group_tagged_artifacts(self):
        groups = {}
        for a in self.tagged_artifacts.all().union(self.child_artifacts.all()):
            cls = a.__class__
            if cls not in groups:
                groups[cls] = []
            groups[cls].append(a)
        for cls in groups:
            groups[cls] = cls.sorto(groups[cls])
        return groups

    @property
    def process_tree_down(self):
        return self.build_process_tree_down(set([self]), set([self]))
    def build_process_tree_down(self, seen, crossed_bridges):
        a = []
        add = 0

        # Detect whether we can cross any bridges
        current_bridges = set([])
        for proc in self.before_process.all().order_by('-process__when'):
            if proc.out_artifact and proc.bridge_artifact:
                current_bridges.add(proc.bridge_artifact)
        can_cross = False
        for b in current_bridges:
            if b in crossed_bridges:
                can_cross = True

        # Go through each process record attached to this artifact
        for proc in self.before_process.all().order_by('-process__when'):
            add = 0
            children = []
            if proc.out_artifact:
                # If this record produces an artifact to share...
                if proc.out_artifact not in seen:
                    # ...and we have not already added this artifact to the process tree
                    if (proc.bridge_artifact is None) or (proc.bridge_artifact in crossed_bridges) or not can_cross:
                        # ...and this artifact is not the other side of a bridge that should not be crossed
                        #children.append(proc)
                        children.extend( proc.out_artifact.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges) )
                        seen.add(proc.out_artifact)
                        add = 1

            # Delve one group deep
            child_ = {}
            c_add = 0
            if proc.out_group:
                #child_[d_proc] = child_proc.out_group.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges)
                children.extend( proc.out_group.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges) )
                add = 1
                seen.add(proc.out_group)
                #if proc.out_group not in seen:
                #    if proc.bridge_group is None or proc.bridge_group in seen:
                #        for child_proc in proc.out_group.before_process.all().order_by('-process__when'):
                #            child_[child_proc] = child_proc.out_artifact.build_process_tree_down(seen=seen, crossed_bridges=crossed_bridges)
                #            c_add = 1
                #        seen.add(proc.out_group)

            if c_add:
                a.append({proc: [children, child_]})
            elif add:
                a.append({proc: children})
        return a
    @property
    def process_tree(self):
        return self.process_tree_up([])
    def process_tree_up(self, seen=set([])):
        a = []
        seen = set(seen)

        for proc in self.after_process.all().order_by('-process__when'):
            if proc in seen:
                continue

            if proc.in_group:
                if proc.process not in a:
                    a.append(proc.process)
                a.extend(proc.in_group.process_tree_up(seen))
            if proc.in_artifact:
                if proc.process not in a:
                    a.append(proc.process)
                a.extend(proc.in_artifact.process_tree_up(seen))
            seen.add(proc)
        return reversed(a)


class PublishedArtifactGroup(MajoraArtifactGroup):
    published_name = models.CharField(max_length=128, db_index=True)
    published_version = models.PositiveIntegerField() #TODO replace this with a custom field that can handle semvar
                                                      # even tempted to ditch this, make MAG top level root model
                                                      # and each version is just a new PAG named with its version
                                                      # then reconstruct path as:  <NAME> / <VERSION>
    #pag_kind = models.CharField()
    published_date = models.DateField(blank=True, null=True)

    is_draft = models.BooleanField(default=False) # ?
    is_latest = models.BooleanField(default=False)
    #replaced_by = models.ForeignKey('PublishedArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="replaces")

    is_public = models.BooleanField(default=False)
    public_timestamp = models.DateTimeField(blank=True, null=True)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    #TODO owner_org?

    is_suppressed = models.BooleanField(default=False)
    suppressed_date = models.DateTimeField(blank=True, null=True)
    suppressed_reason = models.CharField(max_length=128, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["published_name", "is_latest"], name="is_only_published"),
        ]
        permissions = [
            ("temp_can_read_pags_via_api", "Can read published artifact groups via the API"),
            ("can_suppress_pags_via_api", "Can suppress their own published artifact group via the API"),
            ("can_suppress_any_pags_via_api", "Can suppress any published artifact group via the API"),
        ]
    def as_struct(self):
        if self.is_suppressed:
            return {
                "published_name": self.published_name,
                "is_suppressed": self.is_suppressed,
                "suppressed_date": self.suppressed_date.strftime("%Y-%m-%d") if self.suppressed_date else None,
                "suppressed_reason": self.suppressed_reason,
            }


        artifacts = {}
        for artifact in self.tagged_artifacts.all():
            if artifact.artifact_kind not in artifacts:
                artifacts[artifact.artifact_kind] = []
            artifacts[artifact.artifact_kind].append(artifact.as_struct())

        return {
            "published_name": self.published_name,
            "published_version": self.published_version,
            "published_date": self.published_date.strftime("%Y-%m-%d") if self.published_date else None,
            "is_latest": self.is_latest,

            "qc_reports": {report.test_group.slug: report.as_struct() for report in self.quality_groups.all()},
            "artifacts": artifacts,
            "accessions": [accession.as_struct() for accession in self.accessions.all()],

            "owner": self.owner.username,
            "owner_org_code": self.owner.profile.institute.code if self.owner.profile.institute else None,

            "owner_org_gisaid_user": self.owner.profile.institute.gisaid_user if self.owner.profile.institute else None,
            "owner_org_gisaid_mail": self.owner.profile.institute.gisaid_mail if self.owner.profile.institute else None,
            "owner_org_gisaid_lab_name": self.owner.profile.institute.gisaid_lab_name if self.owner.profile.institute else None,
            "owner_org_gisaid_lab_addr": self.owner.profile.institute.gisaid_lab_addr if self.owner.profile.institute else None,
            "owner_org_gisaid_list": self.owner.profile.institute.gisaid_list if self.owner.profile.institute else None,


        }

    @property
    def group_kind(self):
        return "Published Artifact Group"
    @property
    def name(self):
        return self.published_name
    @property
    def path(self):
        return self.published_name
    @classmethod
    def get_resty_serializer(cls):
        from . import resty_serializers
        return resty_serializers.RestyPublishedArtifactGroupSerializer

# TODO This is a quick and dirty way to toss the accessions we're getting snowed with onto a PAG
# Partly because we just want to be able to quickly count how many PAGs are public, by institute
# I eventually want to move these tags onto the artifacts themselves but this needs more work (as I have big ideas for splitting apart the models for files in particular)
class TemporaryAccessionRecord(models.Model):
    pag = models.ForeignKey('PublishedArtifactGroup', on_delete=models.PROTECT, related_name="accessions")
    #artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.PROTECT)
    service = models.CharField(max_length=64)
    primary_accession = models.CharField(max_length=64, blank=True, null=True)
    secondary_accession = models.CharField(max_length=64, blank=True, null=True)
    tertiary_accession = models.CharField(max_length=64, blank=True, null=True)

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)

    requested_timestamp = models.DateTimeField(blank=True, null=True)
    is_public = models.BooleanField(default=False)
    public_timestamp = models.DateTimeField(blank=True, null=True)

    is_rejected = models.BooleanField(default=False)
    rejected_timestamp = models.DateTimeField(blank=True, null=True)
    rejected_reason = models.CharField(max_length=24, blank=True, null=True)

    def as_struct(self):
        return {
            "service": self.service,
            "primary_accession": self.primary_accession,
        }


class PAGQualityTestEquivalenceGroup(models.Model):
    slug = models.SlugField(max_length=64, blank=True, null=True)
    name = models.CharField(max_length=64, unique=True)

class PAGQualityTest(models.Model):
    group = models.ForeignKey('PAGQualityTestEquivalenceGroup', on_delete=models.PROTECT, related_name="tests", blank=True, null=True)
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, blank=True, null=True)

class PAGQualityTestFilter(models.Model):
    test = models.ForeignKey('PAGQualityTest', on_delete=models.PROTECT, related_name="filters") # these are not versioned so you can only apply them to the top model, not the version model
    filter_name = models.CharField(max_length=64)
    filter_desc = models.CharField(max_length=128)

    force_field = models.BooleanField(default=True)

    #metric_namespace = models.CharField(max_length=64, blank=True, null=True)
    #metric_name = models.CharField(max_length=64, blank=True, null=True)

    metadata_namespace = models.CharField(max_length=64, blank=True, null=True)
    metadata_name = models.CharField(max_length=64, blank=True, null=True)

    filter_on_str =  models.CharField(max_length=64)
    #filter_test_value_numeric =  models.CharField(max_length=64) # use this if op is set to gt/lt(e)
    op = models.CharField(max_length=3, blank=True, null=True) # lol ? #API allows NEQ or EQ here atm

class PAGQualityTestVersion(models.Model):
    test = models.ForeignKey('PAGQualityTest', on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveSmallIntegerField()
    version_date = models.DateField()

#TODO PAGQualityTestRule > PAGQualityNumericTestRule, PAGQualityBooleanTestRule, ?
class PAGQualityTestRule(models.Model):
    test = models.ForeignKey('PAGQualityTestVersion', on_delete=models.PROTECT, related_name="rules")
    rule_name = models.CharField(max_length=64)
    rule_desc = models.CharField(max_length=128)

    metric_namespace = models.CharField(max_length=64)
    metric_name = models.CharField(max_length=64)
    warn_min = models.FloatField(blank=True, null=True)
    warn_max = models.FloatField(blank=True, null=True)
    fail_min = models.FloatField(blank=True, null=True)
    fail_max = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.rule_name

class PAGQualityBasicTestDecision(models.Model):
    test = models.ForeignKey('PAGQualityTestVersion', on_delete=models.PROTECT, related_name="decisions")
    a = models.ForeignKey('PAGQualityTestRule', on_delete=models.PROTECT, related_name="rules_as_a")
    b = models.ForeignKey('PAGQualityTestRule', on_delete=models.PROTECT, blank=True, null=True, related_name="rules_as_b")
    op = models.CharField(max_length=3, blank=True, null=True) # lol ?

    def __str__(self):
        if self.b:
            return "%s %s %s" % (self.a.rule_name, self.op, self.b.rule_name)
        else:
            return self.a.rule_name


# TODO A quick and dirty way to store and group QC on the files. QC reports should be attached to artifacts directly.
# I'm gonna throw them on a PAG because for this project we need fast PAG access.
# although actually, if you QC an artifact, it should be published, so this might be a good model
class PAGQualityReportEquivalenceGroup(models.Model):
    pag = models.ForeignKey('PublishedArtifactGroup', on_delete=models.CASCADE, related_name="quality_groups")
    test_group = models.ForeignKey('PAGQualityTestEquivalenceGroup', on_delete=models.PROTECT, related_name="report_groups", blank=True, null=True)
    is_pass = models.BooleanField(default=False) # we'll bubble passes up to the top group

    last_updated = models.DateTimeField(blank=True, null=True)
    def as_struct(self):
        return {
            "is_pass": self.is_pass,
            "test_name": self.test_group.slug,
        }

class PAGQualityReportGroup(models.Model):
    pag = models.ForeignKey('PublishedArtifactGroup', on_delete=models.PROTECT, related_name="quality_tests", blank=True, null=True)
    group = models.ForeignKey('PAGQualityReportEquivalenceGroup', on_delete=models.CASCADE, related_name="quality_tests", blank=True, null=True)

    test_set = models.ForeignKey('PAGQualityTest', on_delete=models.PROTECT, related_name="report_groups", blank=True, null=True)

    is_pass = models.BooleanField(default=False) # we'll bubble passes up to the top group
    is_skip = models.BooleanField(default=False)

    @property
    def get_latest(self):
        return self.reports.latest('timestamp')

class PAGQualityReport(models.Model):
    report_group = models.ForeignKey('PAGQualityReportGroup', on_delete=models.CASCADE, related_name="reports")
    test_set_version = models.ForeignKey('PAGQualityTestVersion', on_delete=models.CASCADE, related_name="reports")

    timestamp = models.DateTimeField()
    is_pass = models.BooleanField(default=False)
    is_skip = models.BooleanField(default=False)

class PAGQualityReportRuleRecord(models.Model):
    report = models.ForeignKey('PAGQualityReport', on_delete=models.CASCADE, related_name="tests")
    rule = models.ForeignKey('PAGQualityTestRule', on_delete=models.PROTECT)
    test_metric_str = models.CharField(max_length=64, blank=True, null=True)
    is_pass = models.BooleanField(default=False)
    is_warn = models.BooleanField(default=False)
    is_fail = models.BooleanField(default=False)

class PAGQualityReportDecisionRecord(models.Model):
    report = models.ForeignKey('PAGQualityReport', on_delete=models.CASCADE, related_name="decisions")
    decision = models.ForeignKey('PAGQualityBasicTestDecision', on_delete=models.PROTECT)

    a = models.ForeignKey('PAGQualityReportRuleRecord', on_delete=models.CASCADE, related_name="decisions_as_a")
    b = models.ForeignKey('PAGQualityReportRuleRecord', on_delete=models.CASCADE, blank=True, null=True, related_name="decisions_as_b")
    is_pass = models.BooleanField(default=False)
    is_warn = models.BooleanField(default=False)
    is_fail = models.BooleanField(default=False)


# Until Artifacts become less generic in Majora3, we have to encode properties about them somewhere
class TemporaryMajoraArtifactMetric(PolymorphicModel):
    artifact = models.ForeignKey('MajoraArtifact', on_delete=models.CASCADE, related_name="metrics")
    namespace = models.CharField(max_length=64, blank=True, null=True)

    @property
    def kind(self):
        return self.metric_kind
    @property
    def metric_kind(self):
        return 'Metric'

    def as_struct(self):
        return {}
    def get_serializer(self):
        from . import serializers
        return serializers.MetricSerializer

class TemporaryMajoraArtifactMetricRecord(PolymorphicModel):
    artifact_metric = models.ForeignKey('TemporaryMajoraArtifactMetric', on_delete=models.CASCADE, related_name="metric_records")

class TemporaryMajoraArtifactMetric_ThresholdCycle(TemporaryMajoraArtifactMetric):
    num_tests = models.PositiveIntegerField()
    min_ct = models.FloatField()
    max_ct = models.FloatField()

    @property
    def metric_kind(self):
        return 'Ct'
    def as_struct(self):
        return {
            "num_tests": self.num_tests,
            "min_ct": self.min_ct,
            "max_ct": self.max_ct,
            "records": [record.as_struct() for record in self.metric_records.all()],
        }
    def get_serializer(self):
        from . import serializers
        return serializers.MetricSerializer_ThresholdCycle

class TemporaryMajoraArtifactMetricRecord_ThresholdCycle(TemporaryMajoraArtifactMetricRecord):
    ct_value = models.FloatField(blank=True, null=True)
    test_platform = models.CharField(max_length=48, blank=True, null=True)
    test_target = models.CharField(max_length=48, blank=True, null=True)
    test_kit = models.CharField(max_length=48, blank=True, null=True)

    def as_struct(self):
        return {
            "ct_value": self.ct_value,
            "test_platform": self.test_platform,
            "test_target": self.test_target,
            "test_kit": self.test_kit,
        }

class TemporaryMajoraArtifactMetric_Sequence(TemporaryMajoraArtifactMetric):
    num_seqs = models.PositiveIntegerField()
    num_bases = models.PositiveIntegerField()
    pc_acgt = models.FloatField()
    pc_masked = models.FloatField()
    pc_invalid = models.FloatField()
    longest_gap = models.PositiveIntegerField(blank=True, null=True)
    longest_ungap = models.PositiveIntegerField(blank=True, null=True)

    @property
    def metric_kind(self):
        return 'Sequence'
    def as_struct(self):
        ret = {
            "num_seqs": self.num_seqs,
            "num_bases": self.num_bases,
            "pc_acgt": self.pc_acgt,
            "pc_masked": self.pc_masked,
            "pc_invalid": self.pc_invalid,
        }
        if self.longest_gap is not None:
            ret["longest_gap"] = self.longest_gap
        if self.longest_ungap is not None:
            ret["longest_ungap"] = self.longest_ungap
        return ret

class TemporaryMajoraArtifactMetric_Mapping(TemporaryMajoraArtifactMetric):
    num_pos = models.PositiveIntegerField()
    num_maps = models.PositiveIntegerField(blank=True, null=True)
    num_unmaps = models.PositiveIntegerField(blank=True, null=True)

    median_cov = models.FloatField(blank=True, null=True)
    mean_cov = models.FloatField(blank=True, null=True)

    pc_pos_cov_gte1 = models.FloatField(blank=True, null=True)
    pc_pos_cov_gte5 = models.FloatField(blank=True, null=True)
    pc_pos_cov_gte10 = models.FloatField(blank=True, null=True)
    pc_pos_cov_gte20 = models.FloatField(blank=True, null=True)
    pc_pos_cov_gte50 = models.FloatField(blank=True, null=True)
    pc_pos_cov_gte100 = models.FloatField(blank=True, null=True)
    pc_pos_cov_gte200 = models.FloatField(blank=True, null=True)

    @property
    def metric_kind(self):
        return 'Mapping'
    def as_struct(self):
        ret = {
            "num_pos": self.num_pos,
            "pc_pos_cov_gte10": self.pc_pos_cov_gte10,
            "pc_pos_cov_gte20": self.pc_pos_cov_gte20,
        }
        if self.num_maps is not None:
            ret["num_maps"] = self.num_maps
        if self.num_unmaps is not None:
            ret["num_unmaps"] = self.num_unmaps

        if self.mean_cov is not None:
            ret["mean_cov"] = self.mean_cov
        return ret
    def get_serializer(self):
        from . import serializers
        return serializers.MetricSerializer_Mapping


class TemporaryMajoraArtifactMetric_Mapping_Tiles(TemporaryMajoraArtifactMetric):
    n_tiles = models.PositiveSmallIntegerField()

    pc_tiles_medcov_gte1 = models.FloatField()
    pc_tiles_medcov_gte5 = models.FloatField()
    pc_tiles_medcov_gte10 = models.FloatField()
    pc_tiles_medcov_gte20 = models.FloatField()
    pc_tiles_medcov_gte50 = models.FloatField()
    pc_tiles_medcov_gte100 = models.FloatField()
    pc_tiles_medcov_gte200 = models.FloatField()
    # TODO tile-cov pairs as records

    @property
    def metric_kind(self):
        return 'Tile'

    def as_struct(self):
        return {
            "pc_tiles_medcov_gte1": self.pc_tiles_medcov_gte1,
            "pc_tiles_medcov_gte5": self.pc_tiles_medcov_gte5,
            "pc_tiles_medcov_gte10": self.pc_tiles_medcov_gte10,
            "pc_tiles_medcov_gte20": self.pc_tiles_medcov_gte20,
            "pc_tiles_medcov_gte50": self.pc_tiles_medcov_gte50,
            "pc_tiles_medcov_gte100": self.pc_tiles_medcov_gte100,
            "pc_tiles_medcov_gte200": self.pc_tiles_medcov_gte200,
        }

class TemporaryMajoraArtifactMetric_Dehum(TemporaryMajoraArtifactMetric):
    #TODO prop dropped, pop n_hits etc
    total_dropped = models.PositiveIntegerField()
    n_hits = models.PositiveIntegerField()
    n_clipped = models.PositiveIntegerField()
    n_known = models.PositiveIntegerField()
    n_collateral = models.PositiveIntegerField()
    # TODO TemporaryMajoraArtifactMetric_Dehum_Record for individual ref-count pairs

    @property
    def metric_kind(self):
        return 'Dehumanisation'


class DigitalResourceNode(MajoraArtifactGroup):
    node_name = models.CharField(max_length=128)
    # ip address
    # ssh key etc.

    def __str__(self):
        return "Node " + self.node_name
    @property
    def group_kind(self):
        return 'Digital Resource Node'
    @property
    def path(self):
        return self.name
    @property
    def name(self):
        return self.node_name
    @property
    def current_name(self):
        return self.name + ':/'

#TODO Need unique combination of parent/name
class DigitalResourceGroup(MajoraArtifactGroup):
    current_name = models.CharField(max_length=512, blank=True, null=True)

    @property
    def group_kind(self):
        return 'Digital Resource Group'
    @property
    def name(self):
        return self.current_name
    @property
    def path(self):
        return "/".join([g.current_name for g in self.hierarchy])



class DigitalResourceArtifact(MajoraArtifact):
    #current_node = models.ForeignKey('Node')
    current_path = models.CharField(max_length=1024, blank=True, null=True) # TODO quick fix to get files quickly

    current_name = models.CharField(max_length=512, db_index=True)
    current_hash = models.CharField(max_length=64)
    current_size = models.BigIntegerField(default=0)
    ghost = models.BooleanField(default=False) # is deleted

    current_extension = models.CharField(max_length=48, default="")
    current_kind = models.CharField(max_length=48, default="File")

    @classmethod
    def construct_test_object(cls):
        file_id = str(uuid.uuid4())
        return cls(
            id = file_id,
            dice_name = file_id,
            current_path = "/path/to/file/hoot.txt",
            current_name = "hoot.txt",
            current_hash = "d41d8cd98f00b204e9800998ecf8427e",
            current_size = 0,
        )

    def get_serializer(self):
        from . import serializers
        return serializers.DigitalResourceArtifactSerializer

    def as_struct(self):
        return {
            "current_path": self.current_path,
            "current_name": self.current_name,
            "current_hash": self.current_hash,
            "current_size": self.current_size,
            "current_kind": self.current_kind,
            "metadata": self.get_metadata_as_struct(),
            "metrics": self.get_metrics_as_struct(),
        }

    def make_path(self, no_node=False):
        if no_node:
            if self.primary_group:
                s = self.primary_group.path + '/' + self.current_name
                try:
                    return s.split(":/")[1]
                except:
                    return s
            else:
                return self.current_name
        else:
            if self.primary_group:
                return self.primary_group.path + '/' + self.current_name
            else:
                return '?/.../' + self.current_name
    @property
    def path(self):
        return self.make_path()
    @property
    def artifact_kind(self):
        return 'Digital Resource'
    @property
    def name(self):
        return self.current_name
    @property
    def clones(self):
        """Return other Resources who share the current_hash, that are not the current Resource, or ghosted."""
        return DigitalResourceArtifact.objects.filter(
                current_hash = self.current_hash,
                ghost = False
        ).exclude(
                id = self.id
        )

    @property
    def process_tree_bioinf(self):
        tree = self.process_tree
        ret = []
        for t in tree:
            if t.process_kind.startswith("Bioinformatics") or t.process_kind == "Sequencing":
                ret.append(t)
        return reversed(ret)

    @property #TODO dont like this but need to be fast, ideally pass the artifact to fixed_data function that defines this?
    def cogtemp_get_qc(self):
        try:
            return self.metadata.filter(meta_tag='cog', meta_name='qc')[0].value
        except:
            return None
    @property
    def cogtemp_get_public(self):
        try:
            return self.metadata.filter(meta_tag='cog', meta_name='public')[0].value
        except:
            return None


    @classmethod
    def sorto(cls, a):
        return sorted(a, key=lambda x: x.current_name)

#TODO this seems like a nice idea on paper but sounds like it will lead to a lifetime of making models for different file formats
#class BasecalledSequenceFile(DigitalResourceArtifact):
#    sequencing = models.ForeignKey("DNASequencingProcess", blank=True, null=True, on_delete=models.PROTECT, related_name="called_reads")
#    basecalling = models.ForeignKey("AbstractBioinformaticsProcess", blank=True, null=True, on_delete=models.PROTECT, related_name="called_reads")

class TubeContainerGroup(MajoraArtifactGroup):

    container_type = models.CharField(max_length=24)
    contains_tubes = models.BooleanField(default=False)

    dimension_x = models.PositiveSmallIntegerField()
    dimension_y = models.PositiveSmallIntegerField()
    #dimension_z = models.PositiveSmallIntegerField(blank=True, default=0)
    #total_slots = models.PositiveSmallIntegerField()

    parent_x = models.PositiveSmallIntegerField()
    parent_y = models.PositiveSmallIntegerField()
    #parent_z = models.PositiveSmallIntegerField(blank=True, default=0)

    # labelled boolean
    # labelling scheme version number

    def __str__(self):
        return '%s (%s)' % (self.dice_name, self.container_type)
    @property
    def group_kind(self):
        return 'Tube Container'
    @property
    def name(self):
        return self.dice_name
    @property
    def full_name(self):
        if self.parent_group:
            return "%s (%s)" % (self.dice_name, str(self.position))
        return self.name
    @property
    def position(self):
        if self.parent_group:
            if self.parent_group.dimension_x == 1:
                return self.parent_y
            elif self.parent_group.dimension_y == 1:
                return self.parent_x
            else:
                return "%d, %d" % (self.parent_y, self.parent_x)
        return '?'
    @property
    def dimensions_y(self):
        return range(self.dimension_y)
    @property
    def dimensions_x(self):
        return range(self.dimension_x)
    @property
    def grid(self):
        a = [ [ None for i in self.dimensions_y ] for j in self.dimensions_x ]
        if self.contains_tubes:
            for d_x in self.dimensions_x:
                for d_y in self.dimensions_y:
                    #TODO Could probably just order the children instead of querying each slot
                    a[d_x][d_y] = TubeArtifact.objects.filter(primary_group=self.id, container_y=d_y+1, container_x=d_x+1).first()
        else:
            for d_x in self.dimensions_x:
                for d_y in self.dimensions_y:
                    a[d_x][d_y] = TubeContainerGroup.objects.filter(parent_group=self.id, parent_y=d_y+1, parent_x=d_x+1).first()
                    #TODO Could probably just order the children instead of querying each slot
        return a


class TubeArtifact(MajoraArtifact):
    container_x = models.PositiveSmallIntegerField()
    container_y = models.PositiveSmallIntegerField()
    storage_medium = models.CharField(max_length=24)

    tube_form = models.CharField(max_length=48, blank=True, null=True)
    sample_form = models.CharField(max_length=48, blank=True, null=True)

    lid_label = models.CharField(max_length=24, blank=True, null=True)
    # dicewareversion / labelersion

    @classmethod
    def construct_test_object(cls):
        tube_id = str(uuid.uuid4())
        return cls(
            id = tube_id,
            dice_name = "majora-test-tube",
            container_x = 0,
            container_y = 0,
            storage_medium = "",
        )

    @property
    def artifact_kind(self):
        return 'Sample Tube'
    @property
    def name(self):
        return self.dice_name
    @property
    def clones(self):
        #TODO Return Tubes that have not been modified since an Aliquot event that links to this Tube
        return []

    @property
    def samples(self):
        #return [r.in_artifact.root_artifact for r in self.process_history if type(r.in_artifact) == TubeArtifact]
        if self.n_samples > 1:
            return [r.in_artifact for r in self.process_history if r.in_artifact and type(r.in_artifact) == BiosampleArtifact]
        else:
            try:
                return [self.root_artifact]
            except:
                return None
    @property
    def sample(self):
        if self.n_samples > 1:
            return [r.in_artifact for r in self.process_history if r.in_artifact and type(r.in_artifact) == BiosampleArtifact]
        else:
            try:
                return self.root_artifact
            except:
                return None
    @property
    def n_samples(self):
        return len([r.in_artifact for r in self.process_history if r.in_artifact and type(r.in_artifact) == BiosampleArtifact])
    @property
    def box(self):
        return self.primary_group
    @property
    def position(self):
        if self.primary_group:
            if self.primary_group.dimension_x == 1:
                return self.container_y
            elif self.primary_group.dimension_y == 1:
                return self.container_x
            else:
                return "%d, %d" % (self.container_x, self.container_y)
        return '?'
    @property
    def location(self):
        a = []
        if self.primary_group:
            h = self.primary_group.hierarchy
            a.append(h[0].name)
            a.extend(str(x.position) for x in h[1:])
        a.append(str(self.position))
        return " // ".join(a)

class BiosampleArtifact(MajoraArtifact):
    root_sample_id = models.CharField(max_length=48, blank=True, null=True)
    sender_sample_id = models.CharField(max_length=48, blank=True, null=True)
    central_sample_id = models.CharField(max_length=48, blank=True, null=True, unique=True)

    sample_type_collected = models.CharField(max_length=24, blank=True, null=True)        #THIS should be a lookup
    sample_site = models.CharField(max_length=24, blank=True, null=True)        #THIS should be a lookup
    sample_type_current = models.CharField(max_length=24, blank=True, null=True)

    sample_longitude = models.PositiveSmallIntegerField(default=0)
    sample_batch = models.PositiveSmallIntegerField(default=0)
    sample_batch_longitude = models.PositiveSmallIntegerField(default=0)

    sample_orig_id = models.CharField(max_length=24, blank=True, null=True) # deprecated
    secondary_identifier = models.CharField(max_length=256, blank=True, null=True) # deprecated
    secondary_accession = models.CharField(max_length=256, blank=True, null=True) # deprecated
    taxonomy_identifier = models.CharField(max_length=24, blank=True, null=True)

    root_biosample_source_id = models.CharField(max_length=48, blank=True, null=True)

    class Meta:
        permissions = [
            ("force_add_biosampleartifact", "Can forcibly add a biosample artifact to Majora"),
        ]

    @classmethod
    def construct_test_object(cls):
        sample_id = str(uuid.uuid4())
        return cls(
            id = sample_id,
            central_sample_id = "ZEAL-HOOT-12345",
            dice_name = "ZEAL-HOOT-12345",
        )

    @property
    def artifact_kind(self):
        return 'Biosample'
    def get_serializer(self):
        from . import serializers
        return serializers.BiosampleArtifactSerializer
    @classmethod
    def get_resty_serializer(cls):
        from . import resty_serializers
        return resty_serializers.RestyBiosampleArtifactSerializer
    @property
    def name(self):
        if self.dice_name:
            if self.sample_orig_id:
                return '%s (%s)' % (self.dice_name, self.sample_orig_id)
            else:
                return self.dice_name
        else:
            return self.central_sample_id

    def as_struct(self):

        ret = {
            "central_sample_id": self.central_sample_id,
            #"sender_sample_id": self.sender_sample_id,
            "root_sample_id": self.root_sample_id,
            "sample_type_collected": self.sample_type_collected,
            "sample_type_received": self.sample_type_current,
            "swab_site": self.sample_site,

            "published_as": ",".join([pag.published_name for pag in self.get_pags(include_suppressed=True)]),
            "metadata": self.get_metadata_as_struct(),
            "metrics": self.get_metrics_as_struct(),
            "root_biosample_source_id": self.root_biosample_source_id,
        }
        collection = {}
        if self.created:
            collection = self.created.as_struct()

        ret.update(collection)
        return ret



    @property
    def source(self):
        return self.primary_group

class BiosampleSource(MajoraArtifactGroup):
    source_type = models.CharField(max_length=24)        #TODO lookup

    secondary_id = models.CharField(max_length=48, blank=True, null=True)

    def __str__(self):
        return '%s' % self.dice_name
    @property
    def group_kind(self):
        return 'Biosample Source'
    @property
    def name(self):
        return str(self.dice_name)

    def as_struct(self):
        return {
            "source_type": self.source_type,
            "biosample_source_id": self.dice_name,
        }

class MajoraArtifactProcessRecord(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    process = models.ForeignKey('MajoraArtifactProcess', on_delete=models.CASCADE, related_name="records")

    bridge_artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, related_name='bridge_process', on_delete=models.CASCADE)
    bridge_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, related_name='bridge_process', on_delete=models.CASCADE)

    in_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, related_name='before_process', on_delete=models.CASCADE)
    in_artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, related_name='before_process', on_delete=models.CASCADE)
    out_artifact= models.ForeignKey('MajoraArtifact', blank=True, null=True, related_name='after_process', on_delete=models.CASCADE)
    out_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, related_name='after_process', on_delete=models.CASCADE)

class MajoraArtifactProcess(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    when = models.DateTimeField(blank=True, null=True)
    #when_time_valid = models.BooleanField()
    who = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)
    #howseen? eg. manual entry, LIMS API update...
    group = models.ForeignKey('MajoraArtifactProcessGroup', on_delete=models.PROTECT, related_name="processes", blank=True, null=True) #TODO do we really need this

    hook_name = models.CharField(max_length=256, blank=True, null=True, unique=True)

    majora_timestamp = models.DateTimeField(blank=True, null=True, default=timezone.now)

    class Meta:
        ordering = ["-when"]

    @property
    def process_kind(self):
        return 'Artifact Process'
    @property
    def kind(self):
        return self.process_kind
    @property
    def short_name(self):
        return self.process_kind
    @property
    def long_name(self):
        return self.process_kind
    @property
    def n_records(self):
        return self.records.count()

    @staticmethod
    def get_groups(proc_list):
        groups = {}
        for a in proc_list:
            if a.n_records == 0:
                continue
            cls = a.__class__
            if cls not in groups:
                groups[cls] = []
            groups[cls].append(a)
        return groups

    @property
    def ordered_artifacts(self):
        ret = {}
        for record in self.records.all().prefetch_related('in_artifact'):
            if record.in_group:
                if record.in_group.kind not in ret:
                    ret[record.in_group.kind] = set([])
                ret[record.in_group.kind].add(record.in_group)
            if record.in_artifact:
                if record.in_artifact.kind not in ret:
                    ret[record.in_artifact.kind] = set([])
                ret[record.in_artifact.kind].add(record.in_artifact)
        return ret


class MajoraArtifactProcessGroup(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    dice_name = models.CharField(max_length=48, blank=True, null=True, unique=True) 
    meta_name = models.CharField(max_length=48, blank=True, null=True) # TODO force unique?

    root_group = models.ForeignKey('MajoraArtifactProcessGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="process_leaves")
    parent_group = models.ForeignKey('MajoraArtifactProcessGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="process_groups")
    groups = models.ManyToManyField('MajoraArtifactProcessGroup', related_name="tagged_groups", blank=True) # represents 'tagged' ResourceGroups

    def __str__(self):
        return self.name
    @property
    def name(self):
        if self.meta_name:
            return self.meta_name
        return str(self.id)
    @property
    def n_processes_t(self):
        count = self.n_processes
        for g in self.process_groups.all():
            count += g.n_processes
        return count
    @property
    def n_groups_t(self):
        count = self.n_groups
        for g in self.process_groups.all():
            count += g.n_groups
        return count
    @property
    def process_groups_tree(self):
        a = []
        if self.process_groups.count() > 0:
            a.extend(self.process_groups.all())
        for g in self.process_groups.all():
            a.extend(g.process_groups_tree)
        return a
    @property
    def process_tree(self):
        a = []
        if self.processes.count() > 0:
            a.extend(self.processes.all())
        for g in self.process_groups.all():
            a.extend(g.process_tree)
        return a
    @property
    def n_groups(self):
        return self.process_groups.count()
    @property
    def n_processes(self):
        return self.processes.count()

    @property
    def hierarchy(self):
        tree = []
        tail = self
        while tail:
            tree.append(tail)
            tail = tail.parent_group
        tree.reverse()
        return tree

    def get_metadatum(self, tag, name):
        m = self.metadata.filter(meta_tag=tag, meta_name=name)
        if m.count() > 0:
            return m

        tail = self.parent_group
        while tail:
            m = tail.metadata.filter(meta_tag=tag, meta_name=name, inheritable=True)
            if m.count() > 0:
                return m
            tail = tail.parent_group

        return m


class MajoraArtifactProcessTest(MajoraArtifactProcess):
    test_message = models.CharField(max_length=256)
    test_user = models.CharField(max_length=24)

    @property
    def process_kind(self):
        return 'Artifact Test Process'

class MajoraArtifactProcessRecordTest(MajoraArtifactProcessRecord):
    test_message = models.CharField(max_length=256)


class MajoraArtifactProcessComment(PolymorphicModel):
    process = models.ForeignKey('MajoraArtifactProcess', on_delete=models.PROTECT, related_name="comments")
    comment = models.TextField()
    when = models.DateTimeField(blank=True, null=True)
    who = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        ordering = ["-when"]

class MajoraArtifactProcessRecordComment(PolymorphicModel):
    record = models.ForeignKey('MajoraArtifactProcessRecord', on_delete=models.PROTECT, related_name="comments")
    comment = models.TextField()
    when = models.DateTimeField(blank=True, null=True)
    who = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        ordering = ["-when"]

class MajoraArtifactQuarantinedProcess(MajoraArtifactProcess):
    @property
    def process_kind(self):
        return 'Quarantined'
    note = models.CharField(max_length=255)
class MajoraArtifactQuarantinedProcessRecord(MajoraArtifactProcessRecord):
    note = models.CharField(max_length=255)

class MajoraArtifactUnquarantinedProcess(MajoraArtifactProcess):
    @property
    def process_kind(self):
        return 'Unquarantined'
    note = models.CharField(max_length=255)
class MajoraArtifactUnquarantinedProcessRecord(MajoraArtifactProcessRecord):
    note = models.CharField(max_length=255)

class BiosourceSamplingProcess(MajoraArtifactProcess):
    @property
    def process_kind(self):
        return 'Sample Collection'

    collection_date = models.DateField(blank=True, null=True)
    received_date = models.DateField(blank=True, null=True)
    submitted_by = models.CharField(max_length=100, blank=True, null=True)
    submission_org = models.ForeignKey("Institute", blank=True, null=True, on_delete=models.SET_NULL, related_name="submitted_sample_records")
    submission_user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="submitted_sample_records")

    source_age = models.PositiveIntegerField(blank=True, null=True)
    source_sex = models.CharField(max_length=10, blank=True, null=True)

    collected_by = models.CharField(max_length=100, blank=True, null=True)
    collection_org = models.ForeignKey("Institute", blank=True, null=True, on_delete=models.SET_NULL, related_name="collected_sample_records") # deprecated

    collection_location_country = models.CharField(max_length=100, blank=True, null=True)
    collection_location_adm1 = models.CharField(max_length=100, blank=True, null=True)
    collection_location_adm2 = models.CharField(max_length=100, blank=True, null=True)
    private_collection_location_adm2 = models.CharField(max_length=100, blank=True, null=True)

    def get_source_age(self):
        if self.source_age:
            return self.source_age
        else:
            return "[Age:?]"
    def get_source_sex(self):
        if self.source_sex:
            return self.source_sex
        else:
            return "[Sex:?]"

    def as_struct(self):
        biosample_sources = []
        for record in self.records.all():
            if record.in_group and record.in_group.kind == "Biosample Source":
                biosample_sources.append(record.in_group.as_struct())

        is_surveillance = ""
        pillar = ""
        if hasattr(self, "coguk_supp"):
            if self.coguk_supp.is_surveillance:
                is_surveillance = "Y"
            elif self.coguk_supp.is_surveillance is False:
                is_surveillance = "N"
            else:
                is_surveillance = ""
            pillar = self.coguk_supp.collection_pillar

        return {
            "collection_date": self.collection_date.strftime("%Y-%m-%d") if self.collection_date else None,
            "received_date": self.received_date.strftime("%Y-%m-%d") if self.received_date else None,
            "submission_user": self.submission_user.username if self.submission_user else None,
            "submission_org": self.submission_org.name if self.submission_org else None,
            "submission_org_code": self.submission_org.code if self.submission_org else None,

            "source_sex": self.source_sex,
            "source_age": self.source_age,

            "collected_by": "",

            "adm0": self.collection_location_country,
            "adm1": self.collection_location_adm1,
            "adm2": self.collection_location_adm2,
            "adm2_private": self.private_collection_location_adm2,

            "is_surveillance": is_surveillance,
            "collection_pillar": pillar,

            "biosample_sources": biosample_sources,
        }


class BiosourceSamplingProcessRecord(MajoraArtifactProcessRecord):
    pass

class BiosampleExtractionProcess(MajoraArtifactProcess):
    @property
    def process_kind(self):
        return 'Sample Extraction'
    extraction_method = models.CharField(max_length=128)

class BiosampleExtractionProcessRecord(MajoraArtifactProcessRecord):
    pass


class LabCheckinProcess(MajoraArtifactProcess):
    originating_site = models.CharField(max_length=512)
    originating_user = models.CharField(max_length=64)
    originating_mail = models.EmailField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    @property
    def process_kind(self):
        return 'Sample Check-In'

    def listing(self):
        return self.records.all().order_by("labcheckinprocessrecord__accepted")

    def damaged(self):
        return self.records.filter(labcheckinprocessrecord__damaged=True)
    def unexpected(self):
        return self.records.filter(labcheckinprocessrecord__unexpected=True)
    def missing(self):
        return self.records.filter(labcheckinprocessrecord__missing=True)
    def confusing(self):
        return self.records.filter(labcheckinprocessrecord__confusing=True)
    def accepted(self):
        return self.records.filter(labcheckinprocessrecord__accepted=True)


#TODO this should be once status
class LabCheckinProcessRecord(MajoraArtifactProcessRecord):
    damaged = models.BooleanField(default=False)
    unexpected = models.BooleanField(default=False)
    missing = models.BooleanField(default=False)
    accepted = models.BooleanField(default=True)
    confusing = models.BooleanField(default=False)


class DigitalResourceCommandPipelineGroup(MajoraArtifactProcessGroup):
    pipe_name = models.CharField(max_length=48)
    orchestrator = models.CharField(max_length=24)

    @property
    def group_kind(self):
        return 'Pipeline'
    @property
    def name(self):
        return '%s %s' % (self.pipe_name, self.orchestrator)

class DigitalResourceCommandGroup(MajoraArtifactProcessGroup):
    group_name = models.CharField(max_length=48)

    @property
    def name(self):
        return "%s:%s" % (str(self.id)[:8], self.group_name)

class DigitalResourceCommand(MajoraArtifactProcess):
    cmd_str = models.CharField(max_length=512)
    return_code = models.SmallIntegerField(blank=True, null=True)

    group_order = models.PositiveSmallIntegerField(default=0)

    #NOTE Could eventually migrate User to an actual User model,
    #     additionally it could be abstracted to the eventual CommandGroup model
    #user = models.CharField(max_length=32)

    queued_at   = models.DateTimeField()
    started_at  = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    @property
    def process_kind(self):
        return 'Command'
    @property
    def short_name(self):
        return str(self.cmd_str)[:8] + '...'
    @property
    def long_name(self):
        return self.cmd_str

class DigitalResourceCommandRecord(MajoraArtifactProcessRecord):
    before_hash = models.CharField(max_length=64)
    before_size = models.BigIntegerField(default=0)
    after_hash = models.CharField(max_length=64)
    after_size = models.BigIntegerField(default=0)
    effect_status = models.CharField(max_length=1)


#TODO could fold these in to a new User class, along with group permissions
class Favourite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="favourites")
    group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="favourited")
    pgroup = models.ForeignKey('MajoraArtifactProcessGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="favourited")

    @staticmethod
    def group_groups(fav_list):
        groups = {}
        for a in fav_list:
            cls = a.group.__class__
            if cls not in groups:
                groups[cls] = []
            groups[cls].append(a.group)
        return groups

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    institute = models.ForeignKey("Institute", blank=True, null=True, on_delete=models.SET_NULL)
    ssh_key = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=128, default=uuid.uuid4)

    slack_id = models.CharField(max_length=24, blank=True, null=True)
    slack_verified = models.BooleanField(default=False)

    is_site_approved = models.BooleanField(default=False)

    is_revoked = models.BooleanField(default=False)
    revoked_reason = models.CharField(max_length=128, blank=True, null=True)
    revoked_timestamp = models.DateTimeField(blank=True, null=True)

    class Meta:
        permissions = [
            ("can_revoke_profiles", "Can revoke the access of any user"),
            ("can_approve_profiles", "Can approve new user profiles for their organisation"),
            ("can_approve_profiles_via_bot", "Can approve new user profiles for any organisation via the bot system"),
            ("can_grant_profile_permissions", "Can grant other users permissions that change the Profile system"),
            #("can_get_sshkey_via_token", "Can get SSH keys for users via the token system"),
            #("can_get_profiles_via_token", "Can get basic Profile information via the token system"),
            ("can_wildcard_sequencing_runs", "Can use the wildcard character to unroll all sequencing runs in Majora"), # do not assign this to any non-elan users
            ("can_sudo_as_other_user", "Can elevate permissions to impersonate other users"),
        ]

    def __str__(self):
        return self.user.username

    @property
    def last_action(self):
        action = self.user.actions.order_by("-timestamp").first()
        if action:
            return action.timestamp

    def get_active_api_keys(self):
        return [k for k in self.api_keys.all() if k.is_active]

    def get_generated_api_keys(self):
        return self.api_keys.all()

    def get_available_api_keys(self):
        return ProfileAPIKeyDefinition.objects.filter(Q(permission__isnull=True) | Q(permission__in=self.user.user_permissions.all())).exclude(id__in=self.get_generated_api_keys().values('key_definition__id'))

    @property
    def tatl_page_requests(self):
        return self.user.requests.filter(is_api=False).order_by('-timestamp')[:25]

    @property
    def tatl_api_requests(self):
        return self.user.requests.filter(is_api=True).order_by('-timestamp')[:25]

    @property
    def oauth2_grant_requests(self):
        return self.user.oauth2_provider_grant.order_by('-created')[:25]


#TODO samstudio8 - future versions of the agreement model might consider
# properties of the user model that determine applicability to sign an agreement
# eg: not showing scottish users agreements for english data
class ProfileAgreementDefinition(models.Model):
    slug = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=96)
    description = models.CharField(max_length=256)
    content = models.TextField()
    version = models.PositiveIntegerField(default=1)
    proposal_timestamp = models.DateTimeField()
    effective_timestamp = models.DateTimeField(null=True, blank=True)
    is_terminable = models.BooleanField(default=True)

#TODO Store this in Tatl?
class ProfileAgreement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # 
    agreement = models.ForeignKey('ProfileAgreementDefinition', on_delete=models.PROTECT)
    profile = models.ForeignKey('Profile', on_delete=models.PROTECT, related_name="agreements")
    signature_timestamp = models.DateTimeField()
    is_terminated = models.BooleanField(default=False)
    terminated_reason = models.CharField(max_length=24, blank=True, null=True)
    terminated_timestamp = models.DateTimeField(blank=True, null=True)

class ProfileAppPassword(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.PROTECT, related_name="app_passwords")
    application = models.ForeignKey(OAUTH_APPLICATION_MODEL, on_delete=models.PROTECT)
    password = models.CharField(max_length=64)

    validity_start = models.DateTimeField(null=True, blank=True)
    validity_end = models.DateTimeField(null=True, blank=True)

    #was_revoked = models.BooleanField(default=False)
    #revoked_reason = models.CharField(max_length=24, blank=True, null=True)

class ProfileAPIKeyDefinition(models.Model):
    key_name = models.CharField(max_length=48, unique=True)
    permission = models.ForeignKey(Permission, blank=True, null=True, on_delete=models.PROTECT)
    is_service_key = models.BooleanField()
    is_read_key = models.BooleanField()
    is_write_key = models.BooleanField()
    lifespan = models.DurationField()

class ProfileAPIKey(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.PROTECT, related_name="api_keys")
    key_definition = models.ForeignKey('ProfileAPIKeyDefinition', on_delete=models.PROTECT)
    key = models.CharField(max_length=128, default=uuid.uuid4)
    validity_start = models.DateTimeField(null=True, blank=True)
    validity_end = models.DateTimeField(null=True, blank=True)

    was_revoked = models.BooleanField(default=False)
    revoked_reason = models.CharField(max_length=24, blank=True, null=True)

    @property
    def is_expired(self):
        now = timezone.now()
        if now < self.validity_start or now > self.validity_end:
            return True
        return False

    @property
    def is_active(self):
        return not self.is_expired

#TODO How to properly link models?
#TODO MajoraCoreObject could be inherited by artifact, group etc.
class MajoraMetaRecord(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.CASCADE, related_name="metadata")
    group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.CASCADE, related_name="metadata")
    process = models.ForeignKey('MajoraArtifactProcess', blank=True, null=True, on_delete=models.CASCADE, related_name="metadata")
    pgroup = models.ForeignKey('MajoraArtifactProcessGroup', blank=True, null=True, on_delete=models.CASCADE, related_name="metadata")

    meta_tag = models.CharField(max_length=64)
    meta_name = models.CharField(max_length=64)

    value_type = models.CharField(max_length=48)
    value = models.CharField(max_length=128, blank=True, null=True)

    link = models.BooleanField(default=False)
    inheritable = models.BooleanField(default=True)
    timestamp = models.DateTimeField(blank=True, null=True)

    restricted = models.BooleanField(default=False)

    @property
    def translate(self):
        if self.link:
            if self.value_type == "TubeArtifact":
                return self.artifact
        return self.value

class Institute(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

    ena_opted = models.BooleanField(default=True)
    ena_assembly_opted = models.BooleanField(default=False)

    gisaid_opted = models.BooleanField(default=False)
    gisaid_user = models.CharField(max_length=100, null=True, blank=True)
    gisaid_mail = models.EmailField(null=True, blank=True)
    gisaid_lab_name = models.CharField(max_length=512, null=True, blank=True)
    gisaid_lab_addr = models.CharField(max_length=512, null=True, blank=True)
    gisaid_list = models.CharField(max_length=2048, null=True, blank=True)

    def __str__(self):
        return "%s: %s" % (self.code, self.name)

    class Meta:
        permissions = [
            ("can_register_institute", "Can register a new institute in Majora"),
        ]

class InstituteCredit(models.Model):
    institute = models.ForeignKey('Institute', on_delete=models.CASCADE, related_name="credits")
    credit_code = models.CharField(max_length=24, unique=True)

    #TODO fuckit we will just fix the namespace for now ffs
    #apply_by_namespace = models.CharField(max_length=64)
    #apply_by_name = models.CharField(max_length=64)

    lab_name = models.CharField(max_length=512, null=True, blank=True)
    lab_addr = models.CharField(max_length=512, null=True, blank=True)
    lab_list = models.CharField(max_length=2048, null=True, blank=True)

class County(models.Model):
    country_code = models.CharField(max_length=10)
    code = models.CharField(max_length=10, blank=True, null=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


'''
class LiquidArtifact(MajoraArtifact):
    container_x = models.PositiveSmallIntegerField()
    container_y = models.PositiveSmallIntegerField()

    tube_type = models.CharField(max_length=48, blank=True, null=True)
    sample_type = models.CharField(max_length=48, blank=True, null=True)
    storage_medium = models.CharField(max_length=24)

    lid_label = models.CharField(max_length=24, blank=True, null=True)
    # dicewareversion / labelersion

    #biosample = models.ForeignKey("BiosampleArtifact", blank=True, null=True, on_delete=models.PROTECT, related_name="aliquots")
    #pool = models.BooleanField(default=False)

    biosamples = models.ManyToManyField('BiosampleArtifact', related_name="biosamples", blank=True, null=True)

    @property
    def artifact_kind(self):
        return 'Sample Aliquot'
    @property
    def name(self):
        return self.dice_name
'''

class LibraryArtifact(MajoraArtifact):
    layout_config = models.CharField(max_length=24, blank=True, null=True)
    layout_read_length = models.PositiveIntegerField(blank=True, null=True)
    layout_insert_length = models.PositiveIntegerField(blank=True, null=True)

    seq_kit = models.CharField(max_length=96, blank=True, null=True)
    seq_protocol = models.CharField(max_length=96, blank=True, null=True)

    @classmethod
    def construct_test_object(cls):
        return cls(
            dice_name = "HOOT-LIB-12345",
        )

    @property
    def artifact_kind(self):
        return 'Library'

    def as_struct(self, deep=True):
        biosamples = []

        if self.created and deep:
            for record in self.created.records.all().prefetch_related('in_artifact'):
                if record.in_artifact and record.in_artifact.kind == "Biosample":
                    rec = record.in_artifact.as_struct()
                    rec.update({
                        "library_strategy": record.library_strategy,
                        "library_source": record.library_source,
                        "library_selection": record.library_selection,
                        "library_adaptor_barcode": record.barcode,
                        "library_protocol": record.library_protocol,
                        "library_primers": record.library_primers,
                    })
                    biosamples.append(rec)
        ret = {
            "library_name": self.dice_name,
            "library_layout_config": self.layout_config,
            "layout_read_length": self.layout_read_length,
            "layout_insert_length": self.layout_insert_length,
            "library_seq_kit": self.seq_kit,
            "library_seq_protocol": self.seq_protocol,

            "metadata": self.get_metadata_as_struct(),

            "biosamples": biosamples,
        }
        return ret

class LibraryPoolingProcess(MajoraArtifactProcess):
    @property
    def process_kind(self):
        return 'Pooling'
class LibraryPoolingProcessRecord(MajoraArtifactProcessRecord):
    barcode = models.CharField(max_length=24, blank=True, null=True)
    volume = models.FloatField(blank=True, null=True)
    library_strategy = models.CharField(max_length=24, blank=True, null=True)
    library_source = models.CharField(max_length=24, blank=True, null=True)
    library_selection = models.CharField(max_length=24, blank=True, null=True)

    #TODO These belong in a proper process before pooling but we don't have time
    library_primers = models.CharField(max_length=48, blank=True, null=True)
    library_protocol = models.CharField(max_length=48, blank=True, null=True)

    #NOTE samstudio8 20210114
    # This REALLY does not belong here but there isn't really anywhere else
    # suitable for it to go. Sorry about that.
    # See https://github.com/COG-UK/dipi-group/issues/12
    sequencing_org_received_date = models.DateField(blank=True, null=True)


class DNASequencingProcessGroup(MajoraArtifactProcessGroup):
    experiment_name = models.CharField(max_length=128)

class DNASequencingProcess(MajoraArtifactProcess):
    run_name = models.CharField(max_length=128, unique=True)
    run_group = models.CharField(max_length=128, blank=True, null=True)

    instrument_make = models.CharField(max_length=64)
    instrument_model = models.CharField(max_length=48)
    flowcell_type = models.CharField(max_length=48, blank=True, null=True)
    flowcell_id = models.CharField(max_length=48, blank=True, null=True)

    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)

    @classmethod
    def get_resty_serializer(cls):
        from . import resty_serializers
        return resty_serializers.RestyDNASequencingProcessSerializer

    @property
    def process_kind(self):
        return 'Sequencing'

    def as_struct(self, deep=True):

        libraries = []
        if deep:
            for record in self.records.all().prefetch_related('in_artifact'):
                if record.in_artifact and record.in_artifact.kind == "Library":
                    libraries.append(record.in_artifact.as_struct())

        return {
            "run_name": self.run_name,
            "run_group": self.run_group,
            "instrument_make": self.instrument_make,
            "instrument_model": self.instrument_model,
            "flowcell_type": self.flowcell_type,
            "flowcell_id": self.flowcell_id,

            "start_time": self.start_time.strftime("%Y-%m-%d %H:%m") if self.start_time else None,
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%m") if self.end_time else None,
            #"duration": None,
            "libraries": libraries,

            "sequencing_uuid": str(self.id),
            "sequencing_org": self.who.profile.institute.name if self.who.profile.institute else None,
            "sequencing_org_code": self.who.profile.institute.code if self.who.profile.institute else None,
            "sequencing_submission_date": self.when.strftime("%Y-%m-%d") if self.when else None,
        }

class DNASequencingProcessRecord(MajoraArtifactProcessRecord):
    pass


class AbstractBioinformaticsProcess(MajoraArtifactProcess):
    pipe_kind = models.CharField(max_length=64, blank=True, null=True) # will eventually need a controlled vocab here
    pipe_name = models.CharField(max_length=96, blank=True, null=True)
    pipe_version = models.CharField(max_length=48, blank=True, null=True)

    @property
    def process_kind(self):
        return 'Bioinformatics: %s' % self.pipe_kind

    @classmethod
    def get_resty_serializer(cls):
        from . import resty_serializers
        return resty_serializers.AbstractBioinformaticsProcessSerializer


class MajoraDataview(models.Model):
    code_name = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=128)
    description = models.CharField(max_length=256)
    entry_point = models.CharField(max_length=128)
    permission = models.ForeignKey(Permission, blank=True, null=True, on_delete=models.PROTECT)

    class Meta:
        permissions = [
            ("can_read_dataview_via_api", "Can read the contents of CONSORTIUM data views via the API"),
            ("can_read_restricted_dataview_via_api", "Can read the contents of RESTRICTED data views via the API"),
        ]

    def __str__(self):
        return "MDV %s" % (self.code_name)

    def get_filters(self):
        super_q = Q()
        for f in self.filters.all():
            filter_v = f.get_filter_value()
            curr_fop = f.filter_field + '__' + f.filter_op
            curr_q = Q(**{curr_fop:filter_v})

            if f.filter_op == "in" and f.filter_type == "list" and None in filter_v:
                curr_fop = f.filter_field + '__isnull'
                curr_q = (curr_q | Q(**{curr_fop:True}))

            super_q = super_q & curr_q
        return super_q

#TODO This looks a lot like the API key, which is also tied to a profile
# but I think it makes sense to keep them separate for now?
class MajoraDataviewUserPermission(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.PROTECT)
    dataview = models.ForeignKey('MajoraDataview', on_delete=models.CASCADE, related_name="viewers")

    validity_start = models.DateTimeField(null=True, blank=True)
    validity_end = models.DateTimeField(null=True, blank=True)

    is_revoked = models.BooleanField(default=False)
    revoked_reason = models.CharField(max_length=24, blank=True, null=True)
    revoked_timestamp = models.DateTimeField(blank=True, null=True)

    @property
    def is_expired(self):
        now = timezone.now()
        if now < self.validity_start or now > self.validity_end:
            return True
        return False

    @property
    def is_active(self):
        return not self.is_expired

class MajoraDataviewSerializerField(models.Model):
    dataview = models.ForeignKey('MajoraDataview', on_delete=models.CASCADE, related_name="fields")
    model_name = models.CharField(max_length=64)
    model_field = models.CharField(max_length=64) #TODO can we ref the actual model?

#TODO We don't need to do anything smart right now, we shall just support a list of combined filters
class MajoraDataviewFilterField(models.Model):
    dataview = models.ForeignKey('MajoraDataview', on_delete=models.CASCADE, related_name="filters")
    filter_field = models.CharField(max_length=64)
    filter_type = models.CharField(max_length=8, choices=[
        ("str", "str"),
        ("int", "int"),
        ("float", "float"),
        ("bool", "bool"),
        ("list", "list"), # user must provide list of comma delmited strings of type:val,type:val...
    ])
    filter_value = models.CharField(max_length=128)
    filter_op = models.CharField(max_length=10, default="exact") #TODO implement proper choices lookup based on Field lookups

    @property
    def filter_field_nice(self):
        return self.filter_field.replace('__', ' > ')

    # :thinking: ...
    def get_filter_value(self):
        if self.filter_type == "list":
            l = []
            for entry in self.filter_value.split(','):
                if len(entry) == 0:
                    continue
                entry_type, entry_val = entry.split(':')

                type_ = getattr(builtins, entry_type)
                if entry_type == "bool":
                    l.append( type_(int(entry_val)) )
                elif entry_type.lower() == "none":
                    l.append(None)
                else:
                    l.append( type_(entry_val) )
            return l
        else:
            type_ = getattr(builtins, self.filter_type)

            # Catch pesky bool case, thanks https://stackoverflow.com/questions/2678770/how-do-i-store-values-of-arbitrary-type-in-a-single-django-model
            if self.filter_type == "bool":
                return type_(int(self.filter_value))
            else:
                return type_(self.filter_value)


from . import receivers

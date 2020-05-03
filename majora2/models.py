import uuid
import os

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.db.models import Q

from . import receivers

from polymorphic.models import PolymorphicModel

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

    @property
    def artifact_kind(self):
        return 'Artifact'
    @property
    def kind(self):
        return self.artifact_kind
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
            if not flat:
                if m.meta_tag not in metadata:
                    metadata[m.meta_tag] = {}
                metadata[m.meta_tag][m.meta_name] = m.value
            else:
                metadata["%s.%s" % (m.meta_tag, m.meta_name)] = m.value
        return metadata

    def get_pags(self):
        return self.groups.filter(Q(PublishedArtifactGroup___is_latest=True))

    def as_struct(self):
        return {}

# TODO This will become the MajoraGroup
class MajoraArtifactGroup(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    unique_name = models.CharField(max_length=128, blank=True, null=True, unique=True) #TODO graduate away from meta_name, needs to be project unique rather than global, but it will work here 

    dice_name = models.CharField(max_length=96, blank=True, null=True, unique=True) 
    meta_name = models.CharField(max_length=96, blank=True, null=True) # TODO force unique?

    root_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="descendants")
    parent_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="children")
    groups = models.ManyToManyField('MajoraArtifactGroup', related_name="tagged_groups", blank=True) # represents 'tagged' ResourceGroups
    processes = models.ManyToManyField('MajoraArtifactProcessGroup', related_name="tagged_processes", blank=True) # represents 'tagged' ResourceGroups
    physical = models.BooleanField(default=False)

    def __str__(self):
        return "%s (%s)" % (self.name, self.id)

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
    published_name = models.CharField(max_length=128)
    published_version = models.PositiveIntegerField() #TODO replace this with a custom field that can handle semvar
                                                      # even tempted to ditch this, make MAG top level root model
                                                      # and each version is just a new PAG named with its version
                                                      # then reconstruct path as:  <NAME> / <VERSION>
    #pag_kind = models.CharField()
    published_date = models.DateField()

    is_draft = models.BooleanField(default=False) # ?
    is_latest = models.BooleanField(default=False)
    #replaced_by = models.ForeignKey('PublishedArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="replaces")

    is_public = models.BooleanField(default=False)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    #TODO owner_org?

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["published_name", "is_latest"], name="is_only_published"),
        ]

    def as_struct(self):

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
        }

    @property
    def group_kind(self):
        return "Published Artifact Group"
    @property
    def name(self):
        return self.published_name

# TODO This is a quick and dirty way to toss the accessions we're getting snowed with onto a PAG
# Partly because we just want to be able to quickly count how many PAGs are public, by institute
# I eventually want to move these tags onto the artifacts themselves but this needs more work (as I have big ideas for splitting apart the models for files in particular)
class TemporaryAccessionRecord(models.Model):
    pag = models.ForeignKey('PublishedArtifactGroup', on_delete=models.PROTECT, related_name="accessions")
    #artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.PROTECT)
    service = models.CharField(max_length=64)
    primary_accession = models.CharField(max_length=64)
    secondary_accesison = models.CharField(max_length=64, blank=True, null=True)
    tertiary_accession = models.CharField(max_length=64, blank=True, null=True)

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
    pag = models.ForeignKey('PublishedArtifactGroup', on_delete=models.PROTECT, related_name="quality_groups")
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
    group = models.ForeignKey('PAGQualityReportEquivalenceGroup', on_delete=models.PROTECT, related_name="quality_tests", blank=True, null=True)

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
    artifact = models.ForeignKey('MajoraArtifact', on_delete=models.CASCADE)
    namespace = models.CharField(max_length=64, blank=True, null=True)

    @property
    def kind(self):
        return self.metric_kind
    @property
    def metric_kind(self):
        return 'Metric'

    @property
    def as_struct(self):
        return {}

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
    @property
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
    @property
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

    @property
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

    current_name = models.CharField(max_length=512)
    current_hash = models.CharField(max_length=64)
    current_size = models.BigIntegerField(default=0)
    ghost = models.BooleanField(default=False) # is deleted

    current_extension = models.CharField(max_length=48, default="")
    current_kind = models.CharField(max_length=48, default="File")

    def as_struct(self):
        return {
            "current_path": self.current_path,
            "current_name": self.current_name,
            "current_hash": self.current_hash,
            "current_size": self.current_size,
            "current_kind": self.current_kind,
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

    sample_orig_id = models.CharField(max_length=24, blank=True, null=True)
    sample_type_collected = models.CharField(max_length=24, blank=True, null=True)        #THIS should be a lookup
    sample_site = models.CharField(max_length=24, blank=True, null=True)        #THIS should be a lookup
    sample_type_current = models.CharField(max_length=24, blank=True, null=True)

    sample_longitude = models.PositiveSmallIntegerField(default=0)
    sample_batch = models.PositiveSmallIntegerField(default=0)
    sample_batch_longitude = models.PositiveSmallIntegerField(default=0)

    secondary_identifier = models.CharField(max_length=256, blank=True, null=True)
    secondary_accession = models.CharField(max_length=256, blank=True, null=True)
    taxonomy_identifier = models.CharField(max_length=24, blank=True, null=True)

    @property
    def artifact_kind(self):
        return 'Biosample'
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
            "secondary_identifier": self.secondary_identifier,
            "sample_type_collected": self.sample_type_collected,
            "sample_type_received": self.sample_type_current,
            "swab_site": self.sample_site,
            "secondary_accession": self.secondary_accession,

            "published_as": ",".join([pag.published_name for pag in self.get_pags()]),
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

    hook_name = models.CharField(max_length=256, blank=True, null=True)

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
        for record in self.records.all():
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
    source_category = models.CharField(max_length=64, blank=True, null=True)
    source_setting = models.CharField(max_length=64, blank=True, null=True)

    collected_by = models.CharField(max_length=100, blank=True, null=True)
    collection_org = models.ForeignKey("Institute", blank=True, null=True, on_delete=models.SET_NULL, related_name="collected_sample_records")

    collection_location_country = models.CharField(max_length=100, blank=True, null=True)
    collection_location_adm1 = models.CharField(max_length=100, blank=True, null=True)
    collection_location_adm2 = models.CharField(max_length=100, blank=True, null=True)
    private_collection_location_adm2 = models.CharField(max_length=100, blank=True, null=True)

    sampling_strategy = models.CharField(max_length=64, blank=True, null=True)

    def as_struct(self):
        biosample_sources = []
        for record in self.records.all():
            if record.in_group and record.in_group.kind == "Biosample Source":
                biosample_sources.append(record.in_group.as_struct())

        return {
            "collection_date": self.collection_date.strftime("%Y-%m-%d") if self.collection_date else None,
            "received_date": self.received_date.strftime("%Y-%m-%d") if self.received_date else None,
            "submission_user": self.submission_user.username if self.submission_user else None,
            "submission_org": self.submission_org.name if self.submission_org else None,
            "submission_org_code": self.submission_org.code if self.submission_org else None,

            "source_sex": self.source_sex,
            "source_age": self.source_age,
            "source_category": self.source_category,
            "source_setting": self.source_setting,
            "sampling_strategy": self.sampling_strategy,

            "collected_by": "",

            "adm0": self.collection_location_country,
            "adm1": self.collection_location_adm1,
            "adm2": self.collection_location_adm2,
            "adm2_private": "",

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

    @property
    def translate(self):
        if self.link:
            if self.value_type == "TubeArtifact":
                return self.artifact
        return self.value

class Institute(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

    def __str__(self):
        return "%s: %s" % (self.code, self.name)


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

    seq_kit = models.CharField(max_length=48, blank=True, null=True)
    seq_protocol = models.CharField(max_length=48, blank=True, null=True)

    @property
    def artifact_kind(self):
        return 'Library'

    def as_struct(self):
        biosamples = []

        if self.created:
            for record in self.created.records.all():
                if record.in_artifact and record.in_artifact.kind == "Biosample":
                    rec = record.in_artifact.as_struct()
                    rec.update({
                        "library_strategy": record.library_strategy,
                        "library_source": record.library_source,
                        "library_selection": record.library_selection,
                        "library_adaptor_barcode": record.barcode,
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

    @property
    def process_kind(self):
        return 'Sequencing'

    def as_struct(self):

        libraries = []
        for record in self.records.all():
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
    pass


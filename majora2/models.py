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
    dice_name = models.CharField(max_length=48, blank=True, null=True, unique=True)
    meta_name = models.CharField(max_length=48, blank=True, null=True)
    unique_name = models.CharField(max_length=48, blank=True, null=True, unique=True) #TODO graduate away from meta_name, needs to be project unique rather than global, but it will work here 

    root_artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.PROTECT, related_name="descendants")
    quarantined = models.BooleanField(default=False)

    primary_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="child_artifacts")
    groups = models.ManyToManyField('MajoraArtifactGroup', related_name="tagged_artifacts", blank=True) # represents 'tagged' ResourceGroups

    @property
    def artifact_kind(self):
        return 'Artifact'
    @property
    def name(self):
        return self.meta_name
    @property
    def process_history(self):
        return (self.before_process.all() | self.after_process.all()).order_by('-process__when').get_real_instances()
    @property
    def process_tree(self):
        a = []
        a.extend(self.after_process.all().order_by('-process__when'))
        for proc in a:
            if proc.in_artifact and proc.in_artifact.id != proc.out_artifact.id:# or proc.in_group:
                a.extend(proc.in_artifact.process_tree)
        return a
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
    def created(self):
        return self.process_history[0]
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

"""
class MajoraGroup(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    dice_name = models.CharField(max_length=48, blank=True, null=True, unique=True) 
    meta_name = models.CharField(max_length=48, blank=True, null=True) # TODO force unique?

    root_group = models.ForeignKey('MajoraGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="descendants")
    parent_group = models.ForeignKey('MajoraGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="children")
    groups = models.ManyToManyField('MajoraGroup', related_name="tagged_groups", blank=True) 
    physical = models.BooleanField(default=False)

    def __str__(self):
        return "%s (%s)" % (self.name, self.id)

    @property
    def group_kind(self):
        return 'Group'
    @property
    def name(self):
        if self.meta_name:
            return self.meta_name
        return str(self.id)
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

class MajoraArtifactGroup2(MajoraGroup):
    @property
    def group_kind(self):
        return 'Artifact Group'

class MajoraProcessGroup2(MajoraGroup):
    @property
    def group_kind(self):
        return 'Process Group'

"""
# TODO This will become the MajoraGroup
class MajoraArtifactGroup(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    unique_name = models.CharField(max_length=48, blank=True, null=True, unique=True) #TODO graduate away from meta_name, needs to be project unique rather than global, but it will work here 

    dice_name = models.CharField(max_length=48, blank=True, null=True, unique=True) 
    meta_name = models.CharField(max_length=48, blank=True, null=True) # TODO force unique?

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
    def name(self):
        if self.meta_name:
            return self.meta_name
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

    current_name = models.CharField(max_length=512)
    current_hash = models.CharField(max_length=64)
    current_size = models.BigIntegerField(default=0)
    ghost = models.BooleanField(default=False) # is deleted

    current_extension = models.CharField(max_length=48, default="")
    current_kind = models.CharField(max_length=48, default="File")

    @property
    def path(self):
        return self.primary_group.path + '/' + self.current_name
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

    @classmethod
    def sorto(cls, a):
        return sorted(a, key=lambda x: x.current_name)

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
    sample_orig_id = models.CharField(max_length=24, blank=True, null=True)
    sample_type = models.CharField(max_length=24, blank=True, null=True)        #THIS should be a lookup
    specimen_type = models.CharField(max_length=24, blank=True, null=True)

    sample_longitude = models.PositiveSmallIntegerField(default=0)
    sample_batch = models.PositiveSmallIntegerField(default=0)
    sample_batch_longitude = models.PositiveSmallIntegerField(default=0)

    #NOTE Trying something different, Biosamples almost exclusively come from a sampling event, so let's hard link it here
    collection = models.ForeignKey("BiosourceSamplingProcess", blank=True, null=True, on_delete=models.PROTECT, related_name="biosamples")

    @property
    def artifact_kind(self):
        return 'Biosample'
    @property
    def name(self):
        if self.dice_name:
            return '%s (%s)' % (self.dice_name, self.sample_orig_id)
        else:
            return self.sample_orig_id
    @property
    def source(self):
        return self.primary_group

class BiosampleSource(MajoraArtifactGroup):
    source_type = models.CharField(max_length=24)        #TODO lookup

    def __str__(self):
        return '%s' % self.meta_name
    @property
    def group_kind(self):
        return 'Biosample Source'
    @property
    def name(self):
        return str(self.meta_name)


class MajoraArtifactProcessRecord(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    process = models.ForeignKey('MajoraArtifactProcess', on_delete=models.CASCADE, related_name="records")

    in_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, related_name='before_process', on_delete=models.PROTECT)
    in_artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, related_name='before_process', on_delete=models.PROTECT)
    out_artifact= models.ForeignKey('MajoraArtifact', blank=True, null=True, related_name='after_process', on_delete=models.PROTECT)
    out_group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, related_name='after_process', on_delete=models.PROTECT)

class MajoraArtifactProcess(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #
    when = models.DateTimeField(blank=True, null=True)
    #when_time_valid = models.BooleanField()
    who = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)
    #howseen? eg. manual entry, LIMS API update...
    group = models.ForeignKey('MajoraArtifactProcessGroup', on_delete=models.PROTECT, related_name="processes", blank=True, null=True) #TODO do we really need this

    class Meta:
        ordering = ["-when"]

    @property
    def process_kind(self):
        return 'Artifact Process'
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
    collection_by = models.CharField(max_length=100, blank=True, null=True)

    collection_location_country = models.CharField(max_length=100, blank=True, null=True)
    collection_location_adm0 = models.CharField(max_length=100, blank=True, null=True)
    collection_location_adm1 = models.CharField(max_length=100, blank=True, null=True)


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
    organisation = models.CharField(max_length=100)
    institute = models.ForeignKey("Institute", blank=True, null=True, on_delete=models.SET_NULL)
    ssh_key = models.TextField(blank=True, null=True)

#TODO How to properly link models?
class MajoraMetaRecord(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    artifact = models.ForeignKey('MajoraArtifact', blank=True, null=True, on_delete=models.PROTECT, related_name="metadata")
    group = models.ForeignKey('MajoraArtifactGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="metadata")
    process = models.ForeignKey('MajoraArtifactProcess', blank=True, null=True, on_delete=models.PROTECT, related_name="metadata")
    pgroup = models.ForeignKey('MajoraArtifactProcessGroup', blank=True, null=True, on_delete=models.PROTECT, related_name="metadata")

    meta_tag = models.CharField(max_length=64)
    meta_name = models.CharField(max_length=64)

    value_type = models.CharField(max_length=48)
    value = models.CharField(max_length=128)

    link = models.BooleanField(default=False)
    inheritable = models.BooleanField(default=True)
    timestamp = models.DateTimeField()

    @property
    def translate(self):
        if self.link:
            if self.value_type == "TubeArtifact":
                return self.artifact
        return self.value

class Institute(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import uuid
import os

from django.db import models
from django.db.models import Q


class Node(models.Model):
    """Any device or computer capable of storing a Resource, or executing a Command."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True, db_index=True)

    def __str__(self):
        return "%s (%s)" % (self.name, str(self.id)[-5:])

class ResourceGroup(models.Model):
    # A ResourceGroup could be an entire directory (indeed, that is the minimum),
    # but it could also be a pseudo-folder like group of files that make up a database, or an experiment.
    # A Resource must have a ResourceGroup, but can be attached to other groups as 'tags'.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=512)

    physical = models.BooleanField()
    current_node = models.ForeignKey('Node', blank=True, null=True)
    current_path = models.CharField(max_length=512, blank=True, null=True)
    physical_parent_group = models.ForeignKey('ResourceGroup', blank=True, null=True) # not currently using these

    groups = models.ManyToManyField('ResourceGroup', related_name="tagged_groups") # represents 'tagged' ResourceGroups

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        if self.name:
            return self.name
        else:
            return self.current_path

    @classmethod
    def get_by_path(cls, node_uuid, path):
        return cls.objects.filter(current_node__id = node_uuid, current_path = path).first() #TODO first?

    @property
    def metadata(self):
        #TODO Future, flatten (tag, name) records if they have been 'overwritten'
        return self.metarecord_set.all().order_by('-timestamp')


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    current_node = models.ForeignKey('Node')
    current_path = models.CharField(max_length=512)
    current_hash = models.CharField(max_length=64)
    current_size = models.BigIntegerField(default=0)

    ghost = models.BooleanField(default=False)

    current_master_group = models.ForeignKey('ResourceGroup') # represents the physical directory
    groups = models.ManyToManyField('ResourceGroup', related_name="tagged_resources") # represents 'tagged' ResourceGroups

    @classmethod
    def get_by_path(cls, node_uuid, path):
        return cls.objects.filter(current_node__id = node_uuid, current_path = path, ghost = False).first() #TODO first?

    def __str__(self):
        return "%s (%s:%s)" % (self.full_path, str(self.id)[-5:], self.current_hash[-5:])

    @property
    def full_path(self):
        return "%s:%s" % (self.current_node.name, self.current_path)


    @property
    def basename(self):
        return os.path.basename(self.current_path)

    @property
    def dirname(self):
        return os.path.dirname(self.current_path)

    @property
    def hash_friends(self):
        """Return other Resources who share the current_hash, that are not the current Resource, or ghosted."""
        return Resource.objects.filter(
                current_hash = self.current_hash,
                ghost = False
        ).exclude(
                id = self.id
        )

    @property
    def adjacent_files(self):
        """Return other Resources who share the current directory, that are not ghosted."""
        #TODO Use master_group
        return Resource.objects.filter(
                # current_groups__in = [self.current_master_group],
                current_path__startswith = os.path.dirname(self.current_path),
                ghost= False
        )

    @property
    def ghosts(self):
        return Resource.objects.filter(
                current_path=self.current_path,
                ghost = True,
        ).exclude(
                id = self.id
        )

    @property
    def metadata(self):
        # Flatten (tag, name) records if they have been 'overwritten'
        #TODO There must be a way to do this properly with the queryset
        records = self.metarecord_set.all().order_by('-timestamp')
        seen = {}
        filtered = []
        for r in records:
            if r.meta_tag not in seen:
                seen[r.meta_tag] = {}
            if r.meta_name in seen[r.meta_tag]:
                continue
            seen[r.meta_tag][r.meta_name] = 1
            filtered.append(r)
        return filtered


    @property
    def effects(self):
        return self.commandonresource_set.all().order_by('-command__finished_at', '-command__group_order')

    @property
    def last_effect(self):
        return self.effects.last()

    @property
    def effect_created(self):
        return self.commandonresource_set.filter(effect_status__in = ['N','C']).earliest('command__finished_at')

    @property
    def effect_last_modified(self):
        return self.commandonresource_set.filter(Q(effect_status = 'M')).latest('command__finished_at')
    @property
    def effect_last_used(self):
        return self.commandonresource_set.filter(Q(effect_status = 'U')).latest('command__finished_at')


class Command(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cmd_str = models.CharField(max_length=512)
    return_code = models.SmallIntegerField(blank=True, null=True)

    # group_uuid
    group_order = models.PositiveSmallIntegerField(default=0)

    #NOTE Could eventually migrate User to an actual User model,
    #     additionally it could be abstracted to the eventual CommandGroup model
    user = models.CharField(max_length=32)

    queued_at   = models.DateTimeField()
    started_at  = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)


    def __str__(self):
        return "%s (%s)" % (self.cmd_str[:40], str(self.queued_at))

    @property
    def metadata(self):
        #TODO Future, flatten (tag, name) records if they have been 'overwritten'
        return self.metarecord_set.all().order_by('-timestamp')

    @property
    def effects_unchanged(self):
        return self.effects.filter(Q(effect_status = 'U'))

    @property
    def effects_changed(self):
        return self.effects.filter(~Q(effect_status = 'U'))


class CommandOnResource(models.Model):
    """Record of a Command having an effect on a Resource"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    resource = models.ForeignKey('Resource')
    command = models.ForeignKey('Command', related_name="effects")

    resource_hash = models.CharField(max_length=64)
    resource_size = models.BigIntegerField(default=0)

    effect_status = models.CharField(max_length=1)

    def __str__(self):
        return ("%s - %s" % (self.command, self.resource))

    @property
    def prev(self):
        """Get the previous effect for the associated Resource"""
        return self.resource.commandonresource_set.filter(command__finished_at__lte = self.command.finished_at).order_by('command__finished_at', '-command__group_order').last()

    @property
    def next(self):
        """Get the next effect for the associated Resource"""
        return self.resource.commandonresource_set,filter(command__finished_at__gte = self.command.finished_at).order_by('command__finished_at', '-command__group_order').first()

class MetaRecord(models.Model):
    """Metadata pertaining to:
        * A Command, such as run time, or its parameters,
        * A Resource, such as the number of lines or records inside of it,
        * A Command and Resource, indicating a record for a Command that has changed a Resource
        * A ResourceGroup, to save you having to mark all the Resources inside
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    resource = models.ForeignKey('Resource', null=True, blank=True)
    group = models.ForeignKey('ResourceGroup', null=True, blank=True)
    command = models.ForeignKey('Command', null=True, blank=True)

    meta_tag = models.CharField(max_length=64, db_index=True)
    meta_name = models.CharField(max_length=64)

    value_type = models.CharField(max_length=48)
    value = models.CharField(max_length=128)

    timestamp = models.DateTimeField()

    def translate(self):
        # if value_type == "datetime"...
        #   return strftime
        # elif value_type == "resource"...
        #   return lookup resource
        return self.value


from . import models
from dateutil.rrule import rrule, DAILY
import datetime
import re
from django.utils import timezone
from dateutil.parser import parse

def get_mag(root, path, sep="/", artifact=False, by_hard_path=False):

    try:
        node = models.DigitalResourceNode.objects.get(node_name=root)
    except:
        return None, []

    lpath = path.split(sep)
    if path[0] == sep:
        # Chop leading path head
        lpath = lpath[1:]
    if path[-1] == sep:
        lpath = lpath[:-1]

    if artifact:
        # Chop path tail
        lpath = lpath[:-1]


    if by_hard_path:
        try:
            dir_g = models.DigitalResourceGroup.objects.get(root_group=node, group_path=sep.join(lpath))
            return dir_g
        except:
            return None, []
    else:
        parent = node
        for i, dir_name in enumerate(lpath):
            try:
                dir_g = models.DigitalResourceGroup.objects.get(
                        current_name=dir_name,
                        root_group=node,
                        parent_group=parent,
                )
                parent = dir_g
            except:
                return None, []
        return dir_g


def mkroot(node_name):
    node, created = models.DigitalResourceNode.objects.get_or_create(
        unique_name = node_name,
        dice_name = node_name,
        meta_name = node_name,
        node_name = node_name,
    )
    return node

def mkmag(path, sep="/", parents=True, artifact=False, physical=True, root=None, kind=None):

    lpath = path.split(sep)

    if path[0] == sep:
        # Chop leading path head
        lpath = lpath[1:]

    if artifact:
        # Chop path tail
        lpath = lpath[:-1]

    mags = []
    mags_created = []
    parent = root
    for i, dir_name in enumerate(lpath):
        dir_g, created = models.DigitalResourceGroup.objects.get_or_create(
                group_path=sep.join(lpath[:i+1]),
                current_name=dir_name,
                root_group=root,
                parent_group=parent,
                temp_kind=kind,
                physical=physical)
        parent = dir_g

        mags.append(dir_g)
        mags_created.append(created)

    return mags, mags_created

def quarantine_artifact(process, artifact):
    artifact.quarantined = True

    qr = models.MajoraArtifactQuarantinedProcessRecord(
        process=process,
        in_artifact=artifact,
        out_artifact=artifact,
    )
    qr.save()
    artifact.save()

def try_date(str_):
    dt = None
    for s_ in re.split('[^0-9-]', str_):
        if len(s_.replace("-", "")) < 6:
            continue
        try:
            tdt = parse(s_, yearfirst=True, fuzzy=True)
            if tdt and tdt.year >= (timezone.now().year - 1) and tdt.year <= timezone.now().year:
                # Try and avoid absurd dates
                dt = tdt
                break # just use the first thing that looks like a date?
        except ValueError:
            pass
    return dt

def make_spark(queryset, days=30, many=None):
    counts = {}
    querysets = {}
    if not many:
        querysets = {"default": queryset}
    else:
        for obj in queryset:
            curr_qs = obj[many].replace("/", "_")
            if curr_qs not in querysets:
                querysets[curr_qs] = []
            querysets[curr_qs].append(obj)
    
    for qs in querysets:
        i = 0
        try:
            cursor = querysets[qs][i]
            if qs not in counts:
                counts[qs] = {
                    "n": 0,
                    "a": [],
                }
            for dt in rrule(DAILY, dtstart=timezone.now().date()-datetime.timedelta(days=days), until=timezone.now().date()):
                dt = dt.date()
                cdt = cursor["date"].date()
                if dt < cdt:
                    counts[qs]["a"].append({"date": dt.strftime("%Y-%m-%d"), "count": counts[qs]["n"]})
                    continue
                elif dt == cdt:
                    counts[qs]["n"] += cursor["count"]
                    i += 1
                    counts[qs]["a"].append({"date": dt.strftime("%Y-%m-%d"), "count": counts[qs]["n"]})
                    try:
                        cursor = querysets[qs][i]
                    except IndexError:
                        pass
                elif dt > cdt:
                    counts[qs]["a"].append({"date": dt.strftime("%Y-%m-%d"), "count": counts[qs]["n"]})
        except:
            pass

    if not many:
        return counts["default"]["a"]
    else:
        return {k: v["a"] for k, v in counts.items()}


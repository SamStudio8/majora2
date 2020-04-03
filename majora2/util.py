from . import models
from dateutil.rrule import rrule, DAILY
import datetime
import re
from django.utils import timezone
from dateutil.parser import parse

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
    for s_ in re.split('[^a-zA-Z0-9]', str_):
        if len(s_) < 6:
            continue
        try:
            tdt = parse(s_, yearfirst=True, fuzzy=True)
            if tdt and tdt.year >= (timezone.now().year - 1) and tdt.year <= timezone.now().year:
                # Try and avoid absurd dates
                dt = tdt
        except ValueError:
            pass
    return dt

def make_spark(queryset, days=30):
    counts = []
    i = 0
    n = 0
    cursor = queryset[i]
    for dt in rrule(DAILY, dtstart=timezone.now().date()-datetime.timedelta(days=days), until=timezone.now().date()):
        dt = dt.date()
        cdt = cursor["date"].date()
        if dt < cdt:
            counts.append({"date": dt.strftime("%Y-%m-%d"), "count": n})
            continue
        elif dt == cdt:
            n += cursor["count"]
            i += 1
            counts.append({"date": dt.strftime("%Y-%m-%d"), "count": n})
            try:
                cursor = queryset[i]
            except IndexError:
                pass
        elif dt > cdt:
            counts.append({"date": dt.strftime("%Y-%m-%d"), "count": n})
    return counts

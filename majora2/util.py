from . import models
from dateutil.rrule import rrule, DAILY
import datetime
from django.utils import timezone

def quarantine_artifact(process, artifact):
    artifact.quarantined = True

    qr = models.MajoraArtifactQuarantinedProcessRecord(
        process=process,
        in_artifact=artifact,
        out_artifact=artifact,
    )
    qr.save()
    artifact.save()

def create_biosample(self):
    pass


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

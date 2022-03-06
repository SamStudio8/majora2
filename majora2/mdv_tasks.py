from datetime import datetime

from django.db.models import F

from majora2 import models

def subtask_get_mdv_v3_phe1_faster():
    ret = []
    for sample in models.BiosampleArtifact.objects.filter(
        created__biosourcesamplingprocess__collection_location_adm1="UK-ENG",
        created__who__profile__agreements__agreement__slug="eng-sendersampleid-phe-1",
        created__who__profile__agreements__is_terminated=False
    ).values(
        "central_sample_id",
        "sender_sample_id",
        adm1=F("created__biosourcesamplingprocess__collection_location_adm1"),
        collection_date=F("created__biosourcesamplingprocess__collection_date"),
        received_date=F("created__biosourcesamplingprocess__received_date"),
    ): 
        ret.append({
            "central_sample_id": sample["central_sample_id"],
            "created": {
                "adm1": sample["adm1"],
                "collection_date": datetime.strftime(sample["collection_date"], "%Y-%m-%d") if sample["collection_date"] else None,
                "process_model": "BiosourceSamplingProcess", # backward compat
                "received_date": datetime.strftime(sample["received_date"], "%Y-%m-%d") if sample["received_date"] else None,
            },
            "sender_sample_id": sample["sender_sample_id"],
        })
    return ret

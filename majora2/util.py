from . import models

def quarantine_artifact(process, artifact):
    artifact.quarantined = True

    qr = models.MajoraArtifactQuarantinedProcessRecord(
        process=process,
        in_artifact=artifact,
        out_artifact=artifact,
    )
    qr.save()
    artifact.save()

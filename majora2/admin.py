from django.contrib import admin
from django.db import models

from . import models as m

admin.site.register(m.DigitalResourceArtifact)
admin.site.register(m.DigitalResourceGroup)
admin.site.register(m.DigitalResourceNode)
admin.site.register(m.TubeArtifact)
admin.site.register(m.TubeContainerGroup)
admin.site.register(m.MajoraArtifactProcessGroup)
admin.site.register(m.MajoraArtifactProcessTest)
admin.site.register(m.MajoraArtifactProcessRecordTest)
admin.site.register(m.MajoraArtifactGroup)
admin.site.register(m.BiosampleArtifact)
admin.site.register(m.BiosourceSamplingProcess)
admin.site.register(m.BiosampleSource)
admin.site.register(m.LabCheckinProcess)
admin.site.register(m.LabCheckinProcessRecord)


admin.site.register(m.DigitalResourceCommand)
admin.site.register(m.DigitalResourceCommandGroup)
admin.site.register(m.DigitalResourceCommandPipelineGroup)
admin.site.register(m.DigitalResourceCommandRecord)

admin.site.register(m.MajoraMetaRecord)
admin.site.register(m.Favourite)

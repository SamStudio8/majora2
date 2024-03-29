from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.utils.http import urlencode

from . import models
from . import util
from . import forms
from . import signals

import json
import datetime
import dateutil.parser
from django.contrib.auth.models import User

#from django.contrib.auth.decorators import user_passes_test
#def user_check(user):
#    return user.email.endswith('.ac.uk')
#from django.contrib.auth.decorators import permission_required
#@permission_required('polls.can_vote')



from django.contrib.auth.decorators import login_required
from django_otp.decorators import otp_required

from tatl.util import django_2fa_mixin_hack
from tatl.models import TatlVerb

@login_required
def barcode(request, uuid):
    #TODO Do this ONCE and cache the result
    from pylibdmtx.pylibdmtx import encode
    from PIL import Image
    encoded = encode(str(uuid).encode('utf-8'), 'Ascii')
    img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
    response = HttpResponse(content_type="image/png")
    img.save(response, "PNG")
    return response

@login_required
def detail_artifact(request, artifact_uuid):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp
    artifact = get_object_or_404(models.MajoraArtifact, id=artifact_uuid)

    TatlVerb(request=request.treq, verb="RETRIEVE", content_object=artifact).save()
    return render(request, 'detail_artifact.html', {
        "artifact": artifact,
    })

@login_required
def detail_artifact_dice(request, artifact_dice):
    artifact = get_object_or_404(models.MajoraArtifact, dice_name=artifact_dice)
    return redirect(reverse('detail_artifact', kwargs={'artifact_uuid': artifact.id}))

@login_required
def group_artifact(request, group_uuid):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    group = get_object_or_404(models.MajoraArtifactGroup, id=group_uuid)
    f = models.Favourite.objects.filter(user=request.user.id, group=group_uuid)

    if group.tagged_artifacts.count() > 100 or group.child_artifacts.count() > 100:
        return HttpResponseBadRequest("Sorry, this group contains more than 100 artifacts and cannot be displayed at this time.")
    else:
        TatlVerb(request=request.treq, verb="RETRIEVE", content_object=group).save()
        return render(request, 'list_artifact.html', {
            "group": group,
            "favourite": f,
        })

@login_required
def group_artifact_dice(request, group_dice):
    group = get_object_or_404(models.MajoraArtifactGroup, dice_name=group_dice)
    return redirect(reverse('group_artifact', kwargs={'group_uuid': group.id}))

@login_required
def detail_process(request, process_uuid):
    process = get_object_or_404(models.MajoraArtifactProcess, id=process_uuid)
    TatlVerb(request=request.treq, verb="RETRIEVE", content_object=process).save()
    return render(request, 'detail_process.html', {
        "process": process
    })

@login_required
def group_process(request, group_uuid):
    group = get_object_or_404(models.MajoraArtifactProcessGroup, id=group_uuid)
    f = models.Favourite.objects.filter(user=request.user.id, pgroup=group_uuid).first()

    TatlVerb(request=request.treq, verb="RETRIEVE", content_object=group).save()
    return render(request, 'list_process.html', {
        "group": group,
        "favourite": f,
    })

@login_required
def home(request):
    return render(request, 'search.html', {
        'user': request.user,
        'groups': models.Favourite.group_groups(models.Favourite.objects.filter(user=request.user.id).exclude(group__isnull=True)),
        #'processes': models.MajoraArtifactProcess.group(models.MajoraArtifactProcess.objects.filter(who=request.user.id).order_by('-when')),
    })

@login_required
def favourite_group(request, group_uuid):
    group = get_object_or_404(models.MajoraArtifactGroup, id=group_uuid)
    f = models.Favourite.objects.filter(user=request.user.id, group=group_uuid)
    if f:
        f.delete()
    else:
        f = models.Favourite(user=request.user, group=group)
        f.save()
    return redirect(reverse('group_artifact', kwargs={'group_uuid': group.id}))
@login_required
def favourite_pgroup(request, pgroup_uuid):
    group = get_object_or_404(models.MajoraArtifactProcessGroup, id=pgroup_uuid)
    f = models.Favourite.objects.filter(user=request.user.id, pgroup=pgroup_uuid)
    if f:
        f.delete()
    else:
        f = models.Favourite(user=request.user, pgroup=group)
        f.save()
    return redirect(reverse('group_process', kwargs={'group_uuid': group.id}))

@login_required
def profile(request):
    return render(request, 'profile.html', {
        'user': request.user,
        'groups': models.Favourite.objects.filter(user=request.user.id).exclude(group__isnull=True),
        'pgroups': models.Favourite.objects.filter(user=request.user.id).exclude(pgroup__isnull=True),
        'processes': models.MajoraArtifactProcess.objects.filter(who=request.user.id).order_by('-when'),
        'samples': models.BiosampleArtifact.objects.filter(created__who__profile__institute__code=request.user.profile.institute.code),
        'pag_ajax_url': reverse('api.datatable.pag.get') + '?' + urlencode({'default_seqsite': request.user.profile.institute.code}),
        'biosample_ajax_url': reverse('api.datatable.biosample.get'),
        'site_codes': [request.user.profile.institute.code],
    })

@login_required
def search(request):
    query = None
    query = request.GET.get("q", None)

    artifact = process = process_group = group = None
    try:
        artifact = models.MajoraArtifact.objects.get(id=query)
    except Exception:
        pass
    try:
        process = models.MajoraArtifactProcess.objects.get(id=query)
    except Exception:
        pass
    try:
        process_group = models.MajoraArtifactProcessGroup.objects.get(id=query)
    except Exception:
        pass
    try:
        group = models.MajoraArtifactGroup.objects.get(id=query)
    except Exception:
        pass
    if not artifact:
        try:
            artifact = models.MajoraArtifact.objects.filter(dice_name=query).first()
        except Exception:
            pass
    if not group:
        try:
            group = models.MajoraArtifactGroup.objects.filter(dice_name=query).first()
        except Exception:
            pass

    # god what the fuck is all this about
    # if you cant beat them join them
    if not group:
        try:
            group = models.PublishedArtifactGroup.objects.filter(published_name=query).first()
        except Exception:
            pass

    if not process:
        try:
            process = models.DNASequencingProcess.objects.filter(run_name=query).first()
        except Exception:
            pass

    if artifact:
        return redirect(reverse('detail_artifact', kwargs={'artifact_uuid': artifact.id}))
    elif process:
        return redirect(reverse('detail_process', kwargs={'process_uuid': process.id}))
    elif process_group:
        return redirect(reverse('group_process', kwargs={'group_uuid': process_group.id}))
    elif group:
        return redirect(reverse('group_artifact', kwargs={'group_uuid': group.id}))
    else:
        return HttpResponseBadRequest("Sorry, I've searched everywhere and that identifier does not appear in Majora.")

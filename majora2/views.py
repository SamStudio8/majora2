from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

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
    return render(request, 'detail_artifact.html', {
        "artifact": get_object_or_404(models.MajoraArtifact, id=artifact_uuid)
    })

@login_required
def detail_artifact_dice(request, artifact_dice):
    artifact = get_object_or_404(models.MajoraArtifact, dice_name=artifact_dice)
    return redirect(reverse('detail_artifact', kwargs={'artifact_uuid': artifact.id}))

@login_required
def group_artifact(request, group_uuid):
    group = get_object_or_404(models.MajoraArtifactGroup, id=group_uuid)
    f = models.Favourite.objects.filter(user=request.user.id, group=group_uuid)
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
    return render(request, 'detail_process.html', {
        "process": get_object_or_404(models.MajoraArtifactProcess, id=process_uuid)
    })

@login_required
def group_process(request, group_uuid):
    group = get_object_or_404(models.MajoraArtifactProcessGroup, id=group_uuid)
    f = models.Favourite.objects.filter(user=request.user.id, pgroup=group_uuid).first()
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
        'samples': [b.out_artifact for bsr in models.BiosourceSamplingProcess.objects.filter(submission_org=request.user.profile.institute) for b in bsr.records.all()]
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

    if artifact:
        return redirect(reverse('detail_artifact', kwargs={'artifact_uuid': artifact.id}))
    elif process:
        return redirect(reverse('detail_process', kwargs={'process_uuid': process.id}))
    elif process_group:
        return redirect(reverse('group_process', kwargs={'group_uuid': process_group.id}))
    elif group:
        return redirect(reverse('group_artifact', kwargs={'group_uuid': group.id}))
    else:
        return HttpResponseBadRequest("Invalid request.")


@login_required
def tabulate_artifact(request):
    from django.apps import apps

    q = request.GET.get('q', None)
    s = request.GET.get('s', '')
    m = request.GET.get('m', None)
    if not q or not s or not m:
        return HttpResponseBadRequest("Invalid query.")

    model = apps.get_model('majora2', m)
    if not model:
        return HttpResponseBadRequest("Invalid query.")

    fields = {}
    filters = q.split(",")
    for fil in filters:
        try:
            key, value = fil.split(".")
        except:
            return HttpResponseBadRequest("Invalid query.")

        field_map = {
            "pipe-in": "before_process__process__in",
            "pipe-out": "after_process__process__in",
        }
        def vmap_pipe(s):
            try:
                return [x.id for x in models.DigitalResourceCommandPipelineGroup.objects.get(id=s).process_tree]
            except:
                return []
        value_map = {
            "pipe-in": vmap_pipe,
            "pipe-out": vmap_pipe,
        }

        if key in value_map:
            value = value_map[key](value)
        if key in field_map:
            key = field_map[key]

        try:
            fields[key] = int(value)
        except:
            fields[key] = value

    artifacts = model.objects.filter(**fields)


    table = {}
    for artifact in artifacts:
        table[artifact.id] = []

        for field in s.split(","):

            meta = attribute = lookup = False
            lookups = []
            if '.' in field:
                parts = field.split(".")
                meta = True
                tag = parts[0]
                name = parts[1]
            else:
                lookup = True
                #parts, lookups = field.split("__",1)
                lookups = field.split("__")
                attribute = True

            if meta:
                rs = artifact.get_metadatum(tag, name, process_tree=True, group_tree=True)
                if rs:
                    rs = rs.order_by('-timestamp').last() # TODO
                    if lookup:
                        t = rs.translate
                        for l in lookups:
                            t = getattr(t, l, None)
                        table[artifact.id].append(t)
                    else:
                        table[artifact.id].append(rs.translate)
                else:
                    table[artifact.id].append('')
            elif attribute:
                t = artifact
                for l in lookups:
                    t = getattr(t, l, None)
                table[artifact.id].append(t)
            else:
                table[artifact.id].append("")

            """
            if f_type == "PG":
                rs = result.created.process.group.get_metadatum(tag, name).first()
                if rs:
                    if len(parts)>2:
                        lookup = parts[2]
                    else:
                        show[result.id].append(rs.translate)
                else:
                    show[result.id].append("")
            elif f_type == "P":
                show[result.id].append(getattr(result.created.process.group, name, ''))
            elif f_type == "A":
                if len(tag) > 0:
                    try:
                        show[result.id].append(result.get_metadatum(tag, name).last().translate)
                    except:
                        show[result.id].append(getattr(result, name, ''))
                else:
                    show[result.id].append(getattr(result, name, ''))
            else:
                show[result.id].append("")
            """

    return render(request, 'tabulate_artifact.html', {
        "q": q,
        "model": str(model),
        "show_fields": s.split(","),
        "table": table,
        "fields": fields,
    })


##############################################################################
# Forms
from . import form_handlers
from . import fixed_data
##############################################################################
@login_required
def form_sampletest(request):
    initial = fixed_data.fill_fixed_data("api.biosample.add", request.user)

    if request.method == "POST":
        form = forms.TestSampleForm(request.POST, initial=initial)
        if form.is_valid():
            form.cleaned_data.update(initial)
            sample, sample_created = form_handlers.handle_testsample(form, request.user)
            if sample:
                return HttpResponse(json.dumps({
                    "success": True,
                }), content_type="application/json")
    else:
        form = forms.TestSampleForm(
            initial=initial,
        )
    return render(request, 'forms/testsample.html', {'form': form})


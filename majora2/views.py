from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from . import models
from . import util
from . import forms

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
        'processes': models.MajoraArtifactProcess.group(models.MajoraArtifactProcess.objects.filter(who=request.user.id).order_by('-when')),
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
        'processes': models.MajoraArtifactProcess.objects.filter(who=request.user.id).order_by('-when')
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
from django.views.decorators.debug import sensitive_post_parameters
##############################################################################
@sensitive_post_parameters('password', 'password2')
def form_register(request):
    if request.method == "POST":
        form = forms.RegistrationForm(request.POST)
        if form.is_valid():
            # do stuff
            return HttpResponse(json.dumps({
                "success": True,
            }), content_type="application/json")
    else:
        form = forms.RegistrationForm()
    return render(request, 'forms/register.html', {'form': form})


def form_sampletest(request):
    if request.method == "POST":
        form = forms.TestSampleForm(request.POST)
        if form.is_valid():
            # do stuff
            return HttpResponse(json.dumps({
                "success": True,
            }), content_type="application/json")
    else:
        form = forms.TestSampleForm(
            initial={
                'submitting_username': request.user.username,
                'submitting_organisation': request.user.profile.organisation if hasattr(request.user, "profile") else ""
            },
        )
    return render(request, 'forms/testsample.html', {'form': form})


##############################################################################
# API
##############################################################################
from django.conf import settings

@csrf_exempt
def api_hello(request):
    # should be a stream of barcodes
    #TODO make people scan a session token from user account first (if 2FA on)
    pass


@csrf_exempt
def api_extract(request):
    errors = 0
    warnings = 0
    messages = []

    json_data = json.loads(request.body)
    if json_data.get('key', None) != settings.API_KEY:
        return HttpResponseBadRequest()

    pgroup = models.MajoraArtifactProcessGroup()
    #pgroup.save()
    #pgroup.groups.add(project)
    pgroup.save()

    for extraction in json_data.get("extractions", []):
        try:
            extraction_date = dateutil.parser.parse(extraction.get("extraction_date", None))
        except:
            extraction_date = None

        ex_pgroup = models.MajoraArtifactProcessGroup()
        ex_pgroup.save()
        ex_p = models.BiosampleExtractionProcess(
            who=User.objects.get(id=1), # TODO
            when=extraction_date,
            group=ex_pgroup,
            extraction_method=extraction.get("extraction_type", "Unknown")
        )
        ex_p.save()
        for meta_key in extraction.get("metadata", {}):
            try:
                tag, name = meta_key.split(".")
                mr = models.MajoraMetaRecord(process=ex_p, meta_tag=tag, meta_name=name, value_type="str", value=extraction["metadata"][meta_key], timestamp=extraction_date)
                mr.save()
            except:
                #todo warning
                pass

        for tube in extraction.get("tubes", {}):
            tube_o = models.TubeArtifact.objects.filter(dice_name=tube).first()
            in_art = models.BiosampleArtifact.objects.filter(sample_orig_id=extraction["tubes"][tube].get("in_artifact")).first()
            if tube_o and in_art:
                ex_rec = models.BiosampleExtractionProcessRecord(
                    process=ex_p,
                    in_artifact=in_art,
                    out_artifact=tube_o,
                )
                ex_rec.save()

                for meta_key in extraction["tubes"][tube].get("metadata", {}):
                    try:
                        tag, name = meta_key.split(".")
                        mr = models.MajoraMetaRecord(artifact=tube_o, meta_tag=tag, meta_name=name, value_type="str", value=extraction["tubes"][tube]["metadata"][meta_key], timestamp=extraction_date)
                        mr.save()
                    except:
                        #todo warning
                        pass
            else:
                messages.append("Tube '%s' not in Majora." % tube)
                warnings += 1

    #TODO return new box, tube uuid etc.
    return HttpResponse(json.dumps({
        "success": errors == 0,
        "messages": messages,
        "errors": errors,
        "warnings": warnings,
    }), content_type="application/json")

@csrf_exempt
def api_checkin_tube(request):

    errors = 0
    warnings = 0
    messages = []

    json_data = json.loads(request.body)
    if json_data.get('key', None) != settings.API_KEY:
        return HttpResponseBadRequest()

    project_name = json_data.get("project", None)
    if not project_name:
        messages.append("You must provide a Project.")
        errors += 1

    project = models.MajoraArtifactGroup.objects.filter(meta_name=project_name).first()
    if not project:
        messages.append("Project not known to Majora, adding a dummy project.")
        warnings += 1

    boxes = json_data.get("boxes", {})
    for box in boxes:
        box_dice = boxes[box].get("box_dice", None)
        if not box_dice:
            messages.append("All boxes must have a box_dice name.")
            errors += 1
        parent_dice = boxes[box].get("parent_dice", None)
        parent_box = None
        if parent_dice:
            parent_box = models.TubeContainerGroup.objects.filter(dice_name=parent_dice).first()
            if not parent_box:
                messages.append("The parent TubeContainerGroup %s does not exist in Majora, add it first if you want to refer to it." % parent_dice)
                errors += 1

    tubes = json_data.get("tubes", [])
    for tube_i, tube in enumerate(tubes):
        tube_uuid = tube.get("tube_uuid", None)
        tube_dice = tube.get("tube_dice", None)
        sample_orig = tube.get("sample_name", None)
        sample_source = tube.get("source_name", None)
        box_dice = tube.get("box_dice", None)
        if not tube_uuid or not tube_dice:
            messages.append("You must provide a Tube UUID and Dicename to check-in Tube %d." % (tube_i + 1))
            errors += 1
        if not sample_orig or not sample_source:
            messages.append("You must provide a sample source and sample name to check-in Tube %d." % (tube_i + 1))
            errors += 1
        if not box_dice:
            errors += 1
            messages.append("Tube %d has not been provided with a box_dice key." % (tube_i + 1))
        #if box_dice not in boxes:
        #    errors += 1
        #    messages.append("Tube %d refers to Box %s which is not in the boxes dictionary." % (tube_i + 1, box_dice))

    quarantine_process = None
    if not errors:
        if not project:
            project = models.MajoraArtifactGroup(
                meta_name = project_name,
                physical=False,
            )
            project.save()

        #majoraartifactprocessgroup
        pgroup = models.MajoraArtifactProcessGroup()
        #pgroup.save()
        #pgroup.groups.add(project)
        pgroup.save()

        checkin = models.LabCheckinProcess(
            who=User.objects.get(id=1), # TODO
            when=datetime.datetime.now(),
            originating_site  = json_data.get("origin_site", "Unknown"),
            originating_user  = json_data.get("origin_user", "Unknown"),
        )
        checkin.group=pgroup,
        checkin.save()

        for tube_i, tube in enumerate(tubes):
            tube_uuid = tube.get("tube_uuid", None)
            tube_dice = tube.get("tube_dice", None)
            sample_orig = tube.get("sample_name", None)
            sample_source = tube.get("source_name", None)

            box_dice = tube.get("box_dice", None)
            box = models.TubeContainerGroup.objects.filter(dice_name=box_dice).first()
            if not box:
                messages.append("TubeContainerGroup not known to Majora, adding a dummy box.")
                warnings += 1

                # Add dummy box
                box = models.TubeContainerGroup(
                    dice_name=box_dice,
                    physical=True,
                    contains_tubes=True,
                    parent_x =      json_data.get("parent_x", 0),
                    parent_y =      json_data.get("parent_y", 0),
                    dimension_x =   json_data.get("box_xdim", 0),
                    dimension_y =   json_data.get("box_ydim", 0),
                    container_type =json_data.get("box_type", "Box"),
                )
                box.save()
                box.groups.add(project)
                box.save()

            source = models.BiosampleSource.objects.filter(meta_name=sample_source).first()
            if not source:
                source = models.BiosampleSource(
                    meta_name   = sample_source,
                    source_type = tube.get("source_type", "Unknown"),
                    physical = True,
                )
                source.save()
                source.groups.add(project)
                source.save()

            sample = models.BiosampleArtifact.objects.filter(sample_orig_id=sample_orig).first()
            if not sample:
                # Create the sample process and sample

                try:
                    collection_date = dateutil.parser.parse(tube.get("collection_date", None))
                except:
                    collection_date = None

                sample = models.BiosampleArtifact(
                    sample_orig_id = sample_orig,
                    sample_type = tube.get("sample_type", "Unknown"),
                    specimen_type = tube.get("specimen_type", "Unknown"),
                    collection_date = collection_date,
                    primary_group = source,
                )
                sample.save()

                sample_pgroup = models.MajoraArtifactProcessGroup()
                sample_pgroup.save()
                sample_p = models.BiosourceSamplingProcess(
                    when=collection_date,
                    group=sample_pgroup,
                )
                sample_p.save()
                sampling_rec = models.BiosourceSamplingProcessRecord(
                    process=sample_p,
                    in_group=source,
                    out_artifact=sample,
                )
                sampling_rec.save()

                for meta_key in tube.get("metadata", {}):
                    try:
                        tag, name = meta_key.split(".")
                        mr = models.MajoraMetaRecord(artifact=sample, meta_tag=tag, meta_name=name, value_type="str", value=tube["metadata"][meta_key], timestamp=datetime.datetime.now())
                        mr.save()
                    except:
                        #todo warning
                        pass

            tube_o = models.TubeArtifact(
                id=tube_uuid,
                dice_name=tube_dice,
                container_x =    tube.get("tube_x", 0),
                container_y =    tube.get("tube_y", 0),
                storage_medium = tube.get("medium", "None"),
                tube_form =      tube.get("tube_form", ""),
                sample_form =    tube.get("sample_form", ""),
                primary_group = box,
                root_artifact = sample,
            )
            tube_o.save()

            if tube.get("self_checkin", None):
                in_art = tube_o
            else:
                in_art = sample

            missing= tube.get("missing", False)
            unexpected= tube.get("unexpected", False)
            confusing= tube.get("confusing", False)
            damaged= tube.get("damaged", False)
            accepted=tube.get("accepted", True)

            checkin_rec = models.LabCheckinProcessRecord(
                process=checkin,
                in_artifact=in_art,
                out_artifact=tube_o,
                missing=missing,
                unexpected=unexpected,
                confusing=confusing,
                damaged=damaged,
                accepted=accepted,
            )
            checkin_rec.save()

            if not accepted:
                if not quarantine_process:
                    quarantine_process = models.MajoraArtifactQuarantinedProcess(
                        who=User.objects.get(id=1), # TODO
                        when=datetime.datetime.now(),
                    )
                    quarantine_process.save()
                #TODO return errors etc.
                util.quarantine_artifact(quarantine_process, tube_o)

    #TODO return new box, tube uuid etc.
    return HttpResponse(json.dumps({
        "success": errors == 0,
        "messages": messages,
        "errors": errors,
        "warnings": warnings,
    }), content_type="application/json")










@csrf_exempt
def api_checkin_container(request):

    errors = 0
    warnings = 0
    messages = []

    json_data = json.loads(request.body)
    if json_data.get('key', None) != settings.API_KEY:
        return HttpResponseBadRequest()

    boxes = json_data.get("boxes", [])
    for ibox, dbox in enumerate(boxes):
        box_dice = dbox.get("box_dice", None)
        if not box_dice:
            messages.append("Box %d was ignored as it did not have a box_dice key." % (ibox+1))
            warnings += 1
        parent_dice = dbox.get("parent_dice", None)
        parent_box = None

        if parent_dice:
            parent_box = models.TubeContainerGroup.objects.filter(dice_name=parent_dice).first()
            if not parent_box:
                messages.append("The parent for Box %d was ignored as the parent TubeContainerGroup '%s' does not exist in Majora. It should have appeared in the listing before this box if you want to add it at this time." % (ibox+1, parent_dice))
                warnings += 1

        box = models.TubeContainerGroup.objects.filter(dice_name=box_dice).first()
        if not box:

            box = models.TubeContainerGroup(
                dice_name=box_dice,
                physical=True,
                parent_group = parent_box,
                contains_tubes= dbox.get("contains_tubes", False),
                parent_x =      dbox.get("parent_row", 0),
                parent_y =      dbox.get("parent_col", 0),
                dimension_x =   dbox.get("box_rows", 0),
                dimension_y =   dbox.get("box_cols", 0),
                container_type =dbox.get("box_type", "Box"),
            )
            box.save()
            #box.groups.add(project)
            box.save()

            for meta_key in dbox.get("metadata", {}):
                try:
                    tag, name = meta_key.split(".")
                    mr = models.MajoraMetaRecord(group=box, meta_tag=tag, meta_name=name, value_type="str", value=dbox["metadata"][meta_key], timestamp=datetime.datetime.now())
                    mr.save()
                except:
                    #todo warning
                    pass
        else:
            messages.append("TubeContainerGroup %s already known to Majora, ignoring entry." % box_dice)
            warnings += 1


    if not errors:
        pass
        #pgroup = models.MajoraArtifactProcessGroup()
        #pgroup.save()

        #checkin = models.LabCheckinProcess(
        #    who=User.objects.get(id=1), # TODO
        #    when=datetime.datetime.now(),
        #    group=pgroup,
        #    originating_site  = json_data.get("origin_site", "Unknown"),
        #    originating_user  = json_data.get("origin_user", "Unknown"),
        #)
        #checkin.save()

        #checkin_rec = models.LabCheckinProcessRecord(
        #    process=checkin,
        #    in_artifact=sample,
        #    out_artifact=tube_o,
        #)
        #checkin_rec.save()

    #TODO return new box, tube uuid etc.
    return HttpResponse(json.dumps({
        "success": errors == 0,
        "messages": messages,
        "errors": errors,
        "warnings": warnings,
    }), content_type="application/json")







@csrf_exempt
def ocarina_new_command(request):
    def f(request, api_o, json_data):
        cmd_uuid = json_data["cmd_uuid"]
        cmd_str = json_data["cmd_str"]
        user = json_data.get("user", "somebody")
        queued_at = datetime.datetime.fromtimestamp(json_data["queued_at"])
        group_order = json_data.get("order", 0)

        cgroup = models.DigitalResourceCommandGroup()
        cgroup.save()
        c = models.DigitalResourceCommand(
            id=cmd_uuid,
            cmd_str=cmd_str,
            who=User.objects.get(id=1), # TODO
            when=queued_at,
            group=cgroup,
            group_order=group_order,
            queued_at=queued_at,
        )
        c.save()

        api_o["new"].append(str(c.id))

    return wrap_api(request, f)

@csrf_exempt
def ocarina_update_command(request):
    def f(request, api_o, json_data):
        c = models.DigitalResourceCommand.objects.filter(id=json_data["cmd_uuid"]).first()
        if not c:
            api_o["errors"] += 1
            api_o["messages"].append("DigitalResourceCommand not found.")
            return

        c.started_at = datetime.datetime.fromtimestamp(json_data["started_at"])
        c.finished_at = datetime.datetime.fromtimestamp(json_data["finished_at"])
        c.return_code = json_data["return_code"]
        api_o["updated"].append(str(c.id))
        c.save()

        resources = json_data.get("resources", [])
        if len(resources) == 0:
            # Command didn't have any effects, just ignore for now
            #TODO Delete uuid?
            api_o["warnings"] += 1
            api_o["messages"].append("No DigitalArtifacts were affected.")
            return # No more to do

        effect_code = 'X'
        for resource in resources:
            try:

                # Get the node
                node = models.DigitalResourceNode.objects.filter(pk=resource["node_uuid"]).first()
                if not node:
                    api_o["errors"] += 1
                    api_o["messages"].append("DigitalResourceNode %s not known to Majora" % resource["node_uuid"])
                    api_o["ignored"].append(resource["path"])

                # Get the directory
                parent = node
                for i, dir_name in enumerate(resource["lpath"]):
                    if i == 0:
                        dir_g = models.DigitalResourceGroup.objects.filter(current_name=dir_name, root_group=node).first()
                    else:
                        dir_g = models.DigitalResourceGroup.objects.filter(current_name=dir_name, parent_group=parent).first()

                    if not dir_g:
                        # Directory not yet seen by Majora, add it!
                        dir_g = models.DigitalResourceGroup(
                            current_name = dir_name,
                            physical = True,
                            root_group = node,
                            parent_group = parent,
                        )
                        dir_g.save()
                    parent = dir_g

                # Get the resource
                in_a = out_a = None
                res = models.DigitalResourceArtifact.objects.filter(primary_group=parent, current_name=resource["name"]).first()
                if not res:
                    # New resource!
                    effect_code = 'C'
                    if resource["precommand_exists"]:
                        # Pre-existing resource has been NOTICED
                        effect_code = 'N'
                    res = models.DigitalResourceArtifact(
                    )
                    out_a = res
                else:
                    if not resource["exists"]:
                        # Deleted
                        effect_code = 'D'
                    elif resource["hash"] is not None and res.current_hash != resource["hash"]:
                        # Modified
                        effect_code = 'M'
                        in_a = out_a = res
                    else:
                        # Used
                        # Assume the file has just been used if the hash hasn't been updated
                        effect_code = 'U'
                        resource["hash"] = res.current_hash
                        in_a = res

                dc = models.DigitalResourceCommandRecord(
                    process=c,
                    in_artifact=in_a,
                    out_artifact=out_a,
                    before_size=res.current_size if res.current_size else 0,
                    before_hash=res.current_hash if res.current_hash else "",
                    after_size=resource["size"] if resource["size"] else 0,
                    after_hash=resource["hash"] if resource["hash"] else "",
                    effect_status=effect_code
                )

                if effect_code != 'U':
                    # If something happened
                    if effect_code == 'D':
                        #TODO Might have to suppress adding the hash and size after rm
                        res.ghost = True
                    else:
                        # If the file wasn't deleted
                        res.primary_group = parent
                        res.current_name = resource["name"]
                        res.current_extension = resource["name"].split(".")[-1]
                        res.current_hash = resource["hash"]
                        res.current_size = resource["size"]
                    res.save()
                dc.save()



                #TODO Resource metadata
                api_o["updated"].append({
                    "res_uuid": str(res.id),
                    "effect_code": effect_code,
                })

            except Exception as e:
                api_o["errors"] += 1
                api_o["ignored"].append({resource["path"]: str(e)})
                continue


    return wrap_api(request, f)

@csrf_exempt
def wrap_api(request, f):

    api_o = {
        "errors": 0,
        "warnings": 0,
        "messages": [],
        "new": [],
        "updated": [],
        "ignored": [],
    }

    json_data = json.loads(request.body)
    if json_data.get('key', None) != settings.API_KEY:
        return HttpResponseBadRequest()

    f(request, api_o, json_data)

    api_o["success"] = api_o["errors"] == 0
    api_o["messages"] = list(set(api_o["messages"])) #TODO swap [] to set and use add instead of append
    return HttpResponse(json.dumps(api_o), content_type="application/json")

@csrf_exempt
def ocarina_view_group(request):
    def f(request, api_o, json_data):
        try:

            # Get the node
            node = models.DigitalResourceNode.objects.filter(pk=json_data["node_uuid"]).first()
            if not node:
                api_o["errors"] += 1
                api_o["messages"].append("DigitalResourceNode %s not known to Majora" % json_data["node_uuid"])
                api_o["ignored"].append(json_data["path"])

            # Get the directory
            parent = node
            for i, dir_name in enumerate(json_data["lpath"]):
                if i == 0:
                    dir_g = models.DigitalResourceGroup.objects.select_related().filter(current_name=dir_name, root_group=node).first()
                else:
                    dir_g = models.DigitalResourceGroup.objects.select_related().filter(current_name=dir_name, parent_group=parent).first()

                if not dir_g:
                    # Directory not yet seen by Majora, add it!
                    dir_g = models.DigitalResourceGroup(
                        current_name = dir_name,
                        physical = True,
                        root_group = node,
                        parent_group = parent,
                    )
                    dir_g.save()
                parent = dir_g

        except Exception as e:
            api_o["errors"] += 1
            api_o["ignored"].append({json_data["path"]: str(e)})

        api_o["group"] = {"uuid": str(parent.pk), "name": parent.name}
        api_o["group"]["resources"] = [{"uuid": str(r.pk), "hash": r.current_hash, "name": r.current_name} for r in parent.child_artifacts.all()]
    return wrap_api(request, f)

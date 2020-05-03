def api_biosample_add(user):
    return {
            'source_type': "human",
            'source_taxon': '2697049',
            'country': "United Kingdom",
            'submitting_user': user.username,
            'submitting_org': user.profile.institute.id if hasattr(user, "profile") and not user.profile.institute.code.startswith("?") else None
    }

FIXED_DATA = {
    "api.artifact.biosample.add": api_biosample_add,
}

def fill_fixed_data(k, user=None):
    if k in FIXED_DATA:
        return FIXED_DATA[k](user)
    else:
        return {}

def sampling_strategy_choices(convert_choice=None):
    lookup = {
        "S": "SURVEILLANCE",
        "C": "CLUSTER",
        None: None,
        "": None,
    }
    if convert_choice:
        if convert_choice in lookup:
            return lookup[convert_choice]
        else:
            return None
    else:
        return [(k, v) for k, v in lookup.items()]

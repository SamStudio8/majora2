def api_biosample_add(user):
    return {
            'source_type': "human",
            'source_taxon': '2697049',
            'country': "United Kingdom",
            'submitting_username': user.username,
            'submitting_organisation': user.profile.institute if hasattr(user, "profile") and not user.profile.institute.code.startswith("?") else None
    }

FIXED_DATA = {
    "api.biosample.add": api_biosample_add,
}

def fill_fixed_data(k, user=None):
    if k in FIXED_DATA:
        return FIXED_DATA[k](user)
    else:
        return {}


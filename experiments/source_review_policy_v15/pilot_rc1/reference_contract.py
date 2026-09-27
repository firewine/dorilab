"""Reference-set contract for CPU fixtures and candidate metadata review.
Does not read model predictions. Existing v13/v14 scorers remain untouched.
"""
def matches_sufficient_set(selected_refs, provided_refs, sufficient_sets):
    if not isinstance(selected_refs,list) or not selected_refs:
        return False
    if not all(isinstance(x,str) for x in selected_refs):
        return False
    if len(selected_refs)!=len(set(selected_refs)):
        return False
    selected=set(selected_refs);provided=set(provided_refs)
    if not selected<=provided:
        return False
    # Deliberately no selected==provided rejection. Membership in a sufficient set matters.
    return any(selected==set(s) and set(s)<=provided for s in sufficient_sets)

def evaluate_approved_metadata(selected_refs,provided_refs,metadata):
    if metadata.get('approved') is not True:
        return None  # unapproved AI candidate metadata must not become an official score
    return matches_sufficient_set(selected_refs,provided_refs,metadata['sufficient_sets'])

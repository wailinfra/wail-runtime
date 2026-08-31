import copy


def build_hash_input(artifact):

    obj = copy.deepcopy(artifact)
    obj.pop("integrity", None)

    return obj
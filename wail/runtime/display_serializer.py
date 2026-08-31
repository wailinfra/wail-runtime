def humanize_numbers(obj):

    if isinstance(obj, dict):
        return {k: humanize_numbers(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [humanize_numbers(v) for v in obj]

    if isinstance(obj, str):

        try:
            f = float(obj)
            return round(f, 6)
        except:
            return obj

    return obj

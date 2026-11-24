def evaluate(visit, recipe, timeline):
    known = in_band = longest = streak = 0
    slices = []
    for piece in timeline.clip(visit['from'], visit['to']):
        span = piece['to'] - piece['from']
        temperature = piece['tenth']
        if temperature is None:
            status = 'unknown'
        elif recipe['min_tenth'] <= temperature <= recipe['max_tenth']:
            status = 'in_band'
        else:
            status = 'out_of_band'
        if status != 'unknown':
            known += span
        if status == 'in_band':
            in_band += span
            streak += span
            longest = max(longest, streak)
        else:
            streak = 0
        slices.append({**piece, 'status': status})
    duration = visit['to'] - visit['from']
    state = ('incomplete' if known < duration else
             'short' if longest < recipe['min_contiguous_s'] else 'qualified')
    return {**visit, 'zone': recipe['zone'], 'label': recipe['label'], 'state': state,
            'duration_s': duration, 'known_s': known, 'in_band_s': in_band, 'longest_s': longest,
            'min_contiguous_s': recipe['min_contiguous_s'], 'slices': slices}

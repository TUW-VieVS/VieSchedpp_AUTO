from itertools import combinations


def spread_ones_global(arr, total_ones):
    n = len(arr)
    fixed = [i for i, v in enumerate(arr) if v == 1]
    zeros = [i for i, v in enumerate(arr) if v == 0]

    to_add = total_ones - len(fixed)
    if to_add <= 0:
        return arr[:]

    best_min_dist = -1
    best_choice = None

    for combo in combinations(zeros, to_add):
        ones = sorted(fixed + list(combo))

        # minimum distance between any two 1s
        min_dist = min(ones[i + 1] - ones[i] for i in range(len(ones) - 1))

        if min_dist > best_min_dist:
            best_min_dist = min_dist
            best_choice = combo

    result = arr[:]
    for i in best_choice:
        result[i] = 1

    return result

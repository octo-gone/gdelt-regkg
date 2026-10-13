"""One-to-one maximum-cardinality matching with minimum-cost tie breaking."""

import math
from collections import defaultdict


def assignment(left, right, cost):
    """Solve a rectangular assignment with explicit unmatched columns.

    None forbids a pair. The unmatched penalty exceeds the cost of all valid
    pairs combined, so minimizing cost first maximizes the number of matches.
    """
    if not left or not right:
        return []
    from scipy.optimize import linear_sum_assignment

    values = [[cost(a, b) for b in right] for a in left]
    valid = [value for row in values for value in row if value is not None]
    if not valid:
        return []
    if any(not math.isfinite(value) or value < 0 for value in valid):
        raise ValueError("Matching costs must be finite and nonnegative")
    penalty = (max(valid) + 1) * (min(len(left), len(right)) + 1)
    matrix = [
        [penalty * 2 if v is None else v for v in row] + [penalty] * len(left) for row in values
    ]
    rows, columns = linear_sum_assignment(matrix)
    return [
        (int(row), int(column))
        for row, column in zip(rows, columns)
        if column < len(right) and values[row][column] is not None
    ]


def match_by_key(left, right, key, tolerance=None):
    a, b = defaultdict(list), defaultdict(list)
    for index, item in enumerate(left):
        a[key(item)].append((index, item))
    for index, item in enumerate(right):
        b[key(item)].append((index, item))
    result: list[tuple[int, int]] = []
    for identity in a.keys() & b.keys():
        first, second = a[identity], b[identity]

        def cost(x, y):
            distance = abs((x[1].offset or 0) - (y[1].offset or 0))
            return distance if tolerance is None or distance <= tolerance else None

        if len(first) == len(second) == 1:
            matches = [(0, 0)] if cost(first[0], second[0]) is not None else []
        else:
            matches = assignment(first, second, cost)
        result.extend((first[i][0], second[j][0]) for i, j in matches)
    return result

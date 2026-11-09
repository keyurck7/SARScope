"""Area accounting on explicit support; no missing pixels imputed as land cover."""
import csv
from pathlib import Path
import numpy as np
from common import CLASSES, write

def statistics(labels, months, pixel_area_m2=100.0):
    labels = np.asarray(labels)
    if labels.ndim != 3 or len(labels) != len(months) or len(set(months)) != len(months):
        raise ValueError('Expected one label map per unique month')
    if not np.isin(labels, list(range(9)) + [255]).all() or pixel_area_m2 <= 0:
        raise ValueError('Invalid class or pixel area')
    area = labels.shape[1] * labels.shape[2] * pixel_area_m2
    rows = []
    for month, lab in zip(months, labels):
        valid = lab < 9; n = int(valid.sum())
        for k, name in list(enumerate(CLASSES)) + [(255, 'unobserved')]:
            count = int((lab == k).sum())
            rows.append({'month': month, 'class_id': k, 'class': name, 'pixels': count,
                         'area_km2': count * pixel_area_m2 / 1e6,
                         'percent_full_aoi': count * pixel_area_m2 / area * 100,
                         'percent_observed': 100 * count / n if n and k < 9 else None,
                         'coverage_percent': n * pixel_area_m2 / area * 100})
    pairs = [(i-1, i, 'consecutive') for i in range(1, len(months))]
    if len(months) > 1: pairs.append((0, len(months)-1, 'first_to_last'))
    changes, transitions = [], []
    for i, j, kind in pairs:
        a, b = labels[i], labels[j]
        common = (a < 9) & (b < 9); n = int(common.sum())
        matrix = np.bincount((a[common].astype(int)*9 + b[common]), minlength=81).reshape(9,9)
        for k, name in enumerate(CLASSES):
            before, after = int(matrix[k].sum()), int(matrix[:,k].sum())
            changes.append({'comparison': kind, 'from_month': months[i], 'to_month': months[j], 'class': name,
                            'common_pixels': n, 'common_coverage_percent': 100*n / a.size,
                            'before_percent': 100*before/n if n else None,
                            'after_percent': 100*after/n if n else None,
                            'change_percentage_points': 100*(after-before)/n if n else None,
                            'net_area_change_km2_common': (after-before)*pixel_area_m2/1e6 if n else None,
                            'changed_pixel_percent_common': 100*(n-int(np.trace(matrix)))/n if n else None})
        transitions.append({'comparison': kind, 'from_month': months[i], 'to_month': months[j],
                            'common_pixels': n, 'matrix_from_rows_to_columns': matrix.tolist()})
    return rows, changes, transitions

def save_tables(folder, labels, months):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    rows, changes, transitions = statistics(labels, months)
    for name, data in [('monthly_shares.csv', rows), ('changes.csv', changes)]:
        with (folder / name).open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    write(folder / 'transitions.json', transitions)
    write(folder / 'accounting.json', {
        'classes': CLASSES, 'area_method': 'UTM projected area; 100 m² per 10 m pixel (not geodesic area)',
        'monthly_denominator': 'Full fixed AOI, including unobserved; additional observed-only percentages provided',
        'change_denominator': 'Pixels observed in both compared months; common coverage reported for every pair',
        'change_unit': 'percentage points; after minus before, on the same pixels',
        'interpretation': 'Predicted land-cover changes; seasonality and classification error can produce apparent transitions',
        'no_common_support': 'Null changes, never zero change', 'area_km2': labels.shape[1]*labels.shape[2]/10000})
    return rows, changes

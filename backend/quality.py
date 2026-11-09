"""Evidence-quality and anomaly review; does not alter predictions or claim accuracy.

The thresholds are transparent *review triggers*, not statistical significance
or probabilities. Acquisition scene counts describe intersecting scenes, not
number of valid per-pixel observations. Never score geographic correctness.
"""
import math

RULES={
    'limited_scene_count': 'One or two intersecting Sentinel-1 scenes; temporal support may be limited.',
    'missing_acquisition_receipt': 'No source receipt available for this month; observation provenance cannot be checked.',
    'incomplete_coverage': 'Less than 95% of the requested AOI has predicted labels; use common observed support.',
    'dominant_class': 'A single predicted class covers at least 90% of the AOI. Review against a suitable independent reference; high dominance is not automatically an error.',
    'large_monthly_shift': 'At least one class changed by 5 or more percentage points from the previous month. This is predicted change, not a verified event.',
    'snow_ice_surge': 'Predicted snow/ice expanded by at least 5 percentage points since the preceding month. Inspect seasonal/geographic plausibility and reference evidence.',
}

def review_months(months, ambiguity=None):
    """Return metadata per month. Accepts API-ready month dicts with source receipts and shares."""
    result=[]; previous=None
    values=ambiguity.get('values',[]) if isinstance(ambiguity,dict) else []
    for i,month in enumerate(months):
        source=month.get('acquisition') or {}
        count=source.get('source_count') if source.get('available') else None
        shares={int(x['class_id']):float(x['percent']) for x in month.get('shares',[])}
        warnings=[]
        if count is None: warnings.append({'code':'missing_acquisition_receipt','message':RULES['missing_acquisition_receipt']})
        elif count<=2: warnings.append({'code':'limited_scene_count','message':RULES['limited_scene_count']})
        if month.get('coverage',0)<95: warnings.append({'code':'incomplete_coverage','message':RULES['incomplete_coverage']})
        if any(x>=90 for x in shares.values()): warnings.append({'code':'dominant_class','message':RULES['dominant_class']})
        biggest=None
        if previous is not None:
            changes={k:shares.get(k,0)-previous.get(k,0) for k in set(previous)|set(shares)}
            if changes:
                c=max(changes,key=lambda k:(abs(changes[k]),-k));delta=changes[c]
                if abs(delta)>=5:
                    biggest={'class_id':c,'change_percentage_points':round(delta,3)}
                    warnings.append({'code':'large_monthly_shift','message':RULES['large_monthly_shift']})
                if changes.get(8,0)>=5:
                    warnings.append({'code':'snow_ice_surge','message':RULES['snow_ice_surge']})
        entropy=values[i] if i<len(values) else None
        if not isinstance(entropy,(int,float)) or not math.isfinite(entropy) or not (0<=entropy<=1):entropy=None
        result.append({'month':month.get('month'),'source_scene_count':count,'coverage_percent':round(float(month.get('coverage',0)),4),
                       'normalized_entropy':entropy,'entropy_interpretation':'Uncalibrated model uncertainty indicator; NOT probability of error',
                       'warnings':warnings,'biggest_class_shift':biggest,'quality_label':'REVIEW' if warnings else 'NO_RULE_TRIGGERED'})
        previous=shares
    return result

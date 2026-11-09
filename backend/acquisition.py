"""Request timing and public acquisition provenance; never changes model inputs."""
from datetime import datetime, timezone
import json

def latest_start(today=None):
    today = today or datetime.now(timezone.utc).date()
    return f"{today.year-1:04d}-{today.month:02d}"

def public_sources(folder, month):
    path = folder / 'acquisition_receipts.json'
    receipts = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    receipt = next((r for r in receipts if r.get('identity', {}).get('month') == month), None)
    if receipt is None:
        return {'available': False, 'reason': 'Acquisition receipts were not included in this saved review.'}
    stamps = receipt.get('source_timestamps_ms', [])
    def iso(value):
        return datetime.fromtimestamp(value/1000, timezone.utc).isoformat().replace('+00:00','Z')
    return {'available': True, 'collection': receipt.get('collection'),
            'source_count': len(receipt.get('source_indices', [])),
            'earliest_acquisition': iso(min(stamps)) if stamps else None,
            'latest_acquisition': iso(max(stamps)) if stamps else None,
            'retrieved_at': receipt.get('retrieved_at'),
            'orbit_policy': receipt.get('orbit_policy'),
            'note': 'Scene inventory intersecting the tile; individual pixels may have fewer valid observations.'}

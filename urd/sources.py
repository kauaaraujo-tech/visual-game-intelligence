"""Pointers to inspected instrumentation, never automatic blame attribution."""
from urd.adapters.hookshot import SOURCE_COMMIT, PERFORMANCE_HEADER


def correlate_sources(report: dict) -> list[dict]:
    metadata=report.get('metadata',{})
    if metadata.get('adapter')!='hookshot' or metadata.get('parser_source_commit')!=SOURCE_COMMIT:
        return []
    rows=[]
    for incident in report.get('incidents',[]):
        for item in incident.get('events',[]):
            event=item['event']
            if event.get('kind') in PERFORMANCE_HEADER and event['kind'].endswith('_ms'):
                rows.append({'evidence_id':event['id'],'metric':event['kind'],
                             'source_commit':SOURCE_COMMIT,'path':'gpu/vk/vk_replay.cpp','line':3251,
                             'url':f'https://github.com/NotRexed/Hookshot/blob/{SOURCE_COMMIT}/gpu/vk/vk_replay.cpp#L3251',
                             'relation':'instrumentation_emission_only','binary_version_verified':False,
                             'limitation':'Points to CSV metric emission; neither faulty-code attribution nor verification of the installed build.'})
    return rows

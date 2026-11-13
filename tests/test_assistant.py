import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urd.assistant import make_brief, validate_suggestions, request_local
from urd.sources import correlate_sources


def report():
    return {'schema_version':1,'session_id':'s','synthetic':True,
            'metadata':{'adapter':'hookshot','parser_source_commit':'e9975d6c245275aaf89a34e8d17a6bbe8badab46'},
            'incidents':[{'id':'i1','start_ns':0,'end_ns':10000000,'frame_ids':[1], 'baseline_ms':16,'peak_ms':80,'threshold_ms':24,
                          'events':[{'event':{'id':'e1','kind':'pipe_wait_ms','message':'SECRET PROPRIETARY DATA','source':{'file':'trace.csv','line':2}},'association':'exact_frame'}],
                          'captures':[{'capture':{'path':'/PRIVATE/IMAGE.png'},'association':'exact_frame'}]}],
            'provenance':[{'file':'PRIVATE-name','sha256':'x'*64}], 'limitations':['incomplete GPU timing']}

class AssistantTests(unittest.TestCase):
    def test_brief_excludes_raw_logs_images_paths(self):
        brief=make_brief(report())
        serialized=json.dumps(brief)
        self.assertNotIn('SECRET',serialized)
        self.assertNotIn('PRIVATE',serialized)
        self.assertIn('e1',brief['evidence_ids'])
        self.assertTrue(brief['synthetic'])
    def test_model_cannot_invent_evidence_or_claim_proof(self):
        good={'hypotheses':[{'claim':'May be wait related','confidence':'low','evidence_ids':['e1'],'next_test':'Repeat controlled scene'}]}
        result=validate_suggestions(good,make_brief(report()))
        self.assertEqual(result['hypotheses'][0]['status'],'untrusted_model_hypothesis')
        self.assertFalse(result['causality_verified'])
        for change in [{'evidence_ids':['invented']},{'confidence':'proven'},{'next_test':''}]:
            bad=json.loads(json.dumps(good)); bad['hypotheses'][0].update(change)
            with self.assertRaises(ValueError): validate_suggestions(bad,make_brief(report()))
    def test_source_links_are_instrumentation_not_cause(self):
        result=correlate_sources(report())
        self.assertEqual(result[0]['evidence_id'],'e1')
        self.assertIn('e9975d6c',result[0]['url'])
        self.assertEqual(result[0]['relation'],'instrumentation_emission_only')
        self.assertFalse(result[0]['binary_version_verified'])
    def test_wrong_source_commit_never_maps(self):
        r=report(); r['metadata']['parser_source_commit']='other'
        self.assertEqual(correlate_sources(r),[])
    def test_local_api_roundtrip_no_external_urls(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers()
                suggestions={'hypotheses':[{'claim':'Potential wait','confidence':'low','evidence_ids':['e1'],'next_test':'Repeat'}]}
                self.wfile.write(json.dumps({'response':json.dumps(suggestions)}).encode())
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            result=request_local(report(),model='test-local',port=server.server_port)
            self.assertFalse(result['causality_verified'])
            self.assertEqual(received[0]['model'],'test-local')
            self.assertNotIn('SECRET',received[0]['prompt'])
        finally:
            server.shutdown(); server.server_close(); thread.join()
    def test_invalid_local_request_fails_before_network(self):
        for port in [0,65536,True]:
            with self.assertRaises(ValueError): request_local(report(),model='x',port=port)

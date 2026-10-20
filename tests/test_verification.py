import copy
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import documents
import organizer
import research
import verification
import test_research


class VerificationTests(unittest.TestCase):
    setUp=test_research.ResearchTests.setUp
    tearDown=test_research.ResearchTests.tearDown
    job=test_research.ResearchTests.job
    # Reuse isolated DB fixtures, without inheriting the other tests below.
    def claim(self,kind='fact'):
        return {'id':'1','original':'公开过程可以帮助建立连接。','statement':'公开过程可以帮助建立连接。','kind':kind,'query':'公开过程 连接 证据'}

    def prepared(self,kind='fact'):
        job=self.job(True,'verify');job.update(status='awaiting_confirmation',claims=[self.claim(kind)])
        research.save(job);return job

    def test_prepare_waits_without_search_and_anchors_exact_text(self):
        job=self.job(True,'verify')
        row=self.claim();row['original']='公开过程';row['statement']='公开过程'
        with patch.object(organizer,'request_json',return_value=({'claims':[row]},{})),patch.object(research,'collected_sources') as search:
            research.run(job)
        self.assertEqual(job['status'],'awaiting_confirmation');search.assert_not_called()
        self.assertEqual(job['claims'][0]['anchor']['exact'],'公开过程')

    def test_fabricated_original_is_rejected_before_confirmation(self):
        job=self.job(True,'verify')
        with patch.object(organizer,'request_json',return_value=({'claims':[self.claim()]},{})):
            research.run(job)
        self.assertEqual(job['status'],'failed') # selection only contains 公开过程

    def test_confirm_is_single_submit_and_rejects_foreign_ids(self):
        job=self.prepared()
        with self.assertRaises(ValueError):verification.confirm(job['id'],['other'])
        with patch.object(research.EXECUTOR,'submit') as submit:
            verification.confirm(job['id'],['1'])
            with self.assertRaises(documents.Conflict):verification.confirm(job['id'],['1'])
        submit.assert_called_once()

    def test_confirm_rejects_changed_draft(self):
        job=self.prepared();job['context']=research.context(self.task,'draft',1,None,'公开过程');research.save(job)
        doc=documents.get(self.task)
        documents.save(self.task,doc['revision'],doc['content'])
        with self.assertRaises(documents.Conflict):verification.confirm(job['id'],['1'])

    def test_cancel_confirmation_cannot_submit(self):
        job=self.prepared();research.cancel(job['id'])
        with self.assertRaises(documents.Conflict):verification.confirm(job['id'],['1'])

    def test_no_web_evidence_is_completed_insufficient_without_inference(self):
        job=self.prepared();job['selected_claim_ids']=['1']
        with patch.object(research,'collected_sources',return_value=[]),patch.object(organizer,'request_json') as request:
            verification.run(job)
        self.assertEqual(job['status'],'completed');self.assertEqual(job['verdicts'][0]['decision'],'insufficient')
        request.assert_not_called()

    def test_opinion_never_searches_or_becomes_fact(self):
        job=self.prepared('opinion');job['selected_claim_ids']=['1']
        with patch.object(research,'collected_sources') as search,patch.object(organizer,'request_json') as request:
            verification.run(job)
        search.assert_not_called();request.assert_not_called()
        self.assertEqual(job['verdicts'][0]['decision'],'opinion')

    def test_forged_quotes_and_current_manuscript_cannot_support_claim(self):
        claim=self.claim();sources=[{'id':'current','kind':'passage','body':'公司赚了一百万元。'}]
        data={'results':[{'claim_id':'1','decision':'supported','citations':[{'source_id':'current','quote':'公司赚了一百万元。','relation':'supports'}]}]}
        self.assertEqual(verification.result_rows([claim],data,sources)[0]['decision'],'insufficient')

    def test_conflicting_relations_downgrade_supported_to_partial(self):
        sources=[{'id':'web-1','kind':'web','url':'https://example.com','body':'实验一显示有效，实验二显示无效。'}]
        value={'results':[{'claim_id':'1','decision':'supported','citations':[{'source_id':'web-1','quote':'实验一显示有效','relation':'supports'},
                    {'source_id':'web-1','quote':'实验二显示无效','relation':'contradicts'}]}]}
        row=verification.result_rows([self.claim()],value,sources)[0]
        self.assertEqual(row['decision'],'partial');self.assertEqual(row['source_domains'],['example.com'])

    def test_second_review_disagreement_fails_closed_and_exports(self):
        job=self.prepared();job['selected_claim_ids']=['1']
        source={'id':'web-1','kind':'web','url':'https://example.com','title':'实验记录','body':'只记录了参与人数，没有公布转化结果。'}
        responses=[({'results':[{'claim_id':'1','decision':'supported','reason':'参与了就有效','citations':[{'source_id':'web-1','quote':'只记录了参与人数','relation':'supports'}]}]},{}),
                   ({'reviews':[{'claim_id':'1','valid':False,'reason':'人数不支持有效性'}]}, {})]
        before=copy.deepcopy(documents.get(self.task))
        with patch.object(research,'collected_sources',return_value=[source]),patch.object(organizer,'request_json',side_effect=responses):verification.run(job)
        self.assertEqual(job['verdicts'][0]['decision'],'insufficient');self.assertEqual(job['verdicts'][0]['citations'],[])
        self.assertEqual(documents.get(self.task),before)
        note=research.save_note(job['id'],'测试核实','保留疑问')
        self.assertIn('证据不足',research.export_note(note['id']))

    def test_api_confirm_origin_and_duplicate(self):
        job=self.prepared()
        with TestClient(app.app) as client,patch.object(research.EXECUTOR,'submit'):
            path='/api/studio/research/jobs/'+job['id']+'/confirm';body={'claim_ids':['1']}
            self.assertEqual(client.post(path,json=body,headers={'Origin':'https://evil.test'}).status_code,403)
            self.assertEqual(client.post(path,json=body).status_code,200)
            self.assertEqual(client.post(path,json=body).status_code,409)

    def test_temporary_limit_expires_by_date(self):
        self.assertIsNone(organizer.daily_call_limit('2026-10-20'))
        self.assertEqual(organizer.daily_call_limit('2026-10-21'),30)
        self.assertEqual(organizer.daily_call_limit('2026-10-19'),30)
        self.assertEqual(organizer.daily_call_limit('2027-10-20'),30)


    def test_user_can_correct_model_claim_type_without_changing_original(self):
        job=self.prepared('opinion')
        with patch.object(research.EXECUTOR,'submit'):
            result=verification.confirm(job['id'],['1'],{'1':'fact'})
        self.assertEqual(result['confirmed_claims'][0]['kind'],'fact')
        self.assertEqual(result['claims'][0]['kind'],'opinion')
        self.assertEqual(result['confirmed_claims'][0]['original'],job['claims'][0]['original'])

    def test_invalid_classification_or_foreign_claim_is_rejected(self):
        job=self.prepared()
        for kinds in [{'2':'fact'},{'1':'truth'}]:
            with self.assertRaises(ValueError):verification.confirm(job['id'],['1'],kinds)
        self.assertEqual(research.get(job['id'])['status'],'awaiting_confirmation')

    def test_positive_and_negative_relations_require_review_and_exact_spans(self):
        for decision,relation in [('supported','supports'),('refuted','contradicts')]:
            job=self.prepared();job['selected_claim_ids']=['1']
            source={'id':'web-1','kind':'web','url':'https://example.com','title':'实验','body':'实验观察到明确的结果。'}
            answers=[({'results':[{'claim_id':'1','decision':decision,'reason':'测试证据','citations':[{'source_id':'web-1','quote':'实验观察到明确的结果','relation':relation}]}]},{}),
                     ({'reviews':[{'claim_id':'1','valid':True,'reason':'直接支持关系'}]}, {})]
            with patch.object(research,'collected_sources',return_value=[source]),patch.object(organizer,'request_json',side_effect=answers):verification.run(job)
            row=job['verdicts'][0]
            self.assertEqual(row['decision'],decision);self.assertEqual(row['support_status'],'model_checked')
            cite=row['citations'][0];self.assertEqual(source['body'][cite['start']:cite['end']],cite['quote'])
            note=research.save_note(job['id'],'关系导出'+decision,'')
            self.assertIn('证据关系（AI建议）：'+('支持' if relation=='supports' else '反驳'),research.export_note(note['id']))

    def test_review_failure_never_publishes_first_pass_verdict(self):
        job=self.prepared();job['selected_claim_ids']=['1']
        source={'id':'web-1','kind':'web','url':'https://example.com','title':'实验','body':'实验观察到明确的结果。'}
        answers=[({'results':[{'claim_id':'1','decision':'supported','citations':[{'source_id':'web-1','quote':'实验观察到明确的结果','relation':'supports'}]}]},{}),RuntimeError('限额')]
        with patch.object(research,'collected_sources',return_value=[source]),patch.object(organizer,'request_json',side_effect=answers):verification.run(job)
        self.assertEqual(job['status'],'failed');self.assertNotIn('verdicts',job)

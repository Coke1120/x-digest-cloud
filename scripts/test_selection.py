"""Offline behavior checks; synthetic evidence never enters a live snapshot."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gather import plan
from prefilter import select_candidates, selection_report
from source_pool import load_pool, rotation, account_hints, active_accounts
import copy
from source_health import build as build_health

EXAMPLE_POOL = Path(__file__).resolve().parents[1] / 'examples' / 'source_pool.json'


def fixture_pool():
    pool = load_pool(EXAMPLE_POOL)
    for account in pool['accounts']:
        account['status'] = 'active'
        account['reviewed_at'] = '2026-10-03'
    return pool


def health(snapshot, previous, pool):
    return build_health(snapshot, previous, pool, source_repository='example/x-digest-cloud')

NOW = datetime.now(timezone.utc)
def row(number, handle, text, likes=0, views=0, age=1):
    return {'id':str(1980000000000000000+number),'handle':handle,'name':handle,
            'text':text[:280],'_full_text':text,'createdAt':(NOW-timedelta(hours=age)).isoformat(),
            'likes':likes,'views':views,'retweets':0,'isRetweet':False,'source':'search-latest-00.json'}

class SelectionTests(unittest.TestCase):
    def test_substantive_small_builder_beats_viral_reaction(self):
        rows=[row(1,'sama','AI is fun',10**7,10**10),row(2,'newbuilder','Released an open-source LLM inference tool on GitHub, benchmark latency fell 40% using 8 GB VRAM.')]
        output=select_candidates(rows,2,{'sama'},NOW)
        self.assertEqual(output[0]['handle'],'newbuilder')
        self.assertIn('measurement',output[0]['quality_signals'])

    def test_full_text_signals_after_preview_and_private_fields_removed(self):
        text='Our AI tool has an update. '+('Context details. '*22)+' Released on GitHub with reproducible benchmark: latency 20 ms.'
        output=select_candidates([row(1,'builder',text)],1,set(),NOW)
        self.assertIn('measurement',output[0]['quality_signals'])
        self.assertNotIn('_full_text',output[0]);self.assertLessEqual(len(output[0]['text']),280)

    def test_discovery_opportunities_author_limit_and_no_padding(self):
        rows=[row(i,'famous','Released LLM version '+str(i)+' on GitHub: latency 20 ms.',1000000) for i in range(20)]
        rows += [row(100+i,'small'+str(i),'Released LLM tool '+str(i)+' on GitHub: latency 30 ms.') for i in range(6)]
        output=select_candidates(rows,10,{'famous'},NOW)
        self.assertEqual(sum(r['handle']=='famous' for r in output),4)
        self.assertEqual(sum(r['selection_lane']=='discovery' for r in output),6)
        self.assertEqual(len(select_candidates(rows,150,{'famous'},NOW)),10)

    def test_noise_invalid_time_retweets_and_copied_posts(self):
        rows=[row(1,'a','Released an LLM tool on GitHub'),row(2,'b','Released an LLM tool on GitHub'),row(3,'c','My breakfast was nice today'),row(4,'d','Released an LLM tool on GitHub',age=-1),row(5,'e','Released an LLM tool on GitHub',age=27),row(6,'f','AI giveaway airdrop check your wallet balance https://example.test')]
        bad=row(7,'g','Released an LLM tool on GitHub');bad['isRetweet']=True;rows.append(bad)
        bad=row(8,'h','Released an LLM tool on GitHub');bad['createdAt']='unknown';rows.append(bad)
        self.assertEqual(len(select_candidates(rows,150,set(),NOW)),1)

    def test_limit_one_never_overflows_reserved_pools(self):
        rows=[row(1,'a','Released LLM A on GitHub'),row(2,'b','Released LLM B on GitHub')]
        self.assertEqual(len(select_candidates(rows,1,{'a'},NOW)),1)

    def test_high_volume_topic_cannot_crowd_out_other_categories(self):
        texts=['Released LLM model weights on GitHub', 'Released Codex agent on GitHub', 'Released MCP SDK on GitHub', 'AI partnership capacity announced 5%', 'Startup earnings revenue reported 50%', 'MLX quantization benchmark 40 tok/s', 'AI privacy security advisory released', 'GPU HBM specifications announced 80 GB', 'Hong Kong transport government approved service reform', 'Ceasefire treaty signed by government', 'Clinical trial results published for vaccine', 'Typhoon evacuation warning confirmed']
        rows=[]
        for category,text in enumerate(texts):
            for i in range(100 if category==0 else 26):
                number=category*1000+i
                rows.append(row(number,'builder'+str(number),text+' project '+str(number)+' with detailed verifiable context.',likes=100000 if category==0 else 0))
        output=select_candidates(rows,150,set(),NOW)
        counts={category:sum(r['category']==category for r in output) for category in {r['category'] for r in output}}
        self.assertEqual(len(counts),12)
        self.assertEqual(len(output),150)
        self.assertTrue(all(count>=10 for count in counts.values()),counts)

    def test_general_news_requires_development_and_finance_is_broad(self):
        rows=[row(1,'a','Hong Kong government is so annoying. '*5),
              row(2,'b','Ceasefire treaty signed after government talks; confirmed terms are published.'),
              row(3,'c','Central bank announced interest rate decision after inflation data.'),
              row(4,'d','Clinical trial results published for vaccine; the study reports its limitations.'),
              row(5,'e','Typhoon warning confirmed with evacuation notices for coastal residents.')]
        out=select_candidates(rows,150,set(),NOW)
        self.assertEqual({r['category'] for r in out},{'國際重大新聞','財經','科學／醫療與健康','環境／能源與公共安全'})
        self.assertNotIn('a',{r['handle'] for r in out})

    def test_hardware_measurements_and_financing_are_distinct(self):
        rows=[row(1,'a','Released GPU HBM specifications: memory capacity 80 GB.'),
              row(2,'b','MLX GPU quantization benchmark: Qwen Q4 with batch 1, context 8k achieved 40 tok/s.'),
              row(3,'c','GPU infrastructure funding round reported a valuation of 20 billion dollars.')]
        out=select_candidates(rows,150,set(),NOW)
        self.assertEqual({r['category'] for r in out},{'算力／晶片與硬件','本地 AI／部署與推理','財經'})

    def test_cli_preserves_all_source_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);tweet={'id':'1980000000000000001','author':{'screenName':'builder','name':'Builder'},'text':'Released an LLM tool on GitHub, with latency 20 ms.','createdAtISO':NOW.isoformat(),'isRetweet':False,'metrics':{'views':100}}
            for name in ['search-top-00.json','search-latest-00.json']:(root/name).write_text(json.dumps({'data':[tweet]}))
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('prefilter.py')),str(root),'-o',str(root/'out.jsonl'),'--source-pool',str(EXAMPLE_POOL)],capture_output=True,text=True,check=True)
            output=json.loads((root/'out.jsonl').read_text())
            self.assertEqual(output['sources'],['search-latest-00.json','search-top-00.json'])
            self.assertEqual(json.loads(result.stdout)['distinct_authors'],1)

    def test_collection_plan_has_both_orders_and_only_read_commands(self):
        fixed=datetime(2026,10,3,tzinfo=timezone.utc)
        jobs=plan('2026-10-01',12,4,pool=fixture_pool(),now=fixed,rotation_hour=0)
        searches=[command for _,command in jobs if command[0]=='search']
        self.assertEqual(len(jobs),40);self.assertEqual(len(searches),24)
        self.assertEqual(len([c for _,c in jobs if c[0]=='user-posts']),14)
        for query in {c[1] for c in searches}:
            self.assertEqual({command[command.index('-t')+1] for command in searches if command[1]==query},{'Top','Latest'})
        self.assertTrue(all(command[0] in {'search','feed','user-posts'} for _,command in jobs))

    def test_rotation_reaches_every_source_and_every_query_without_duplicates(self):
        pool=fixture_pool();fixed=datetime(2026,10,3,tzinfo=timezone.utc)
        handles,queries=set(),set()
        plans=[rotation(pool,fixed,h) for h in range(24)]
        for selected in plans:
            current=[a['handle'].lower() for a in selected['accounts']]
            self.assertEqual(len(current),14);self.assertEqual(len(set(current)),14)
            self.assertTrue(all(a['handle'].lower() in current for a in pool['accounts'] if a['core']))
            handles.update(current);queries.update(q['query'] for q in selected['queries'])
            self.assertEqual(set(q['topic'] for q in selected['queries']),set(pool['topics']))
        self.assertEqual(handles,{a['handle'].lower() for a in pool['accounts']})
        self.assertEqual(queries,{q for options in pool['topics'].values() for q in options})
        self.assertNotEqual(plans[0]['accounts'],plans[1]['accounts'])

    def test_paused_and_unreviewed_sources_are_not_sampled(self):
        pool=copy.deepcopy(fixture_pool());pool['accounts'][4]['status']='paused'
        pool['accounts'][5]['reviewed_at']='2026-01-01'
        selected=rotation(pool,datetime(2026,10,3,tzinfo=timezone.utc),0)
        sampled={a['handle'] for a in selected['accounts']}
        self.assertNotIn(pool['accounts'][4]['handle'],sampled)
        self.assertNotIn(pool['accounts'][5]['handle'],sampled)
        self.assertIn(pool['accounts'][5]['handle'],selected['review_due'])

    def test_hong_kong_review_date_accepts_current_evening_utc(self):
        pool=fixture_pool()
        self.assertEqual(len(active_accounts(pool,datetime(2026,10,2,18,tzinfo=timezone.utc))),len(pool['accounts']))

    def test_pure_long_opinion_and_trade_hype_cannot_fill_a_category(self):
        rows=[row(1,'famous','AI will change everything. '*20,10**8),
              row(2,'pumper','AI earnings growth 50% my bias is bullish buy now https://example.test'),
              row(3,'builder','I tested Qwen Q4 on RTX 3090 with batch 1 and 8k context: benchmark 40 tok/s; reproduce with this script.')]
        output=select_candidates(rows,150,set(),NOW)
        self.assertEqual([r['handle'] for r in output],['builder'])
        self.assertEqual(output[0]['claim_kind_hint'],'measurement_claim')
        self.assertEqual(set(output[0]['measurement_context_hint']),{'hardware','model_or_precision','method'})

    def test_account_role_does_not_make_a_claim_first_party_or_boost_its_score(self):
        base=row(1,'sample_source04','Released an AI tool on GitHub, benchmark 20 ms.')
        plain=select_candidates([base],1,set(),NOW)[0]
        tagged=select_candidates([base],1,set(),NOW,hints=account_hints(fixture_pool()))[0]
        self.assertEqual(plain['selection_score'],tagged['selection_score'])
        self.assertEqual(tagged['source_role_hint'],'community')
        self.assertFalse(tagged['first_person_hint'])

    def test_private_funnel_and_proposals_do_not_assert_semantic_review(self):
        rows=[row(1,'outsider','Released LLM A on GitHub'),row(2,'opinion','AI is nice. '*20)]
        selected=select_candidates(rows,150,set(),NOW)
        report=selection_report(rows,selected,NOW,{})
        self.assertFalse(report['semantic_reviewed'])
        self.assertEqual(report['category_funnel']['AI 模型與研究']['weak_or_promotional'],1)
        self.assertEqual(report['source_proposals'][0]['status'],'unreviewed')

    def test_health_retains_distinct_evidence_without_automatic_promotion(self):
        base = {'schema_version': 1, 'source_repository': 'example/x-digest-cloud',
                'run_id': 'offline-test-1', 'collected_at': NOW.isoformat(), 'coverage': {'ok': True},
                'records': [{'id': '1980000000000000001', 'author': {'screenName': 'newbuilder'},
                             'text': 'Offline fixture, never publish.', 'createdAtISO': (NOW-timedelta(hours=2)).isoformat(),
                             'isRetweet': False, 'candidate_context': {'category': '開發者工具'}}]}
        first = health(base, {}, fixture_pool())
        second = health(base, first, fixture_pool())
        self.assertEqual(len(second['runs']), 1)
        self.assertEqual(second['sources'][0]['distinct_posts_retained'], 1)
        self.assertEqual(second['sources'][0]['status'], 'unreviewed')
        self.assertFalse(second['semantic_reviewed'])
        base['run_id'] = 'offline-test-2'
        base['collected_at'] = (NOW+timedelta(days=8)).isoformat()
        base['records'][0]['id'] = '1980000000000000002'
        base['records'][0]['createdAtISO'] = (NOW+timedelta(days=8, hours=-1)).isoformat()
        third = health(base, second, fixture_pool())
        self.assertEqual(len(third['runs']), 1)
        self.assertEqual(third['sources'][0]['distinct_posts_retained'], 1)
        self.assertEqual(third['sources'][0]['posts'][0]['id'], '1980000000000000002')

    def test_failed_collection_cannot_advance_source_health(self):
        with self.assertRaisesRegex(ValueError, 'invalid_health_snapshot'):
            health({'schema_version': 1, 'coverage': {'ok': False}, 'records': [{}]}, {}, fixture_pool())

if __name__=='__main__':unittest.main()


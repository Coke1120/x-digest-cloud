"""Offline behavior checks; synthetic evidence never enters a live snapshot."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gather import plan, QUERIES, WATCHLIST
from prefilter import select_candidates

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
        texts=['Released LLM benchmark on GitHub', 'Released Codex skill on GitHub', 'Released MCP SDK on GitHub', 'AI copyright regulation research report: licensing cost changed 5%', 'AI startup funding revenue report: revenue increased 50%']
        rows=[]
        for category,text in enumerate(texts):
            for i in range(100 if category==0 else 26):
                number=category*1000+i
                rows.append(row(number,'builder'+str(number),text+' project '+str(number)+' with detailed verifiable technical context.',likes=100000 if category==0 else 0))
        output=select_candidates(rows,150,set(),NOW)
        counts={category:sum(r['category']==category for r in output) for category in {r['category'] for r in output}}
        self.assertEqual(len(counts),5)
        self.assertEqual(len(output),150)
        self.assertTrue(all(count>=24 for count in counts.values()),counts)

    def test_cli_preserves_all_source_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);tweet={'id':'1980000000000000001','author':{'screenName':'builder','name':'Builder'},'text':'Released an LLM tool on GitHub, with latency 20 ms.','createdAtISO':NOW.isoformat(),'isRetweet':False,'metrics':{'views':100}}
            for name in ['search-top-00.json','search-latest-00.json']:(root/name).write_text(json.dumps({'data':[tweet]}))
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('prefilter.py')),str(root),'-o',str(root/'out.jsonl')],capture_output=True,text=True,check=True)
            output=json.loads((root/'out.jsonl').read_text())
            self.assertEqual(output['sources'],['search-latest-00.json','search-top-00.json'])
            self.assertEqual(json.loads(result.stdout)['distinct_authors'],1)

    def test_collection_plan_has_both_orders_and_only_read_commands(self):
        jobs=plan('2026-10-01',12,4)
        searches=[command for _,command in jobs if command[0]=='search']
        self.assertEqual(len(searches),2*len(QUERIES));self.assertEqual(len(WATCHLIST),14)
        for query in QUERIES:
            self.assertEqual({command[command.index('-t')+1] for command in searches if command[1]==query},{'Top','Latest'})
        self.assertTrue(all(command[0] in {'search','feed','user-posts'} for _,command in jobs))

if __name__=='__main__':unittest.main()

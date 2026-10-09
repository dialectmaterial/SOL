"""Synthetic note-layout fixtures; no copyrighted book text is committed."""
from collections import Counter
import unittest

from sol_corpus_notes import extract_notes


def span(identifier,text,x,y,width=50,size=8,height=7.97,family='AGaramond'):
    return {'source_id':identifier,'text':text,'markdown':text,'x':x,'y':y,
            'width':width,'height':height,'size':size,'family':family}


def page(number,*spans):
    return {'number':number,'width':430,'height':646,'spans':list(spans)}


def prose(identifier='body',y=100):
    return span(identifier,'Synthetic main prose supplies a left margin.',53.5,y,
                width=310,size=11,height=10.96)


def label(identifier,text,x=53.5,y=397):
    return span(identifier,text,x,y,width=5,size=6,height=7.77,
                family='AGaramondExp')


class NoteExtractionTests(unittest.TestCase):
    def test_separates_inline_definitions(self):
        p=page(17,prose(),label('label22','22'),
               span('text22','Synthetic note alpha.',65,400,width=100),
               label('label23','23',x=185),
               span('text23','Synthetic note beta.',197,400,width=100))
        result=extract_notes([p])
        self.assertEqual([n['label'] for n in result['notes']],['22','23'])
        self.assertEqual(result['notes'][0]['source_ids'],['label22','text22'])
        self.assertEqual(result['notes'][1]['source_ids'],['label23','text23'])

    def test_nested_reference_is_not_new_definition(self):
        p=page(333,prose(),label('labeln','n'),
               span('textn','Synthetic note includes',65,400,width=100),
               label('nested145','145',x=165,y=397),
               span('tailn','a nested callout.',173,400,width=70),
               label('label145','145',y=427),
               span('text145','Synthetic nested-note body.',65,430,width=120))
        result=extract_notes([p])
        self.assertEqual([n['label'] for n in result['notes']],['n','145'])
        self.assertEqual(result['notes'][0]['callouts'][0]['source_id'],'nested145')

    def test_note_continues_across_pages(self):
        a=page(330,prose('body330'),label('label141','141'),
               span('start141','Synthetic unfinished note',65,400))
        b=page(331,prose('body331'),
               span('continued141','continued on the next page.',65,400),
               label('label142','142',y=427),
               span('text142','A separate synthetic note.',65,430))
        result=extract_notes([a,b])
        first=result['notes'][0]
        self.assertEqual((first['start_page'],first['end_page']),(330,331))
        self.assertEqual(first['continuation_pages'],[331])
        self.assertIn('continued141',first['source_ids'])
        self.assertEqual(result['warnings'],[])

    def test_body_callouts_do_not_start_note_region(self):
        p=page(80,prose(),span('callout','a',190,99,width=4,size=8,height=7.67))
        result=extract_notes([p])
        self.assertEqual(result['notes'],[])
        self.assertEqual(len(result['pages'][0]['body_spans']),2)

    def test_very_short_note_is_not_dropped(self):
        p=page(20,prose(),label('label37','37'),
               span('text37','AB',65,400,width=12),
               span('digits37','6',78,398.2,width=5,size=8,height=10.36,
                    family='AGaramondExp'))
        result=extract_notes([p])
        self.assertEqual(result['notes'][0]['source_ids'],
                         ['label37','text37','digits37'])

    def test_oldstyle_numbers_remain_in_line_order(self):
        p=page(331,prose(),label('label142','142'),
               span('text142','Synthetic person (',65,400,width=90),
               span('dagger142','†',155,398.2,width=4,size=8,height=10.36,
                    family='AGaramondItalic'),
               span('digits142','1618',159,398.2,width=15,size=8,height=10.36,
                    family='AGaramondExp'),
               span('tail142',') synthetic body.',174,400,width=80))
        result=extract_notes([p])
        self.assertEqual(result['notes'][0]['source_ids'],
                         ['label142','text142','dagger142','digits142','tail142'])

    def test_bibliography_and_index_are_not_footnotes(self):
        for number in [830,850]:
            p=page(number,span('small','Synthetic reference entry',53.5,400))
            result=extract_notes([p])
            self.assertEqual(result['notes'],[])
            self.assertEqual(result['pages'][0]['body_spans'],p['spans'])

    def test_every_span_is_consumed_once(self):
        pages=[page(80,prose('body'),label('label1','1'),
                    span('text1','Synthetic note body.',65,400))]
        result=extract_notes(pages)
        before=Counter(s['source_id'] for p in pages for s in p['spans'])
        after=Counter(s['source_id'] for p in result['pages'] for s in p['body_spans'])
        after.update(i for n in result['notes'] for i in n['source_ids'])
        self.assertEqual(before,after)
        self.assertTrue(all(count==1 for count in after.values()))

    def test_orphan_and_nonadjacent_continuations_are_explicit(self):
        orphan=page(80,prose('body80'),span('orphan','Synthetic continuation.',65,400))
        gap=page(83,prose('body83'),span('gap','Continuation after absent pages.',65,400))
        result=extract_notes([orphan,gap])
        self.assertTrue(result['notes'][0]['orphan'])
        self.assertEqual([w['code'] for w in result['warnings']],
                         ['orphan_note_continuation','nonadjacent_note_continuation'])

    def test_displayed_math_powers_do_not_split_the_note(self):
        p=page(299,prose(),label('labelk','k',y=247),
               span('intro','Synthetic explanation of an equation.',65,250,width=180),
               span('phi1','ϕ',195,287,width=4.5,size=8,height=10.36,family='RMTMI'),
               label('power2','2',x=200,y=286),
               span('math1','f t',206,294,width=12,size=8,height=7.65,
                    family='Garamond-BookCondensedItalic'),
               span('prose1','Synthetic intermediate explanation.',65,310,width=180),
               span('phi2','ϕ',225,326,width=4.5,size=8,height=10.36,family='RMTMI'),
               label('power3','3',x=230,y=325),
               span('math2','f t',236,333,width=12,size=8,height=7.65,
                    family='Garamond-BookCondensedItalic'),
               span('tail','Synthetic equation conclusion.',65,350,width=180),
               label('label102','102',y=397),
               span('text102','A separate actual synthetic note.',65,400,width=180))
        result=extract_notes([p])
        self.assertEqual([n['label'] for n in result['notes']],['k','102'])
        first=result['notes'][0]
        self.assertIn('power2',first['source_ids'])
        self.assertIn('power3',first['source_ids'])
        self.assertEqual(first['callouts'],[])
        self.assertIn('tail',first['source_ids'])
        self.assertEqual(Counter(s['source_id'] for s in p['spans']),
                         Counter(s['source_id'] for out in result['pages'] for s in out['body_spans'])
                         +Counter(i for n in result['notes'] for i in n['source_ids']))

    def test_detached_accent_does_not_steal_definition_baseline(self):
        p=page(545,prose(),label('label4','4',y=397.2),
               span('accent','¨',335,397.8,width=3),
               span('text4','Synthetic citation includes',65,400,width=260),
               span('title4','Uber a title',332,400,width=45,family='AGaramond-Italic'),
               label('label5','5',y=427.2),
               span('text5','Separate synthetic note.',65,430,width=150))
        result=extract_notes([p])
        self.assertEqual([n['label'] for n in result['notes']],['4','5'])
        self.assertIn('accent',result['notes'][0]['source_ids'])
        self.assertIn('text4',result['notes'][0]['source_ids'])

    def test_citation_can_begin_with_digits_or_opening_quotation(self):
        p=page(251,prose(),label('label38','38',y=397),
               span('citationdigits','987',65,398.2,width=11,size=8,height=10.36,
                    family='AGaramondExp'),
               span('citationprose','b, a synthetic citation.',76,400,width=130),
               label('label39','39',y=427),
               span('quotation','“ . . .',65,430,width=14),
               span('quotedprose','synthetic quoted material',81,430,width=150,
                    family='AGaramond-Italic'))
        result=extract_notes([p])
        self.assertEqual([n['label'] for n in result['notes']],['38','39'])
        self.assertIn('citationdigits',result['notes'][0]['source_ids'])
        self.assertIn('quotedprose',result['notes'][1]['source_ids'])


if __name__=='__main__':
    unittest.main()

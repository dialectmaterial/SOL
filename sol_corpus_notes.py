"""Poppler-span note segmentation for the audited Cambridge Science of Logic PDF.

Input: iterable of page dicts(number,width,height,spans), with span dicts
x,y,width,height,size,family,text,markdown,source_id. Coordinates are points
from pdftohtml -zoom 1 -noroundcoord. Never assigns stable corpus IDs.

Output has notes, pages (body_spans and note_source_ids), and warnings.
Every input span is returned exactly once in body_spans or a note's spans.
Callouts remain in their owner's span list and are additionally referenced
by source_id. The main importer must handle header/margin/footer exclusions.
"""
from collections import Counter
import re

LABEL = re.compile(r"(?:[a-z]|\d{1,3})\Z")

def _sid(span):
    return span['source_id']

def _size(span):
    return float(span.get('size',span.get('font_size',0)))

def _text(span):
    return span.get('text','').strip()

def _marker(span):
    return _size(span) <= 6.8 and bool(LABEL.fullmatch(_text(span)))

def _normal_note(span):
    # Exp oldstyle digits are taller than same-fontsize prose; base regular
    # and italic prose supply the reliable line anchor. Tiny math exponents
    # and body note callouts must not start a note region themselves.
    return (7.3 <= _size(span) <= 8.5 and 7.82 <= float(span.get('height',0)) <= 8.14
            and 'Exp' not in span.get('family','')
            and any(c.isalpha() for c in _text(span)))

def _left(page):
    candidates=[round(float(s['x']),1) for s in page['spans']
                if 10.3 <= _size(s) <= 11.7 and 50<float(s['y'])<550
                and len(_text(s))>=25]
    if candidates:
        counts=Counter(candidates)
        return max(counts,key=lambda x:(counts[x],-x))
    return 53.5

def _lines(spans):
    # Oldstyle digits have an earlier top than standard glyphs. Attach them
    # to regular/italic line anchors rather than create spurious date lines.
    anchors=[]
    for s in sorted(spans,key=lambda s:(float(s['y']),float(s['x']))):
        # Detached accent glyphs and punctuation are not independent prose
        # baselines. An umlaut above an italic word otherwise steals a nearby
        # note-definition marker away from the actual line of note text.
        if not _marker(s) and _normal_note(s):
            y=float(s['y'])
            if not anchors or min(abs(y-a) for a in anchors)>1:
                anchors.append(y)
    groups={y:[] for y in anchors}
    for s in spans:
        y=float(s['y'])
        if anchors:
            anchor=min(anchors,key=lambda a:abs(a-y))
            if abs(anchor-y)<=5.8:
                groups[anchor].append(s)
                continue
        # Retain any isolated unusual-font line rather than lose it.
        groups.setdefault(y,[]).append(s)
    return [(y,sorted(values,key=lambda s:float(s['x'])))
            for y,values in sorted(groups.items())]

def _definitions(line,left):
    output=[]
    for i,s in enumerate(line):
        if not _marker(s):continue
        x=float(s['x'])
        previous=line[i-1] if i else None
        gap=x-(float(previous['x'])+float(previous['width'])) if previous else 999
        # Definitions can be near left margin OR inline after a large gap.
        # Nested callouts follow punctuation with essentially zero gap.
        # Isolated formula powers are also six-point Arabic digits. A real
        # definition introduces nearby normal-size note prose on this line;
        # a numerator/exponent on a separate equation row does not. Bare
        # powers must remain content of the current note rather than create
        # synthetic notes which own the remainder of its text.
        # Citations may begin with a regular-size number or opening quotation
        # before the first alphabetic prose span, so do not require that prose
        # to sit immediately beside the definition marker.
        following=[t for t in line[i+1:] if _normal_note(t)]
        if (x<=left+9 or gap>=9) and following:
            output.append(i)
    return output

def _math_power(span,region):
    """A tiny digit attached to a mathematical glyph is not a note callout."""
    if not _text(span).isdigit():
        return False
    x=float(span['x'])
    y=float(span['y'])
    for previous in region:
        family=previous.get('family','')
        mathematical=any(name in family for name in
                         ('RMTMI','MTSY','Math','Garamond-BookCondensedItalic'))
        if (mathematical and _text(previous)
                and -0.5<=x-float(previous['x'])-float(previous['width'])<=2.5
                and -10<=y-float(previous['y'])<=2):
            return True
    return False

def _new_note(label,page,span,orphan=False):
    return {'label':label,'start_page':page,'end_page':page,'spans':[],
            'source_ids':[],'callouts':[],'continuation_pages':[],
            'definition_source_id':_sid(span) if span else None,
            'orphan':orphan,'attribution_status':'needs_verified_attribution'}

def extract_notes(pages):
    notes=[]
    pages_out=[]
    warnings=[]
    active=None
    for page in pages:
        number=int(page['number'])
        input_spans=page['spans']
        # Front title typography and bibliography/index use small fonts for
        # non-note content. Scope is specific to the inspected edition.
        in_scope=12<=number<=73 or 80<=number<=829
        starts=[float(s['y']) for s in input_spans
                if in_scope and 50<float(s['y'])<550 and _normal_note(s)]
        if not starts:
            pages_out.append({'number':number,'body_spans':input_spans,
                              'note_source_ids':[],'note_start_y':None})
            continue
        start=min(starts)
        region=[s for s in input_spans if start-6<=float(s['y'])<555
                and 0<_size(s)<=8.5]
        region_ids={_sid(s) for s in region}
        body=[s for s in input_spans if _sid(s) not in region_ids]
        left=_left(page)
        for y,line in _lines(region):
            definitions=_definitions(line,left)
            boundaries=[0]+definitions+[len(line)]
            # Coalesce zero duplicate at start so source spans are not added
            # twice. Content before first definition continues previous note.
            boundaries=list(dict.fromkeys(boundaries))
            for a,b in zip(boundaries,boundaries[1:]):
                if a==b:continue
                chunk=line[a:b]
                if a in definitions:
                    label=_text(chunk[0])
                    active=_new_note(label,number,chunk[0])
                    notes.append(active)
                elif active is None:
                    active=_new_note(None,number,None,orphan=True)
                    notes.append(active)
                    warnings.append({'code':'orphan_note_continuation',
                                     'pdf_page':number,'y':y,
                                     'source_ids':[_sid(s) for s in chunk]})
                elif number!=active['end_page']:
                    if number not in active['continuation_pages']:
                        active['continuation_pages'].append(number)
                    if number>active['end_page']+1:
                        warnings.append({'code':'nonadjacent_note_continuation',
                                         'start_page':active['end_page'],
                                         'pdf_page':number,'label':active['label']})
                active['end_page']=number
                active['spans'].extend(chunk)
                active['source_ids'].extend(_sid(s) for s in chunk)
                active['callouts'].extend({'label':_text(s),'source_id':_sid(s),
                                           'pdf_page':number,'x':s['x'],'y':s['y']}
                                          for s in chunk if _marker(s)
                                          and _sid(s)!=active['definition_source_id']
                                          and not _math_power(s,region))
        pages_out.append({'number':number,'body_spans':body,
                          'note_source_ids':[_sid(s) for s in region],
                          'note_start_y':start})
    return {'notes':notes,'pages':pages_out,'warnings':warnings}


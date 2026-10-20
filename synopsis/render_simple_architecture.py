"""Generate matching, editable draw.io and PNG architecture diagrams."""
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
W, H = 1400, 1450
im = Image.new('RGB', (W * 2, H * 2), 'white')
d = ImageDraw.Draw(im)
font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
bold_path = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
mx = ET.Element('mxfile', host='app.diagrams.net', type='device')
diagram = ET.SubElement(mx, 'diagram', id='mega-simple', name='Architecture')
model = ET.SubElement(diagram, 'mxGraphModel', grid='1', gridSize='10', page='1', pageWidth=str(W), pageHeight=str(H))
root = ET.SubElement(model, 'root')
ET.SubElement(root, 'mxCell', id='0')
ET.SubElement(root, 'mxCell', id='1', parent='0')
nodes = {}

def label(x, y, value, size=23, bold=False):
    d.multiline_text((x*2, y*2), value, font=ImageFont.truetype(bold_path if bold else font_path, size*2), fill='#222222', anchor='mm', align='center', spacing=12)

def node(key, value, x, y, w, h, heading=False):
    nodes[key] = (x,y,w,h)
    if not heading:
        d.rectangle((x*2,y*2,(x+w)*2,(y+h)*2), fill='white', outline='#555555', width=3)
    label(x+w/2,y+h/2,value,25 if heading else 23,heading)
    style = 'text;strokeColor=none;fillColor=none;fontStyle=1;fontSize=25;' if heading else 'rounded=0;strokeColor=#555555;fillColor=#ffffff;fontSize=23;'
    cell = ET.SubElement(root,'mxCell',id=key,value=value,vertex='1',parent='1',style=style+'whiteSpace=wrap;html=0;fontColor=#222222;fontFamily=Arial;align=center;verticalAlign=middle;spacing=10;')
    ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})

def edge(a,b,points=None,value='',side=False):
    ax,ay,aw,ah=nodes[a]; bx,by,bw,bh=nodes[b]
    if points is None: points=[(ax+aw/2,ay+ah),(bx+bw/2,by)]
    d.line([(int(x*2),int(y*2)) for x,y in points],fill='#555555',width=3)
    import math
    x,y=points[-1]; px,py=points[-2]; angle=math.atan2(y-py,x-px)
    d.polygon([(x*2,y*2),((x-12*math.cos(angle-.45))*2,(y-12*math.sin(angle-.45))*2),((x-12*math.cos(angle+.45))*2,(y-12*math.sin(angle+.45))*2)],fill='#555555')
    cell=ET.SubElement(root,'mxCell',id='e-'+a+'-'+b,value=value,edge='1',parent='1',source=a,target=b,style='edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;endFill=1;strokeColor=#555555;fontSize=18;labelBackgroundColor=#ffffff;'+('exitX=1;exitY=0.5;entryX=0;entryY=0.5;' if side else 'exitX=0.5;exitY=1;entryX=0.5;entryY=0;'))
    geo=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
    if len(points)>2:
        arr=ET.SubElement(geo,'Array',attrib={'as':'points'})
        for x,y in points[1:-1]: ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))

node('title','MEGA — Video Search Architecture',100,20,1200,60,True)
node('offline','1. Video indexing',70,110,460,50,True)
node('online','2. User search',740,110,470,50,True)
node('upload','Upload video',70,200,460,70)
node('chunks','Split video into chunks\n7 seconds, with 3-second overlap',70,330,460,90)
node('extract','Extract visual, speech and text features\nOpenCLIP · Whisper · PaddleOCR',70,480,460,110)
node('store','Store embeddings and segment data\nFAISS + MongoDB',70,650,460,100)
for a,b in [('upload','chunks'),('chunks','extract'),('extract','store')]: edge(a,b)
node('query','User query',740,200,470,70)
node('expand','Expand query and select variants',740,320,470,70)
node('search','Search visual, speech and text indexes\nInclude transcript / OCR text matches',740,440,470,90)
node('fusion','Rescore and combine modality scores\nQuery intent + trained weighting model',740,580,470,90)
node('check','Check result relevance',740,720,470,70)
node('refine','Refine timestamps when applicable',740,880,470,70)
node('clean','Expand playback window\nRemove overlapping results',740,1000,470,90)
node('result','Return video, timestamps and scores',740,1140,470,70)
for a,b in [('query','expand'),('expand','search'),('search','fusion'),('fusion','check'),('check','refine'),('refine','clean'),('clean','result')]: edge(a,b,value='Relevant' if a=='check' else '')
label(1030,835,'Relevant',18)
node('none','No relevant video found',70,835,460,70)
edge('check','none',[(740,755),(620,755),(620,870),(530,870)])
# Explicit connector ports for the left-facing rejection branch.
reject=root.find("mxCell[@id='e-check-none']")
reject.set('value','Not relevant')
reject.set('style','edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;endFill=1;strokeColor=#555555;fontSize=18;labelBackgroundColor=#ffffff;exitX=0;exitY=0.5;entryX=1;entryY=0.5;')
label(630,795,'Not relevant',18)
edge('store','search',[(530,700),(600,700),(600,485),(740,485)],side=True)
node('note','Simplified implementation view\n\nIndexing runs once per upload. Searches use the stored data.\nRefinement applies to eligible visual matches.\nCaching, queues and authentication are omitted for clarity.',70,1260,1140,150,True)
# Smaller footnote typography in both outputs.
notes=root.find("mxCell[@id='note']")
notes.set('style','text;strokeColor=none;fillColor=none;whiteSpace=wrap;html=0;fontSize=18;fontColor=#555555;fontFamily=Arial;align=center;verticalAlign=middle;')
d.rectangle((70*2,1260*2,1210*2,1410*2),fill='white')
label(640,1335,'Indexing runs once per upload. Searches use the stored data.\nRefinement applies to eligible visual matches.\nCaching, queues and authentication are omitted for clarity.',18)
notes.set('value','Indexing runs once per upload. Searches use the stored data.\nRefinement applies to eligible visual matches.\nCaching, queues and authentication are omitted for clarity.')
ET.indent(mx)
path=OUT/'architecture_diagram_simple.drawio'
ET.ElementTree(mx).write(path,encoding='utf-8',xml_declaration=True)
im.save(OUT/'architecture_diagram_simple.png',dpi=(200,200))
cells=ET.parse(path).findall('.//mxCell'); ids={c.get('id') for c in cells}
assert len(ids)==len(cells)
for c in cells:
    if c.get('edge'): assert c.get('source') in ids and c.get('target') in ids
print('Saved simplified PNG and draw.io; XML and connectors validated.')

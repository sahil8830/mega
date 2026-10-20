"""Render the implemented MEGA architecture as a publication-sized PNG."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
im = Image.new('RGB', (2400, 2560), '#ffffff')
d = ImageDraw.Draw(im)
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def text(x, y, value, size=30, color='#193044', bold=False, anchor='mm'):
    d.multiline_text((x,y), value, font=ImageFont.truetype(BOLD if bold else FONT,size),
                     fill=color, anchor=anchor, align='center', spacing=10)
def box(x,y,w,h,title,sub='',color='#155d70'):
    d.rounded_rectangle((x,y,x+w,y+h),radius=22,fill=color)
    text(x+w/2,y+(h/2 if not sub else 36),title,31,'white',True)
    if sub: text(x+w/2,y+h/2+22,sub,25,'#ffffff')
def arrow(points, color='#657987', width=4):
    d.line(points,fill=color,width=width,joint='curve')
    x,y=points[-1]; px,py=points[-2]; a=math.atan2(y-py,x-px)
    d.polygon([(x,y),(x-17*math.cos(a-.45),y-17*math.sin(a-.45)),
               (x-17*math.cos(a+.45),y-17*math.sin(a+.45))],fill=color)
def down(x,a,b): arrow([(x,a),(x,b)])

text(1200,65,'MEGA | Multimodal Video Search',52,bold=True)
text(1200,122,'Implemented architecture • Visual + speech + on-screen text',29,color='#607589')
box(90,175,2220,110,'React interface  →  Express API  →  FastAPI ML service',
    'Authenticated uploads and searches • MongoDB metadata and search history', '#233d53')

d.rounded_rectangle((65,335,1050,2270),30,fill='#eef6f8',outline='#c7dce2',width=3)
d.rounded_rectangle((1110,335,2335,2270),30,fill='#fbf5ec',outline='#e7d7bd',width=3)
text(555,385,'OFFLINE • INDEX EACH VIDEO',35,'#155d70',True)
text(1720,385,'ONLINE • SEARCH EACH QUERY',35,'#805020',True)

box(160,440,795,110,'Video upload + indexing queue','BullMQ / Redis • background processing')
down(555,550,595)
box(160,595,795,120,'Temporal segmentation','7-second chunks • 3-second overlap\n4 representative frames per chunk')
down(555,715,760)
box(160,760,795,120,'Whisper speech transcription','Transcribe the full video once\nMap timestamped speech to chunks')
arrow([(555,880),(555,905),(330,905),(330,930)])
arrow([(555,905),(785,905),(785,930)])
box(120,930,420,150,'Visual features','OpenCLIP frame embeddings\nMean pooling per chunk')
box(575,930,420,150,'Text evidence','Whisper transcript\nPaddleOCR on sampled frames')
arrow([(785,1080),(785,1130)])
box(575,1130,420,120,'Text embeddings','CLIP encodes speech\nand OCR text')
arrow([(330,1080),(330,1300),(555,1300),(555,1350)])
arrow([(785,1250),(785,1300),(555,1300)])
box(160,1350,795,145,'Persistent multimodal storage','Per-user FAISS: visual / speech / OCR\nMongoDB: segments, timestamps, text, metadata','#233d53')

text(555,1610,'INDEXING OPTIMIZATIONS',29,'#155d70',True)
text(555,1730,'Sequential frame decoding\nBatched CLIP inference and database writes\nExact OCR reuse within an indexing run',28)
text(555,1950,'Stored evidence feeds retrieval.\nVideo ownership and deletion scope\nare checked before final ranking.',29)

X=1190; W=1065; C=X+W/2
nodes=[
 (440,110,'User query + cache lookup','Redis caches search responses and query expansions'),
 (590,130,'Query preparation','Optional Hindi translation • FLAN-T5 variants\nK-Means representatives • original query retained'),
 (760,130,'Candidate retrieval','Parallel visual / speech / OCR FAISS search\nAdd literal transcript and OCR matches'),
 (930,110,'Rescore against the original query','Score candidates across all three modalities'),
 (1080,130,'Hybrid modality-weighted fusion','Query intent + trained MLP • fixed-weight fallback\nBlend literal text evidence when available'),
]
for y,h,t,s in nodes: box(X,y,W,h,t,s,'#8b5928')
for i in range(len(nodes)-1): down(C,nodes[i][0]+nodes[i][1],nodes[i+1][0])
arrow([(955,1420),(1080,1420),(1080,825),(1190,825)],'#155d70')
text(1048,1480,'Stored\nevidence',22,'#155d70')
down(C,1210,1250)
d.polygon([(C,1250),(C+330,1340),(C,1430),(C-330,1340)], fill='#8b2945')
text(C,1340,'Answerable?',33,'white',True)
arrow([(C-330,1340),(1220,1340),(1220,1475)])
text(1270,1390,'No',24,'#8b2945',True)
box(1150,1475,350,105,'No relevant result','Empty result list','#8b2945')
arrow([(C,1430),(C,1630)])
text(C+55,1500,'Yes',25,'#805020',True)
box(X,1630,W,150,'Conditional temporal refinement','Top results with sufficient confidence; broad visual matches only\nGaussian smoothing + sliding window on stored timeline\nShort chunks and speech/OCR matches keep their timestamps','#155d70')
down(C,1780,1825)
box(X,1825,W,120,'Result window expansion','At least 15 seconds of context when duration allows\nClamp to video boundaries','#155d70')
down(C,1945,1990)
box(X,1990,W,105,'Remove overlapping results','Temporal NMS within each video • return top-K','#155d70')
down(C,2095,2130)
box(X,2130,W,105,'Video + timestamps + evidence scores','Per-modality similarities, fusion weights and confidence','#233d53')

d.rounded_rectangle((90,2320,2310,2530),20,fill='#f1f4f7')
text(1200,2370,'IMPLEMENTATION NOTES',28,bold=True)
text(1200,2445,'Answerability runs after fusion. No standalone QSVideo evidence-selection module.\nDirect search remains available when expansion fails or is omitted.\nA valid full-response cache hit returns early; this diagram shows the uncached search path.',26)
im.save(ROOT/'architecture_diagram_current.png',dpi=(200,200))
print(ROOT/'architecture_diagram_current.png')

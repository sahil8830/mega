import argparse,os,time,json
from importlib.resources import files
from pathlib import Path
benchmark_dir=Path(__file__).resolve().parent
ml_service_dir=benchmark_dir.parent/'ml-service'
parser=argparse.ArgumentParser(description='Run the isolated OCR benchmark from any working directory.')
parser.add_argument('mode',choices=['paddle','hybrid','hybridcoreml','onnx','coreml'])
parser.add_argument('--frames-dir',type=Path,default=ml_service_dir/'frames/1791788736326-758448146')
parser.add_argument('--onnx-models-dir',type=Path,default=Path('/private/tmp/mega-onnx-models'))
parser.add_argument('--paddle-models-dir',type=Path,default=Path.home()/'.paddlex/official_models')
parser.add_argument('--output',type=Path)
parser.add_argument('--extended',action='store_true',default=bool(os.environ.get('EXTENDED')))
args=parser.parse_args()
mode=args.mode
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
os.environ['FLAGS_use_mkldnn']='0'
os.environ['FLAGS_pir_apply_shape_optimization_pass']='0'
from paddleocr import PaddleOCR
base=args.onnx_models_dir if mode!='paddle' else args.paddle_models_dir
models={'doc_orientation_classify':'PP-LCNet_x1_0_doc_ori','doc_unwarping':'UVDoc','textline_orientation':'PP-LCNet_x1_0_textline_ori','text_detection':'PP-OCRv6_medium_det','text_recognition':'PP-OCRv6_medium_rec'}
kwargs={k+'_model_dir':str(base/v) for k,v in models.items()}
kwargs.update({k+'_model_name':v for k,v in models.items()})
if mode not in ('paddle','hybrid','hybridcoreml'):
 import onnxruntime as ort
 print('PROVIDERS',ort.get_available_providers(),flush=True)
 config={'providers':['CPUExecutionProvider'],'intra_op_num_threads':4}
 if mode=='coreml':
  config.update(providers=['CoreMLExecutionProvider','CPUExecutionProvider'],provider_options=[{'ModelFormat':'MLProgram','MLComputeUnits':'ALL','RequireStaticInputShapes':'0'},{}])
 kwargs.update(engine='onnxruntime',engine_config=config)
if mode in ('hybrid','hybridcoreml'):
 import yaml
 cfg=yaml.safe_load(files('paddlex').joinpath('configs','pipelines','OCR.yaml').read_text())
 kwargs={k+'_model_dir':str(args.paddle_models_dir/v) for k,v in models.items()}
 kwargs['text_detection_model_dir']=str(args.onnx_models_dir/models['text_detection'])
 ec={'providers':['CPUExecutionProvider'],'intra_op_num_threads':4}
 if mode=='hybridcoreml':
  ec.update(providers=['CoreMLExecutionProvider','CPUExecutionProvider'],provider_options=[{'ModelFormat':'MLProgram','MLComputeUnits':'ALL','RequireStaticInputShapes':'0'},{}])
 cfg['SubModules']['TextDetection'].update(engine='onnxruntime',engine_config={'onnxruntime':ec})
 kwargs['paddlex_config']=cfg
t=time.perf_counter()
ocr=PaddleOCR(device='cpu',use_textline_orientation=True,lang='en',**kwargs)
print('INIT',time.perf_counter()-t,flush=True)
root=args.frames_dir
frames=['chunk0048_frame0.jpg','chunk0059_frame2.jpg','chunk0010_frame3.jpg']
if args.extended:
 frames=[f'chunk{i:04d}_frame0.jpg' for i in [0,8,16,24,32,40,48,56,64,70]]
rows=[]
for repeat in range(1 if args.extended else 2):
 for f in frames:
  t=time.perf_counter(); result=list(ocr.predict(str(root/f))); elapsed=time.perf_counter()-t
  texts=[text for r in result for text,score in zip(r.get('rec_texts',[]),r.get('rec_scores',[])) if score>0.5]
  row={'repeat':repeat,'frame':f,'seconds':elapsed,'texts':texts}
  rows.append(row);print(json.dumps(row),flush=True)
output=args.output or benchmark_dir/(mode+'-benchmark.json')
output.write_text(json.dumps(rows,indent=2))
print('Results saved to',output,flush=True)

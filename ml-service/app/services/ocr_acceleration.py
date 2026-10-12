"""Optional ONNX text detector; retain Paddle preprocessing and recognition."""
from copy import deepcopy
from pathlib import Path


class DetectorWithFallback:
    def __init__(self, accelerated, original):
        self.accelerated = accelerated
        self.original = original
        self.failed = False

    def __getattr__(self, name):
        return getattr(self.original, name)

    def __call__(self, *args, **kwargs):
        if not self.failed:
            try:
                # Materialize before yielding so a partial failure cannot duplicate results.
                results = list(self.accelerated(*args, **kwargs))
            except Exception as exc:
                self.failed = True
                print(f"[OCR] ONNX detector failed; retaining Paddle detector: {exc}")
            else:
                yield from results
                return
        yield from self.original(*args, **kwargs)


def accelerate_detector(ocr, model_dir, force_cpu=False):
    """Call after normal PaddleOCR initialization. Failure retains original OCR."""
    if not model_dir:
        return "paddle"
    try:
        import onnxruntime as ort
        if not (Path(model_dir) / 'inference.onnx').is_file():
            raise FileNotFoundError(f"No inference.onnx in {model_dir}")
        pipeline = ocr.paddlex_pipeline._pipeline
        config = deepcopy(ocr._merged_paddlex_config['SubModules']['TextDetection'])
        config.update(model_dir=str(model_dir), engine='onnxruntime')
        options = {'providers': ['CPUExecutionProvider'], 'intra_op_num_threads': 4}
        coreml = not force_cpu and 'CoreMLExecutionProvider' in ort.get_available_providers()
        if coreml:
            options.update(providers=['CoreMLExecutionProvider', 'CPUExecutionProvider'],
                           provider_options=[{'ModelFormat': 'MLProgram',
                                              'MLComputeUnits': 'ALL',
                                              'RequireStaticInputShapes': '0'}, {}])
        config['engine_config'] = {'onnxruntime': options}
        try:
            accelerated = pipeline.create_model(config)
        except Exception as exc:
            if not coreml:
                raise
            print(f"[OCR] Core ML detector initialization failed; trying ONNX CPU: {exc}")
            config['engine_config']['onnxruntime'] = {
                'providers': ['CPUExecutionProvider'], 'intra_op_num_threads': 4}
            accelerated = pipeline.create_model(config)
            coreml = False
        pipeline.text_det_model = DetectorWithFallback(accelerated, pipeline.text_det_model)
        backend = 'Core ML + CPU' if coreml else 'ONNX CPU'
        print(f"[OCR] Detector: {backend}; original models and preprocessing retained.")
        return backend
    except Exception as exc:
        print(f"[OCR] Detector acceleration unavailable; retaining Paddle: {exc}")
        return 'paddle'

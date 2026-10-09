# Multiple-screen detection

`face_detection_yunet_2023mar.onnx` is the OpenCV Zoo YuNet model.

- Source: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- Download: https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
- SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- License: MIT; see `YuNet-LICENSE.txt`.

API and worker images bundle this model. Automatic collage inspects the original
clip at three samples per second at up to 960px wide, caches the results by sample
time and detector version, and uses them for both preview and rendering. Existing
low-resolution BlazeFace analysis remains available for single-screen framing.

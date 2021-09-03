# FastMOT
[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FGeekAlexis%2FFastMOT&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![DOI](https://zenodo.org/badge/237143671.svg)](https://zenodo.org/badge/latestdoi/237143671)

<img src="assets/dense_demo.gif" width="400"/> <img src="assets/aerial_demo.gif" width="400"/>

## News
  - (2021.8.30) Add demos
  - (2021.8.17) Support multi-class tracking
  - (2021.7.4) Support yolov4-p5 and yolov4-p6
  - (2021.2.13) Support Scaled-YOLOv4 (i.e. yolov4-csp/yolov4x-mish/yolov4-csp-swish)
  - (2021.1.3) Add DIoU-NMS for postprocessing
  - (2020.11.28) Docker container provided for x86 Ubuntu

## Description
FastMOT is a custom multiple object tracker that implements:
  - YOLO detector
  - SSD detector
  - Deep SORT + OSNet ReID
  - KLT tracker
  - Camera motion compensation

Two-stage trackers like Deep SORT run detection and feature extraction sequentially, which often becomes a bottleneck. FastMOT significantly speeds up the entire system to run in **real-time** even on Jetson. Motion compensation improves tracking for scenes with moving camera, where Deep SORT and FairMOT fail.

To achieve faster processing, FastMOT only runs the detector and feature extractor every N frames, while KLT fills in the gaps efficiently. FastMOT also re-identifies objects that moved out of frame to keep the same IDs.

YOLOv4 was trained on CrowdHuman (82% mAP@0.5) and SSD's are pretrained COCO models from TensorFlow. Both detection and feature extraction use the **TensorRT** backend and perform asynchronous inference. In addition, most algorithms, including KLT, Kalman filter, and data association, are optimized using Numba.

## Performance
### Results on MOT20 train set
| Detector Skip | MOTA | IDF1 | HOTA | MOTP | MT | ML |
|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|
| N = 1 | 66.8% | 56.4% | 45.0% | 79.3% | 912 | 274 |
| N = 5 | 65.1% | 57.1% | 44.3% | 77.9% | 860 | 317 |

### FPS on MOT17 sequences
| Sequence | Density | FPS |
|:-------|:-------:|:-------:|
| MOT17-13 | 5 - 30  | 42 |
| MOT17-04 | 30 - 50  | 26 |
| MOT17-03 | 50 - 80  | 18 |

Performance is evaluated with YOLOv4 using [TrackEval](https://github.com/JonathonLuiten/TrackEval). Note that neither YOLOv4 nor OSNet was trained or finetuned on the MOT20 dataset, so train set results should generalize well. FPS results are obtained on Jetson Xavier NX (20W 2core mode).

FastMOT has MOTA scores close to **state-of-the-art** trackers from the MOT Challenge. Increasing N shows small impact on MOTA. Tracking speed can reach up to **42 FPS** depending on the number of objects. Lighter models (e.g. YOLOv4-tiny) are recommended for a more constrained device like Jetson Nano. FPS is expected to be in the range of **50 - 150** on desktop CPU/GPU.

## Requirements
- CUDA >= 10
- cuDNN >= 7
- TensorRT >= 7
- OpenCV >= 3.3
- Numpy >= 1.17
- Scipy >= 1.5
- Numba == 0.48
- CuPy == 9.2
- TensorFlow < 2.0 (for SSD support)

### Install for x86 Ubuntu
Make sure to have [nvidia-docker](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker) installed. The image requires NVIDIA Driver version >= 450 for Ubuntu 18.04 and >= 465.19.01 for Ubuntu 20.04. Build and run the docker image:
  ```bash
  # Add --build-arg TRT_IMAGE_VERSION=21.05 for Ubuntu 20.04
  # Add --build-arg CUPY_NVCC_GENERATE_CODE=... to speed up build for your GPU, e.g. "arch=compute_75,code=sm_75"
  docker build -t fastmot:latest .
  
  # Run xhost local:root first if you cannot visualize inside the container
  docker run --gpus all --rm -it -v $(pwd):/usr/src/app/FastMOT -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=unix$DISPLAY -e TZ=$(cat /etc/timezone) fastmot:latest
  ```
### Install for Jetson Nano/TX2/Xavier NX/Xavier
Make sure to have [JetPack >= 4.4](https://developer.nvidia.com/embedded/jetpack) installed and run the script:
  ```bash
  ./scripts/install_jetson.sh
  ```
### Download models
Pretrained OSNet, SSD, and my YOLOv4 ONNX model are included.
  ```bash
  ./scripts/download_models.sh
  ```
### Build YOLOv4 TensorRT plugin
  ```bash
  cd fastmot/plugins
  make
  ```
### Download VOC dataset for INT8 calibration
Only required for SSD (not supported on Ubuntu 20.04)
  ```bash
  ./scripts/download_data.sh
  ```

## Usage
```bash
  python3 app.py --input-uri ... --mot
```
- Image sequence: `--input-uri %06d.jpg`
- Video file: `--input-uri file.mp4`
- USB webcam: `--input-uri /dev/video0`
- MIPI CSI camera: `--input-uri csi://0`
- RTSP stream: `--input-uri rtsp://<user>:<password>@<ip>:<port>/<path>`
- HTTP stream: `--input-uri http://<user>:<password>@<ip>:<port>/<path>`

Use `--show` to visualize, `--output-uri` to save output, and `--txt` for MOT compliant results.

Show help message for all options:
```bash
  python3 app.py -h
```
Note that the first run will be slow due to Numba compilation. To use the FFMPEG backend on x86, set `WITH_GSTREAMER = False` [here](https://github.com/GeekAlexis/FastMOT/blob/3a4cad87743c226cf603a70b3f15961b9baf6873/fastmot/videoio.py#L11)
<details>
<summary> More options can be configured in cfg/mot.json </summary>

  - Set `resolution` and `frame_rate` that corresponds to the source data or camera configuration (optional). They are required for image sequence, camera sources, and saving txt results. List all configurations for a USB/CSI camera:
    ```bash
    v4l2-ctl -d /dev/video0 --list-formats-ext
    ```
  - To swap network, modify `model` under a detector. For example, you can choose from `SSDInceptionV2`, `SSDMobileNetV1`, or `SSDMobileNetV2` for SSD.
  - If more accuracy is desired and FPS is not an issue, lower `detector_frame_skip`. Similarly, raise `detector_frame_skip` to speed up tracking at the cost of accuracy. You may also want to change `max_age` such that `max_age` × `detector_frame_skip` ≈ 30
  - Modify `visualizer_cfg` to toggle drawing options.
  - All parameters are documented in the API.

</details>

 ## Track custom classes
FastMOT can be easily extended to a custom class (e.g. vehicle). You need to train both YOLO and a ReID network on your object class. Check [Darknet](https://github.com/AlexeyAB/darknet) for training YOLO and [fast-reid](https://github.com/JDAI-CV/fast-reid) for training ReID. After training, convert weights to ONNX format. The TensorRT plugin adapted from [tensorrt_demos](https://github.com/jkjung-avt/tensorrt_demos/) is only compatible with Darknet.

FastMOT also supports multi-class tracking. It is recommended to train a ReID network for each class to extract features separately.
### Convert YOLO to ONNX
1. Install ONNX version 1.4.1 (not the latest version)
    ```bash
    pip3 install onnx==1.4.1
    ```
2. Convert using your custom cfg and weights
    ```bash
    ./scripts/yolo2onnx.py --config yolov4.cfg --weights yolov4.weights
    ```
### Add custom YOLOv3/v4
1. Subclass `fastmot.models.YOLO` like here: https://github.com/GeekAlexis/FastMOT/blob/32c217a7d289f15a3bb0c1820982df947c82a650/fastmot/models/yolo.py#L100-L109
    ```
    ENGINE_PATH : Path
        Path to TensorRT engine.
        If not found, TensorRT engine will be converted from the ONNX model
        at runtime and cached for later use.
    MODEL_PATH : Path
        Path to ONNX model.
    NUM_CLASSES : int
        Total number of trained classes.
    LETTERBOX : bool
        Keep aspect ratio when resizing.
    NEW_COORDS : bool
        new_coords Darknet parameter for each yolo layer.
    INPUT_SHAPE : tuple
        Input size in the format `(channel, height, width)`.
    LAYER_FACTORS : List[int]
        Scale factors with respect to the input size for each yolo layer.
    SCALES : List[float]
        scale_x_y Darknet parameter for each yolo layer.
    ANCHORS : List[List[int]]
        Anchors grouped by each yolo layer.
    ```
    Note anchors may not follow the same order in the Darknet cfg file. You need to mask out the anchors for each yolo layer using the indices in `mask` in Darknet cfg.
    Unlike YOLOv4, the anchors are usually in reverse for YOLOv3 and YOLOv3/v4-tiny
2. Set class labels to your object classes with `fastmot.models.set_label_map`
3. Modify cfg/mot.json: set `model` in `yolo_detector_cfg` to the added Python class name and set `class_ids` of interest. You may want to play with `conf_thresh` based on model performance.
### Add custom ReID
1. Subclass `fastmot.models.ReID` like here: https://github.com/GeekAlexis/FastMOT/blob/32c217a7d289f15a3bb0c1820982df947c82a650/fastmot/models/reid.py#L50-L55
    ```
    ENGINE_PATH : Path
        Path to TensorRT engine.
        If not found, TensorRT engine will be converted from the ONNX model
        at runtime and cached for later use.
    MODEL_PATH : Path
        Path to ONNX model.
    INPUT_SHAPE : tuple
        Input size in the format `(channel, height, width)`.
    OUTPUT_LAYOUT : int
        Feature dimension output by the model.
    METRIC : {'euclidean', 'cosine'}
        Distance metric used to match features.
    ```
    
2. Modify cfg/mot.json: set `model` in `feature_extractor_cfgs` to the added Python class name. For more than one class, add more feature extractor configurations to the list `feature_extractor_cfgs`. You may want to play with `max_assoc_cost` and `max_reid_cost` based on model performance

 ## Demos

### Person

1. Download any video from [MOTChallenge website](https://motchallenge.net/) for example,
    ```bash
    wget https://motchallenge.net/sequenceVideos/MOT16-07-raw.webm -P ./videos/
    ```
2. Inside docker run the following command
    ```bash
    python3 app.py -i ./videos/MOT16-07-raw.webm -c ./cfg/mot.json -s -v -m
    ```


### Cars

Here we will demonstrate the steps outlined above for extending fastmot to track custom classes (e.g. car in this case). We will use [YOLOv4](https://github.com/AlexeyAB/darknet#pre-trained-models) model for detecting cars and [VeRIWild](https://github.com/JDAI-CV/fast-reid/blob/master/MODEL_ZOO.md#veri-wild-baseline) model as feature extractor. Download any video with cars (for ex: [cars](https://github.com/theAIGuysCode/yolov4-deepsort/blob/master/data/video/cars.mp4)).

1. Convert YOLOv4 model to onnx using `scripts/yolo2onnx.py`. After installing the recommended version of `onnx==1.4.1`, download the [weights](https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights) and [cfg](https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg) corresponding to YOLOv4 model. 
    [Optional step] Test YOLOv4 weights and cfg on the input video.

2. Convert YOLOv4 weights and cfg to onnx model.
    ```bash
    ./scripts/yolo2onnx.py --config yolov4.cfg --weights yolov4.weights
    ```
    
3. Replace the `_label_map` inside `fastmot/models/label.py` with [YOLOv4 class mapping](https://github.com/AlexeyAB/darknet/blob/master/data/coco.names).

    <details>
        <summary>YOLOv4 class mapping</summary> <br/>
        <pre>
    _label_map = (
        'person',
        'bicycle',
        'car',
        'motorbike',
        'aeroplane',
        'bus',
        'train',
        'truck',
        'boat',
        'traffic light',
        'fire hydrant',
        'stop sign',
        'parking meter',
        'bench',
        'bird',
        'cat',
        'dog',
        'horse',
        'sheep',
        'cow',
        'elephant',
        'bear',
        'zebra',
        'giraffe',
        'backpack',
        'umbrella',
        'handbag',
        'tie',
        'suitcase',
        'frisbee',
        'skis',
        'snowboard',
        'sports ball',
        'kite',
        'baseball bat',
        'baseball glove',
        'skateboard',
        'surfboard',
        'tennis racket',
        'bottle',
        'wine glass',
        'cup',
        'fork',
        'knife',
        'spoon',
        'bowl',
        'banana',
        'apple',
        'sandwich',
        'orange',
        'broccoli',
        'carrot',
        'hot dog',
        'pizza',
        'donut',
        'cake',
        'chair',
        'sofa',
        'pottedplant',
        'bed',
        'diningtable',
        'toilet',
        'tvmonitor',
        'laptop',
        'mouse',
        'remote',
        'keyboard',
        'cell phone',
        'microwave',
        'oven',
        'toaster',
        'sink',
        'refrigerator',
        'book',
        'clock',
        'vase',
        'scissors',
        'teddy bear',
        'hair drier',
        'toothbrush',
    )
    </pre>
    </details>
    
4. Add following code to `fastmot/models/yolo.py`
    
    ```python
    class YOLOv4Original(YOLO):
        ENGINE_PATH = Path(__file__).parent / 'yolov4.trt'
        MODEL_PATH = Path(__file__).parent /  'yolov4.onnx'
        NUM_CLASSES = 80
        INPUT_SHAPE = (3, 608, 608)
        LAYER_FACTORS = [8, 16, 32]
        SCALES = [1.2, 1.1, 1.05]
        ANCHORS = [[12,16, 19,36, 40,28],
                   [36,75, 76,55, 72,146],
                   [142,110, 192,243, 459,401]]
    ```
    
    
    [Optional step] Cross verify the values from [cfg](https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg) with the above class.
    
5. Add the following classes in `fastmot/models/reid.py`. These ReID models will be used as feature extractor.

    ```python
    class VERIWild(ReID):
    	"""Model trained on VERIWild dataset using fastreid library"""
    	ENGINE_PATH = Path(__file__).parent / 'veriwild_r50ibn.trt'
    	MODEL_PATH = Path(__file__).parent / 'veriwild_r50ibn.onnx'
    	INPUT_SHAPE = (3, 256, 256)
    	OUTPUT_LAYOUT = 2048
    	METRIC = 'cosine'
    
    class VehicleID(ReID)
    	"""Model trained on VehicleID dataset using fastreid library"""
    	ENGINE_PATH = Path(__file__).parent / 'vehicleid_r50ibn.trt'
    	MODEL_PATH = Path(__file__).parent / 'vehicleid_r50ibn.onnx'
    	INPUT_SHAPE = (3, 256, 256)
    	OUTPUT_LAYOUT = 2048
    	METRIC = 'cosine'
    ```
    Download the [pytorch models](https://github.com/JDAI-CV/fast-reid/blob/ced654431be28492066f4746d23c1ff89d26acbd/MODEL_ZOO.md) from fastreid library and [convert to onnx](https://github.com/JDAI-CV/fast-reid/tree/ced654431be28492066f4746d23c1ff89d26acbd/tools/deploy#onnx-convert) or directly downloading the converted models: [veriwild_r50ibn.onnx](https://drive.google.com/uc?id=1Nyxj_muAKwQOrdk6ftdcq0e0di51nTi-) and [vehicleid_r50ibn.onnx](https://drive.google.com/uc?id=1nk5GqReWBZ4xWoUgNdjqp8fusD8wT9ch). Move the onnx model to `fastmot/models` directory.

    

    [Optional step] [Verify](https://github.com/JDAI-CV/fast-reid/tree/ced654431be28492066f4746d23c1ff89d26acbd/tools/deploy#onnx-convert) the onnx and pytorch model provide same output and visualize the onnx model in [netron](netron.app/).

    

6. After visualizing the onnx model in [netron.app](netron.app/), the model already performs normalization step. Replace the lines starting with `out[]` in `fastmot/feature_extractor.py` with the following
    ```python
    # Normalize according to fastreid model
    out[0, ...] = chw[0, ...]
    out[1, ...] = chw[1, ...]
    out[2, ...] = chw[2, ...]
    ```

7. Inside docker run the following command

    VERIWild reid model

    ```bash
    python3 app.py -i ./videos/cars.mp4 -c ./cfg/veriwild.json -s -v -m
    ```
    VehicleID reid model

    - Replace `VERIWild` in `cfg/veriwild.json` to `VehicleID` to run VehicleID as ReID feature extractor.

### Vehicles

We can easily extend the example of cars to track vehicles (i.e. cars, motorbike, bicycle, trucks and bus combined). We will use all steps outlined in [Cars](#cars) demo with some modifications. Download any video containing vehicles (for ex: [vehicles](https://drive.google.com/file/d/1A7LCl8B2eDA63LJdve_7MAiWO7jcr4rj/view?usp=sharing)).

1. Tying all different classes of interest (for ex: cars and trucks) from YOLOv4 to one class. The mapping of classes in YOLOv4 for cars:2 and trucks:7. Add following lines which combine `cars` and `trucks` in one `cars` classes  after line no: 363 in `fastmot.detector.py`.
    ```python
        if label == 7: # trucks
            label = 2  # cars
    ```
    
2. Modify `cfg/veriwild.json`. Detect and track cars & trucks by modifying `class_ids` and `feature_extractor_cfgs`.
    ```bash
        "class_ids": [ 2, 7], 
            "feature_extractor_cfgs": [
                {
                    "model": "VERIWild",
                    "batch_size": 16
                },
                {
                    "model": "VERIWild",
                    "batch_size": 16
                }
            ],
    ```

3. Inside docker run the following command

    VERIWild reid model

    ```bash
    python3 app.py -i ./videos/nv.mp4 -c ./cfg/veriwild.json -s -v -m
    ```
    
    VehicleID reid model
    
    - Replace `VERIWild` in `cfg/veriwild.json` to `VehicleID` to run VehicleID as ReID feature extractor.
    
    You may want to play with different parameters based on model performance.


 ## Citation
 If you find this repo useful in your project or research, please star and consider citing it:
 ```bibtex
@software{yukai_yang_2020_4294717,
  author       = {Yukai Yang},
  title        = {{FastMOT: High-Performance Multiple Object Tracking Based on Deep SORT and KLT}},
  month        = nov,
  year         = 2020,
  publisher    = {Zenodo},
  version      = {v1.0.0},
  doi          = {10.5281/zenodo.4294717},
  url          = {https://doi.org/10.5281/zenodo.4294717}
}
 ```


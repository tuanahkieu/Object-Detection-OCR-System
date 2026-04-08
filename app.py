import os
import io
import base64
import json
import time
import cv2          # Thêm thư viện vẽ OpenCV
import numpy as np  # Thêm thư viện xử lý ma trận Numpy
from flask import Flask, request, jsonify, send_from_directory
from PIL import Image
import torch
from ultralytics import RTDETR

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Config ──────────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "best.pt")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Load model once at startup ───────────────────────────────────────────────
print(f"[INFO] Loading RT-DETR model from: {MODEL_PATH}")
model = RTDETR(MODEL_PATH)
print(f"[INFO] Model loaded successfully. Classes: {model.names}")


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        # Read image
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # Chuyển ảnh PIL (RGB) sang Numpy Array (BGR) để OpenCV dễ dàng vẽ màu
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Get confidence threshold from request (default 0.25)
        conf = float(request.form.get("conf", 0.25))
        iou = float(request.form.get("iou", 0.45))

        # Run inference
        t0 = time.time()
        results = model.predict(image, conf=conf, iou=iou, verbose=False)
        inference_time = round((time.time() - t0) * 1000, 1)  # ms

        result = results[0]
        detections = []
        boxes = result.boxes

        # ── Xử lý JSON và Vẽ khung tùy chỉnh cùng lúc ────────────────────────
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf_val = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]

                # --- 1. Tùy chỉnh màu sắc (Hệ màu BGR của OpenCV) ---
                if cls_name == 'Table':
                    color = (0, 0, 255)    # Màu Đỏ cho Table
                    thickness = 3          # Viền dày hơn cho Table
                elif cls_name == 'Note':
                    color = (0, 255, 0)    # Màu Xanh lá cho Note
                    thickness = 2
                elif cls_name == 'PartDrawing':
                    color = (255, 0, 0)    # Màu Xanh dương cho PartDrawing
                    thickness = 2
                else:
                    color = (0, 255, 255)  # Màu Vàng mặc định
                    thickness = 2

                # --- 2. Vẽ khung và nhãn lên ảnh cv_img ---
                cv2.rectangle(cv_img, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
                label = f"{cls_name} {conf_val:.2f}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(cv_img, (int(x1), int(y1) - 20), (int(x1) + tw, int(y1)), color, -1)
                cv2.putText(cv_img, label, (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # --- 3. Đóng gói data JSON ---
                detections.append({
                    "id": len(detections) + 1,
                    "class": cls_name,
                    "confidence": round(conf_val, 2),
                    "bbox": {
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2),
                    },
                    "ocr_content": ""
                })

        # ── Chuyển ảnh đã vẽ (BGR) ngược lại thành Base64 (RGB) ───────────
        annotated_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_annotated = Image.fromarray(annotated_rgb)

        buf = io.BytesIO()
        pil_annotated.save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Count per class
        class_counts = {}
        for d in detections:
            name = d["class"]
            class_counts[name] = class_counts.get(name, 0) + 1

        response = {
            "image": file.filename,
            "image_b64": img_b64,
            "inference_time_ms": inference_time,
            "total_detections": len(detections),
            "class_counts": class_counts,
            "objects": detections,
        }
        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/model-info")
def model_info():
    return jsonify({
        "model": "RT-DETR",
        "classes": model.names,
        "num_classes": len(model.names),
        "model_path": MODEL_PATH,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
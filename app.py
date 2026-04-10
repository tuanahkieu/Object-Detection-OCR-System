import os
import io
import base64
import json
import time
import cv2          
import numpy as np  
from flask import Flask, request, jsonify, send_from_directory
from PIL import Image
from ultralytics import RTDETR

# --- THÊM THƯ VIỆN EASYOCR (Chạy mượt 100% trên Mac) ---
import easyocr

app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Config ──────────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "best.pt")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
CROP_FOLDER = os.path.join(UPLOAD_FOLDER, "crops")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CROP_FOLDER, exist_ok=True)

# ── Load RT-DETR model ──────────────────────────────────────────────────────
print(f"[INFO] Loading RT-DETR model from: {MODEL_PATH}")
model = RTDETR(MODEL_PATH)
print(f"[INFO] Model loaded successfully. Classes: {model.names}")

# ── Load EasyOCR model ──────────────────────────────────────────────────────
print("[INFO] Loading EasyOCR model...")
# Tải bộ não đọc cả tiếng Anh ('en') lẫn tiếng Việt ('vi'). Tự động chạy mượt trên Mac.
reader = easyocr.Reader(['vi', 'en'])
print("[INFO] EasyOCR loaded successfully.")

def perform_easyocr_on_crop(cropped_img, is_table=False):
    """Đọc chữ bằng EasyOCR với bộ lọc chuẩn mực cho Bản vẽ kỹ thuật."""
    if cropped_img is None or cropped_img.size == 0:
        return ""

    try:
        # --- BƯỚC 1: TIỀN XỬ LÝ ẢNH CHUYÊN SÂU ---
        
        # 1. Chuyển sang ảnh xám
        gray_img = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        
        # 2. Phóng to ảnh lên 2.5 lần bằng thuật toán CUBIC (Giúp nét chữ sắc sảo hơn, không bị vỡ)
        height, width = gray_img.shape[:2]
        resized_img = cv2.resize(gray_img, (int(width * 2.5), int(height * 2.5)), interpolation=cv2.INTER_CUBIC)

        # 3. Lọc nhiễu (Denoise): "Ủi" phẳng các vết rỗ, nhiễu hạt trên nền giấy
        denoised_img = cv2.fastNlMeansDenoising(resized_img, None, h=10, templateWindowSize=7, searchWindowSize=21)

        # 4. Nhị phân hóa Otsu: Tự động tìm điểm cắt sáng/tối để biến nền thành Trắng tinh (255) và chữ thành Đen tuyền (0)
        _, thresh_img = cv2.threshold(denoised_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # --- BƯỚC 2: GỌI EASYOCR ---
        if not is_table:
            # Ảnh đã được xử lý quá đẹp (như bản scan), ta không cần ép EasyOCR dùng mag_ratio nữa để nó chạy tự nhiên
            result = reader.readtext(thresh_img, detail=0, paragraph=True)
            
            if result:
                return " ".join(result)
            return ""
        else:
            # Đối với bảng, ta lấy detail=1 để giữ lấy tọa độ
            result = reader.readtext(thresh_img, detail=1)
            if not result:
                return ""
            
            lines = []
            for bbox, text, conf in result:
                y_center = (bbox[0][1] + bbox[2][1]) / 2
                x_center = (bbox[0][0] + bbox[1][0]) / 2
                lines.append({"y": y_center, "x": x_center, "text": text})
                
            lines.sort(key=lambda item: item['y'])
            y_tolerance = 20 # Ngưỡng dung sai Y cho ảnh đã phóng to 2.5x
            
            rows = []
            current_row = []
            current_y = None
            
            for item in lines:
                if current_y is None:
                    current_y = item['y']
                    current_row.append(item)
                elif abs(item['y'] - current_y) <= y_tolerance:
                    current_row.append(item)
                    current_y = (current_y * (len(current_row) - 1) + item['y']) / len(current_row)
                else:
                    rows.append(current_row)
                    current_row = [item]
                    current_y = item['y']
            if current_row:
                rows.append(current_row)
                
            formatted_text = ""
            for row in rows:
                row.sort(key=lambda item: item['x'])
                row_text = " | ".join([item['text'] for item in row])
                formatted_text += row_text + "\n"
                
            return formatted_text.strip()
    except Exception as e:
        print(f"[OCR ERROR] perform_easyocr_on_crop: {e}")
        return ""
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

    filename = file.filename
    import re
    safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
    base_filename = os.path.splitext(safe_filename)[0]

    try:
        print(f"[UPLOAD] Incoming file: {file.filename}, content_type={file.content_type}")

        # Read image
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        conf = float(request.form.get("conf", 0.25))
        iou = float(request.form.get("iou", 0.45))

        # Run inference
        t0 = time.time()
        results = model.predict(image, conf=conf, iou=iou, verbose=False)
        inference_time = round((time.time() - t0) * 1000, 1)

        result = results[0]
        detections = []
        boxes = result.boxes

        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf_val = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]

                ocr_text = ""

                # --- Xử lý vẽ khung ---
                if cls_name == 'Table':
                    color = (0, 0, 255)    
                    thickness = 3          
                elif cls_name == 'Note':
                    color = (0, 255, 0)
                    thickness = 2
                elif cls_name == 'PartDrawing':
                    color = (255, 0, 0)    
                    thickness = 2
                else:
                    color = (0, 255, 255)  
                    thickness = 2

                crop_filename = ""
                crop_b64 = ""
                # --- TỰ ĐỘNG CROP VÀ LƯU CHO TẤT CẢ VẬT THỂ ---
                try:
                    x1i = max(0, int(x1))
                    y1i = max(0, int(y1))
                    x2i = min(cv_img.shape[1], int(x2))
                    y2i = min(cv_img.shape[0], int(y2))
                    
                    cropped_img = cv_img[y1i:y2i, x1i:x2i]
                    
                    if cropped_img.size != 0:
                        crop_filename = f"{base_filename}_{cls_name}_{len(detections) + 1}.jpg"
                        
                        _, buffer = cv2.imencode('.jpg', cropped_img)
                        crop_b64 = base64.b64encode(buffer).decode('utf-8')

                        # --- GỌI EASYOCR ĐỂ ĐỌC CHỮ (CHỈ CHO NOTE VÀ TABLE) ---
                        if cls_name in ['Table', 'Note']:
                            ocr_text = perform_easyocr_on_crop(cropped_img, is_table=(cls_name == 'Table'))
                            if ocr_text:
                                print(f"[OCR SUCCESS] Đã đọc được đoạn: {len(ocr_text)} characters")
                    else:
                        print("[CROP WARNING] Vùng cắt bị rỗng")
                except Exception as e:
                    print(f"[CROP/OCR ERROR] Lỗi hệ thống: {e}")

                # --- Vẽ khung ---
                cv2.rectangle(cv_img, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
                label = f"{cls_name} {conf_val:.2f}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                
                # Tránh tình trạng nhãn bị tràn lên trên mất hút (Fix luôn lỗi hiển thị)
                label_y = max(int(y1), 20) 
                
                cv2.rectangle(cv_img, (int(x1), label_y - 20), (int(x1) + tw, label_y), color, -1)
                cv2.putText(cv_img, label, (int(x1), label_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # --- Đóng gói JSON ---
                detections.append({
                    "id": len(detections) + 1,
                    "class": cls_name,
                    "confidence": round(conf_val, 2),
                    "bbox": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                    "crop_image": crop_filename,
                    "crop_b64": crop_b64,
                    "ocr_content": ocr_text 
                })

        # --- Kết xuất ảnh ---
        annotated_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_annotated = Image.fromarray(annotated_rgb)

        buf = io.BytesIO()
        pil_annotated.save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        class_counts = {}
        for d in detections:
            name = d["class"]
            class_counts[name] = class_counts.get(name, 0) + 1

        response = {
            "success": True,
            "filename": filename,
            "image_b64": img_b64,
            "inference_time_ms": inference_time,
            "total_detections": len(detections),
            "class_counts": class_counts,
            "detections": detections,
            "image_size": {"width": image.width, "height": image.height},
            "model": "RT-DETR + EasyOCR", 
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "Internal server error", "details": str(e)}), 500

        return jsonify({"error": str(e)}), 500

@app.route("/model-info")
def model_info():
    return jsonify({
        "model": "RT-DETR + EasyOCR",
        "classes": model.names,
        "num_classes": len(model.names),
        "model_path": MODEL_PATH,
    })

@app.route("/crops/<filename>")
def get_crop(filename):
    return send_from_directory(CROP_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)
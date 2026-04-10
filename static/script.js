// ── State ──────────────────────────────────────────────────────────────────
let currentFile = null;
let lastJSON = null;

// ── File Input ─────────────────────────────────────────────────────────────
const fileInput = document.getElementById('file-input');
const dropZone  = document.getElementById('drop-zone');

fileInput.addEventListener('change', e => handleFile(e.target.files[0]));

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});

dropZone.addEventListener('click', (e) => {
  if (e.target !== fileInput) {
    fileInput.click();
  }
});

function handleFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    showToast('⚠️ Vui lòng chọn file ảnh!', true); return;
  }
  currentFile = file;

  // Preview
  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById('preview-img').src = e.target.result;
    document.getElementById('preview-name').textContent =
      `${file.name}  ·  ${(file.size / 1024).toFixed(1)} KB`;
    document.getElementById('preview-wrap').style.display = 'block';
  };
  reader.readAsDataURL(file);

  document.getElementById('btn-predict').disabled = false;
}

// ── Predict ────────────────────────────────────────────────────────────────
async function runPredict() {
  if (!currentFile) return;

  setLoading(true);

  const formData = new FormData();
  formData.append('image', currentFile);
  formData.append('conf', document.getElementById('conf-slider').value);
  formData.append('iou',  document.getElementById('iou-slider').value);

  try {
    const res = await fetch('/predict', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || 'Lỗi server');
    }

    // ① Update annotated image
    const resImg = document.getElementById('result-img');
    resImg.src = `data:image/jpeg;base64,${data.image_b64}`;
    resImg.style.display = 'block';
    document.getElementById('placeholder').style.display = 'none';

    // ② Stats bar
    document.getElementById('stat-time').textContent  = `${data.inference_time_ms} ms`;
    document.getElementById('stat-count').textContent = `${data.total_detections} vật thể`;
    document.getElementById('stats-bar').style.display = 'flex';

    // ③ JSON
    lastJSON = data;
    updateOCRPanel(data.detections);
    const displayDetections = data.detections.map(d => {
      const copy = { ...d };
      delete copy.crop_b64;
      return copy;
    });
    const finalJSON = {
      image: data.filename || "unknown.jpg",
      objects: displayDetections
    };
    document.getElementById('json-output').innerHTML = syntaxHighlight(JSON.stringify(finalJSON, null, 2));

    showToast(`✅ Phát hiện ${data.total_detections} vật thể · ${data.inference_time_ms}ms`);

  } catch (err) {
    showToast('❌ ' + err.message, true);
    document.getElementById('json-output').textContent = `// Lỗi: ${err.message}`;
  } finally {
    setLoading(false);
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function setLoading(on) {
  document.getElementById('spinner').style.display  = on ? 'block' : 'none';
  document.getElementById('btn-text').textContent   = on ? 'Đang xử lý...' : '⚡ Nhận diện';
  document.getElementById('btn-predict').disabled   = on;
}

function syntaxHighlight(json) {
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    match => {
      let cls = 'j-num';
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'j-key' : 'j-str';
      } else if (/true|false/.test(match)) {
        cls = 'j-bool';
      } else if (/null/.test(match)) {
        cls = 'j-null';
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

function updateOCRPanel(detections) {
  const ocrOutput = document.getElementById('ocr-output');
  const ocrItems = detections.map((item, index) => ({
    id: index + 1,
    className: item.class,
    text: item.ocr_content ? item.ocr_content.trim() : "",
    crop: item.crop_image,
    crop_b64: item.crop_b64
  }));

  if (ocrItems.length === 0) {
    ocrOutput.innerHTML = '<p>Không tìm thấy đối tượng nào.</p>';
    return;
  }

  ocrOutput.innerHTML = ocrItems.map(item => `
    <div class="ocr-card" style="margin-bottom: 12px; border: 1px solid #eee; padding: 10px; border-radius: 8px; background: #fafafa;">
      <div class="ocr-card-header" style="display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: 8px; color: #444;">
        <span>${item.className} #${item.id}</span>
        ${item.crop_b64 ? `<a href="javascript:void(0)" onclick="downloadCrop(${item.id})" style="font-size: 13px; color: #0066cc; text-decoration: none; border: 1px solid #0066cc; padding: 4px 8px; border-radius: 4px;">⬇ Tải Ảnh Cắt</a>` : ''}
      </div>
      ${item.text ? `<div class="ocr-card-body" style="white-space: pre-wrap; font-size: 14px; color: #222; background: #fff; padding: 8px; border-radius: 4px; border: 1px solid #ddd;">${escapeHtml(item.text)}</div>` : ''}
    </div>
  `).join('');
}

function downloadCrop(id) {
  if (!lastJSON || !lastJSON.detections) return;
  const item = lastJSON.detections.find(d => d.id === id);
  if (!item || !item.crop_b64) return;
  
  try {
    const byteCharacters = atob(item.crop_b64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], {type: 'image/jpeg'});

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = item.crop_image || `crop_${id}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    showToast('⬇ Đã tải ảnh cắt!');
  } catch (err) {
    showToast('❌ Lỗi tải ảnh!', true);
    console.error(err);
  }
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function copyJSON() {
  if (!lastJSON) { showToast('Chưa có kết quả!', true); return; }
  const displayDetections = lastJSON.detections.map(d => {
    const copy = { ...d };
    delete copy.crop_b64;
    return copy;
  });
  const finalJSON = {
    image: lastJSON.filename || "unknown.jpg",
    objects: displayDetections
  };
  navigator.clipboard.writeText(JSON.stringify(finalJSON, null, 2));
  showToast('📋 Đã copy JSON!');
}

function downloadJSON() {
  if (!lastJSON) { showToast('Chưa có kết quả!', true); return; }
  const displayDetections = lastJSON.detections.map(d => {
    const copy = { ...d };
    delete copy.crop_b64;
    return copy;
  });
  const finalJSON = {
    image: lastJSON.filename || "unknown.jpg",
    objects: displayDetections
  };
  const blob = new Blob([JSON.stringify(finalJSON, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `rtdetr_result_${Date.now()}.json`;
  a.click();
  showToast('⬇ Đã tải JSON!');
}

function clearAll() {
  currentFile = null; lastJSON = null;
  document.getElementById('preview-wrap').style.display = 'none';
  document.getElementById('result-img').style.display  = 'none';
  document.getElementById('placeholder').style.display = 'flex';
  document.getElementById('stats-bar').style.display   = 'none';
  document.getElementById('json-output').textContent   = '// Chạy nhận diện để xem kết quả JSON ở đây...';
  document.getElementById('ocr-output').innerHTML     = '<p>Các đối tượng được cắt (Crops) và nội dung OCR sẽ hiển thị ở đây.</p>';
  document.getElementById('btn-predict').disabled      = true;
  fileInput.value = '';
}

function showToast(msg, isError = false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = isError ? 'error' : '';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

import gdown
import os

# Thay bằng ID file best.pt trên Google Drive của bạn
file_id = '1r5RBeUzsl2NUouctrq75Km_fvaHPr4KD' 
url = f'https://drive.google.com/uc?id={file_id}'

output = 'best.pt'
if not os.path.exists(output):
    print("Đang tải model weights...")
    gdown.download(url, output, quiet=False)
    print("Đã tải xong!")
else:
    print("Model đã tồn tại.")

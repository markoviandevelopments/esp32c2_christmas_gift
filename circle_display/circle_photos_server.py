import os
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps
from io import BytesIO
app = Flask(__name__)

# Main folder for full originals (gallery/download)
FULL_FOLDER = '/home/preston/Desktop/x_mas_gift/circle_display/photos/melanie_cropped'
os.makedirs(FULL_FOLDER, exist_ok=True)

# Separate folder for 240x240 circular crops (for the physical display)
CROPPED_FOLDER = '/home/preston/Desktop/x_mas_gift/circle_display/photos/circle_display_2'
os.makedirs(CROPPED_FOLDER, exist_ok=True)

def create_circular_crop(input_path, output_path):
    """Create perfect 240x240 circular crop with black background"""
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        # Resize while maintaining aspect ratio and centering
        img = ImageOps.fit(img, (240, 240), Image.LANCZOS)

        # Create circular mask
        mask = Image.new("L", (240, 240), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 240, 240), fill=255)

        # Apply mask
        circular = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
        circular.paste(img, (0, 0), mask)

        # Composite onto black background
        background = Image.new("RGB", (240, 240), (0, 0, 0))
        background.paste(circular, mask=circular.split()[3])  # Use alpha channel

        background.save(output_path, "JPEG", quality=95)

@app.route('/upload', methods=['POST'])
def upload_image():
    print("=== Upload request received ===")
    print("Files keys:", list(request.files.keys()))
    
    if 'image' not in request.files:
        print("ERROR: No 'image' field")
        return jsonify({'error': 'No image part'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    try:
        file_data = file.read()
        print("Bytes received:", len(file_data))
        
        if len(file_data) == 0:
            return jsonify({'error': 'Empty file'}), 400
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f'{timestamp}.jpg'
        
        # Save full original
        full_path = os.path.join(FULL_FOLDER, filename)
        with open(full_path, 'wb') as f:
            f.write(file_data)
        
        # Save cropped version from memory
        from io import BytesIO
        img_stream = BytesIO(file_data)
        cropped_path = os.path.join(CROPPED_FOLDER, filename)
        create_circular_crop(img_stream, cropped_path)
        
        print(f"SUCCESS: Saved full '{filename}' and cropped version")
        return jsonify({'success': True, 'message': 'Uploaded!', 'filename': filename}), 200
    
    except Exception as e:
        print("EXCEPTION:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/images/<filename>')
def get_image(filename):
    # Serve from full folder (for gallery/download)
    return send_from_directory(FULL_FOLDER, filename, mimetype='image/jpeg')

@app.route('/cropped/<filename>')
def get_cropped(filename):
    # New endpoint for device to load cropped version
    return send_from_directory(FULL_FOLDER, filename, mimetype='image/jpeg')

@app.route('/list')
def list_images():
    if not os.path.exists(FULL_FOLDER):
        return jsonify([])
    
    files = [f for f in os.listdir(FULL_FOLDER) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    files.sort(reverse=True)
    return jsonify(files)

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_image(filename):
    full_path = os.path.join(FULL_FOLDER, filename)
    cropped_path = os.path.join(CROPPED_FOLDER, filename)
    
    deleted = False
    if os.path.exists(full_path):
        os.remove(full_path)
        deleted = True
    if os.path.exists(cropped_path):
        os.remove(cropped_path)
        deleted = True
    
    if deleted:
        return jsonify({'success': True, 'message': f'{filename} deleted from both folders'})
    return jsonify({'error': 'File not found'}), 404

@app.route('/')
def home():
    return '''
    <h1>CircleScreen Server Running</h1>
    <p>Upload: POST /upload → saves full + cropped</p>
    <p>Full images: /images/&lt;filename&gt;</p>
    <p>Cropped 240x240: /cropped/&lt;filename&gt;</p>
    <p>List: <a href="/list">/list</a></p>
    '''

if __name__ == '__main__':
    print(f"Full folder: {FULL_FOLDER}")
    print(f"Cropped folder: {CROPPED_FOLDER}")
    print("Server starting on http://0.0.0.0:9026")
    app.run(host='0.0.0.0', port=9026, debug=True)

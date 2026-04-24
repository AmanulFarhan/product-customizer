import os
import cv2
import numpy as np
from django.conf import settings
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage


PRINT_AREAS = {
    "white_tshirt": (100, 90, 160, 210),
    "hoodie": (195, 150, 210, 270),
    "cap": (110, 100, 140, 100)
}


def home(request):
    output_image = None
    product = "white_tshirt"  # default

    if request.method == 'POST':
        product = request.POST.get('product', "white_tshirt")

        # Load product image
        product_path = os.path.join(settings.MEDIA_ROOT, 'products', f"{product}.png")
        product_img = cv2.imread(product_path)

        if product_img is None:
            return render(request, 'home.html', {
                'output_image': None,
                'error': 'Product image not found.'
            })

        # Get print area
        x, y, w, h = PRINT_AREAS.get(product, PRINT_AREAS["white_tshirt"])

        # Load design
        design = request.FILES.get('design')
        filename = "default"

        if design:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
            filename = fs.save(design.name, design)
            uploaded_file_path = fs.path(filename)

            design_img = cv2.imread(uploaded_file_path)

            if design_img is None:
                return render(request, 'home.html', {
                    'output_image': None,
                    'error': 'Design image not found.'
                })

            # --- Resize ---
            design_resized = cv2.resize(design_img, (w, h))

            # --- CAP SPECIFIC CURVE ---
            if product == "cap":
                curve = 0.85
                new_w = int(w * curve)
                design_resized = cv2.resize(design_resized, (new_w, h))

                # recenter
                x = x + (w - new_w) // 2
                w = new_w

            # --- Blur control ---
            if product == "cap":
                design_resized = cv2.GaussianBlur(design_resized, (1,1), 0)
            else:
                design_resized = cv2.GaussianBlur(design_resized, (1,1), 0)

            roi = product_img[y:y+h, x:x+w]

            # --- Shading strength ---
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

            if product == "cap":
                shade_strength = 0.6
            else:
                shade_strength = 0.4

            shade = (roi_gray - roi_gray.mean()) * shade_strength + 1.0
            shade = np.dstack([shade, shade, shade])

            # --- Apply shading ---
            design_f = design_resized.astype(np.float32) / 255.0
            shaded = np.clip(design_f * shade, 0, 1)
            shaded = (shaded * 255).astype(np.uint8)

            # --- Contrast boost for cap ---
            if product == "cap":
                shaded = cv2.convertScaleAbs(shaded, alpha=1.15, beta=0)

            # --- Blending ---
            alpha = 0.75
            blended = cv2.addWeighted(shaded, alpha, roi, 1 - alpha, 0)

            # --- Soft mask ---
            mask = np.zeros((h, w), dtype=np.float32)
            cv2.rectangle(mask, (10,10), (w-10, h-10), 1, -1)
            mask = cv2.GaussianBlur(mask, (15,15), 0)

            for c in range(3):
                roi[:, :, c] = roi[:, :, c] * (1 - mask) + blended[:, :, c] * mask

            product_img[y:y+h, x:x+w] = roi

        # Ensure outputs folder exists
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'outputs'), exist_ok=True)

        # --- Save output ---
        output_filename = f"output_{product}.png"
        output_path = os.path.join(settings.MEDIA_ROOT, 'outputs', output_filename)
        cv2.imwrite(output_path, product_img)

        output_image = settings.MEDIA_URL + 'outputs/' + output_filename

    return render(request, 'home.html', {
        'output_image': output_image,
        'product': product
    })
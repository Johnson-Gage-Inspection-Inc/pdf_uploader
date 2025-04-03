from fitz import open as fopen, Matrix
import numpy as np
from PyPDF2 import PdfReader, PdfWriter
from pytesseract import image_to_osd, TesseractError
from PIL import Image
import cv2
import app.color_print as cp
import os
from traceback import print_exc
from app.pdf import open_with_debug, workorders, move_file


def reorient_pdf_for_workorders(filepath: str, REJECT_DIR: str) -> list:
    file_name = os.path.basename(filepath)
    try:
        cp.white("Checking orientation of PDF file..." + file_name)
        orientation = get_pdf_orientation(filepath)  # get orientation of PDF file
        cp.white(f"Orientation: {orientation} | {file_name}")
        if orientation in [90, 180, 270]:
            rotate_pdf(filepath, orientation)  # rotate PDF file

            if orders := workorders(
                filepath
            ):  # parse work order numbers from PDF file name/body
                return orders
            else:  # If there are still no work orders, skip the file
                cp.yellow(f"no work order found in {file_name}, file skipped")
                move_file(filepath, REJECT_DIR)  # move file to reject directory
                return False  # return False to main loop
        elif orientation == 0:
            cp.white(
                "File appears to be right-side-up. Moving file to reject directory..."
            )
            move_file(filepath, REJECT_DIR)  # move file to reject directory
        else:
            cp.yellow(f"Reorientation of {file_name} failed. Skipping file...")
            cp.white("Moving file to reject directory...")
            move_file(filepath, REJECT_DIR)  # move file to reject directory
            return False
    except FileNotFoundError as e:
        cp.red(f"Error: {filepath} not found. {e}")
        return False
    except Exception as e:
        cp.red(f"Error: {e}\nFile: {file_name}")
        return False


def get_pdf_orientation(filepath):
    image = convert_pdf_to_image(filepath)
    grayscale_image = convert_to_grayscale(image)
    text_orientation = get_text_orientation(grayscale_image)
    if text_orientation is None:
        visual_orientation = get_visual_orientation(grayscale_image)
        return visual_orientation
    else:
        return text_orientation


def convert_pdf_to_image(filepath):
    doc = fopen(filepath)
    page = doc.load_page(
        0
    )  # It assumes you want to check the orientation of the first page
    pix = page.get_pixmap(matrix=Matrix(300 / 72, 300 / 72))
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image


def convert_to_grayscale(image):
    grayscale_image = image.convert("L")
    return grayscale_image


def get_text_orientation(image):
    try:

        temp_file = "temp.png"
        image.save(temp_file)  # Save the PIL image to a temporary file
        text = image_to_osd(temp_file)  # Perform OCR on the temporary file
        os.remove(temp_file)  # Remove the temporary file

        for line in text.splitlines():
            if "Rotate: " in line:
                rotation_line = line
                break
        else:
            return None  # No rotation line found

        rotation_angle = int(rotation_line.split(":")[1].strip())
        if rotation_angle not in [0, 90, 180, 270]:
            return None  # Unknown rotation
        else:
            return rotation_angle
    except TesseractError as e:
        cp.yellow("TesseractError: " + str(e))
        return None
    except Exception as e:
        cp.red(e)
        return None


def get_visual_orientation(image):
    try:
        edges = cv2.Canny(np.array(image), 50, 150)  # Image needs to be a NumPy array
        lines = cv2.HoughLines(
            edges, 1, np.pi / 180, threshold=100
        )  # Get all lines in the image
        if lines is None:
            return None  # No lines detected
        orientations = []  # In degrees

        for line in lines:  # line = [[rho, theta]]
            rho, theta = line[0]  # rho = distance from origin, theta = angle
            angle = np.rad2deg(theta)  # Convert radians to degrees
            orientations.append(angle)  # Add angle to list of orientations

        orientation_counts = np.bincount(
            np.array(orientations, dtype=int)
        )  # Count the number of times each orientation appears
        dominant_orientation = np.argmax(
            orientation_counts
        )  # Get the orientation with the most counts

        return dominant_orientation
    except Exception as e:
        cp.red(e)
        return None


def rotate_pdf(filepath, degrees=180):
    file_name = os.path.basename(filepath)
    cp.yellow(f"Orientation: {degrees}° | {file_name}")
    cp.white("Rotating PDF file... " + file_name)
    try:
        if degrees not in [0, 90, 180, 270]:  # Check for valid degrees
            raise ValueError(
                "degrees must be 0, 90, 180, or 270."
            )  # Raise error if invalid degrees

        with open_with_debug(
            filepath, "rb"
        ) as file:  # Open the PDF file in read-binary mode
            reader = PdfReader(file)  # Create a PDF reader object
            writer = PdfWriter()  # Create a PDF writer object
            for page_num in range(
                len(reader.pages)
            ):  # Iterate over each page in the PDF
                page = reader.pages[page_num]  # Get the page object
                page.rotate(degrees)  # Rotate the page
                writer.add_page(page)  # Add the rotated page to the writer object
            with open_with_debug(
                filepath, "wb"
            ) as output_file:  # Prepare a new PDF file with the rotated pages
                writer.write(output_file)
        cp.green(f'"{file_name}" rotated successfully.')
        return True
    except Exception:
        print_exc()
        return False

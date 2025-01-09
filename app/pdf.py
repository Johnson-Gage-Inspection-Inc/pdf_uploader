# /app/pdf.py

from fitz import open as fopen, Matrix
import numpy as np
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
from pytesseract import pytesseract, image_to_osd, image_to_string, TesseractError
from PIL import Image
from pypdfium2 import PdfDocument
from app.config import tesseract_cmd_path

import app.color_print as cp
from re import findall
from time import sleep
from traceback import print_exc
import os
import sys

# pip3 install opencv-python PyMuPDF numpy pdf2image PyPDF2 pytesseract Pillow pypdfium2

try:
    import cv2  # pip3 install opencv-python
    cv2_imported = True
except ImportError as e:
    cv2_imported = False
    cp.white("ImportError: cv2 not found.")
    input(e)
    print_exc()

try:
    pytesseract.tesseract_cmd = tesseract_cmd_path
except Exception as e:
    cp.red(f"Tesseract not found at: {tesseract_cmd_path}. Please install Tesseract and set the path in config.py\n{e}")

#########################################################################################################################
################################## Orientation detection / PDF rotation #################################################
#########################################################################################################################


def get_pdf_orientation(filepath):
    image = convert_pdf_to_image(filepath)
    grayscale_image = convert_to_grayscale(image)
    text_orientation = get_text_orientation(grayscale_image)
    if text_orientation is None and cv2_imported:
        visual_orientation = get_visual_orientation(grayscale_image)
        return visual_orientation
    else:
        return text_orientation


def convert_pdf_to_image(filepath):
    doc = fopen(filepath)
    page = doc.load_page(0)  # It assumes you want to check the orientation of the first page
    pix = page.get_pixmap(matrix=Matrix(300 / 72, 300 / 72))
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image


def convert_to_grayscale(image):
    grayscale_image = image.convert("L")
    return grayscale_image


def get_text_orientation(image):
    try:

        temp_file = "temp.png"
        image.save(temp_file)                           # Save the PIL image to a temporary file
        text = image_to_osd(temp_file)      # Perform OCR on the temporary file
        os.remove(temp_file)                            # Remove the temporary file

        for line in text.splitlines():
            if "Rotate: " in line:
                rotation_line = line
                break
        else:
            return None                                 # No rotation line found

        rotation_angle = int(rotation_line.split(":")[1].strip())
        if rotation_angle not in [0, 90, 180, 270]:
            return None                                 # Unknown rotation
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
        edges = cv2.Canny(np.array(image), 50, 150)                             # Image needs to be a NumPy array
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)            # Get all lines in the image
        if lines is None:
            return None                                           # No lines detected
        orientations = []                                                       # In degrees

        for line in lines:                                                      # line = [[rho, theta]]
            rho, theta = line[0]                                                # rho = distance from origin, theta = angle
            angle = np.rad2deg(theta)                                           # Convert radians to degrees
            orientations.append(angle)                                          # Add angle to list of orientations

        orientation_counts = np.bincount(np.array(orientations, dtype=int))     # Count the number of times each orientation appears
        dominant_orientation = np.argmax(orientation_counts)                    # Get the orientation with the most counts

        return dominant_orientation
    except Exception as e:
        cp.red(e)
        return None


def rotate_pdf(filepath, degrees=180):
    try:
        if degrees not in [0, 90, 180, 270]:                                    # Check for valid degrees
            raise ValueError('degrees must be 0, 90, 180, or 270.')             # Raise error if invalid degrees

        with open_with_debug(filepath, 'rb') as file:                           # Open the PDF file in read-binary mode
            reader = PdfReader(file)                                     # Create a PDF reader object
            writer = PdfWriter()                                         # Create a PDF writer object
            for page_num in range(len(reader.pages)):                           # Iterate over each page in the PDF
                page = reader.pages[page_num]                                   # Get the page object
                page.rotate(degrees)                                            # Rotate the page
                writer.add_page(page)                                           # Add the rotated page to the writer object
            with open_with_debug(filepath, 'wb') as output_file:                # Prepare a new PDF file with the rotated pages
                writer.write(output_file)                                       # Write the rotated pages to the new file
        cp.green("PDF rotation complete.")
        return True
    except Exception:
        print_exc()
        return False

#########################################################################################################################
########################################## everything else ##############################################################
#########################################################################################################################


PO_NUM_FORMAT = r"56561-\d{6}"


def open_with_debug(file_path, mode='r'):
    try:
        file_obj = open(file_path, mode)
        return file_obj
    except Exception:
        print_exc()
        sys.exit(1)


# Iterate over PDF files in directory
def next(dirname):
    for file in os.listdir(dirname):
        filename = os.fsdecode(file)
        if filename.lower().endswith(".pdf"):
            fpath = os.path.join(dirname, filename)
            yield fpath
        else:
            continue


# Takes a PDF file path as input and converts the PDF into a list of PIL images, representing each page.
def _pdf_to_img(pdf_file):
    try:
        images = []
        pdf = PdfDocument(pdf_file)                         # Splits the PDF into pages
        n_pages = len(pdf)                                  # Get number of pages
        for page_number in range(n_pages):                  # Loop through pages
            page = pdf.get_page(page_number)                # Get page
            pil_image = page.render(                        # Render page
                scale=1,                                    # 1 = 100% scale
                rotation=0,                                 # 0 = 0 degrees rotation
                crop=(0, 0, 0, 0)                           # No crop
            ).to_pil()                                      # Convert to PIL image
            images.append(pil_image)                        # Add to list
            page.close()                                    # Close page
        pdf.close()                                         # Close PDF
        return images                                       # Return list of PIL images (one per page)

    except Exception as e:
        cp.red(e)
        print_exc()
        try:
            # Fallback option: Use pdf2image library
            cp.yellow(f"PyPDFium2 failed. Using pdf2image to convert {os.path.basename(pdf_file)} to images.")
            images = convert_from_path(pdf_file)
            return images
        except Exception as fallback_error:
            cp.red("Fallback conversion to images failed:")
            cp.red(fallback_error)
            print_exc()
    return []


# extract text from pdf using tesseract OCR
def tesseractOcr(pdf_file):
    images = _pdf_to_img(pdf_file)                          # Get list of PIL images
    text = []
    for pg, img in enumerate(images):                       # Loop through images
        page_text = image_to_string(img)        # OCR image
        text.append(page_text)                              # Append to list
    return text                                             # Return text string of all pages


# extract text from pdf
def extract(filepath):
    text = []
    # cp.white(f"Scanning {filepath} for text...")

    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            text.append(page.extract_text())
    except Exception as e:
        cp.white(e)
    try:
        if text == []:
            cp.yellow(f"PyPDF2 failed. Using OCR to extract text from {filepath}.")
            text = tesseractOcr(filepath)
        else:
            cp.white(f"Used PyPDF2 to extract text from {filepath}.")
    except Exception as e:
        cp.white(e)
        pass

    return text


# Extract relevant pages from PDF, and create child PDFs
def create_child_pdf(filepath, pg_nums, output_path):
    try:
        with open_with_debug(filepath, 'rb') as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            pdf_writer = PdfWriter()
            for page_num in pg_nums:
                pdf_writer.add_page(pdf_reader.pages[page_num])
            with open_with_debug(output_path, 'wb') as output:
                pdf_writer.write(output)
    except Exception as e:
        cp.red(e)
    finally:
        pdf_file.close()


# extract work orders from pdf, create a set of pages for each work order, append pages with no work order to the previous work order.
def workorders(filepath):
    order_number = ''
    fileorders = findall(PO_NUM_FORMAT, filepath)            # Find order numbers in file name
    if fileorders != []:                                        # If order number found in file name
        return fileorders                                       # Return orders number found in file name

    text = extract(filepath)                                    # Get list of text from PDF
    scannedorders = {}                                          # Create empty dictionary for order numbers
    for page_index, page in enumerate(text):                    # Loop through pages
        order_numbers = findall(PO_NUM_FORMAT, page)         # Find order numbers in page
        if order_numbers != []:                                 # If new order number found
            order_number = order_numbers[0]                     # Use new order number
        else:
            if order_number == '':                              # If no old order number
                continue                                        # Skip page
            if page.strip() == '':                              # If page is empty
                continue                                        # Skip page

        if order_number not in scannedorders:
            scannedorders[order_number] = set()                 # Create empty set for order number
        scannedorders[order_number].add(page_index)             # Add page number to set
    return scannedorders                                        # Return dictionary of order numbers and page numbers


# Function to increment filename if the file already exists
def increment_filename(old_filename):
    for i in range(99, 0, -1):
        old_suffix = f" ({i}).pdf"
        new_suffix = f" ({i + 1}).pdf"
        new_filename = old_filename.replace(old_suffix, new_suffix)
        if new_filename != old_filename:
            break
    else:
        new_filename = old_filename.replace(".pdf", " (1).pdf")
    sleep(1)  # Wait 1 second before renaming
    return new_filename


# Move the file to the reject directory
def move_file(filepath, output_dir):
    file_name = os.path.basename(filepath)
    new_filepath = os.path.join(output_dir, file_name)
    attempt = 0
    while attempt < 50:  # Max number of rename attempts = 50
        try:
            os.rename(filepath, new_filepath)
            cp.green(f"Moved file to {new_filepath}.")
            return new_filepath
        except PermissionError as e:
            cp.red(e)
            attempt += 1
            sleep(1)  # Wait 1 second before retrying
        except FileExistsError:
            if attempt == 0:
                print("Incrementing filename...", end="")
            else:
                print(".", end="")
            cp.white()
            new_filepath = increment_filename(new_filepath)
            attempt += 1
        except FileNotFoundError as e:  # This probably means the file was already moved by another process (Perhaps another instance of this script is running?)
            cp.red(e)
            return False  # File not found, no need to retry
        except Exception as e:
            cp.red("Unexpected exception for " + filepath)
            cp.red(f"Failed to move {filepath} to {new_filepath}.")
            cp.red(e)
            print_exc()
            return False

    # If all rename attempts failed, handle the error
    cp.red(f"Failed to move file to the reject directory: {filepath}")
    return False


# Try to rename file, return True if successful, False if not
def try_rename(src_path, dst_path):
    try:
        os.rename(src_path, dst_path)
        return True
    except FileExistsError:
        return False
    except FileNotFoundError:
        raise
    except Exception as e:
        cp.red(e)
        cp.red(f"Failed to rename file: {e}")
        return False

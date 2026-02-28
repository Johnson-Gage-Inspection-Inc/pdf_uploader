# /app/pdf.py

from typing import Any

from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
from pytesseract import pytesseract, image_to_string
from pypdfium2 import PdfDocument
from app.config import tesseract_cmd_path

import app.color_print as cp
from re import findall
from time import sleep
from traceback import print_exc
import os
import sys


def open_with_debug(file_path, mode="r"):
    try:
        file_obj = open(file_path, mode)
        return file_obj
    except Exception:
        print_exc()
        sys.exit(1)


try:
    pytesseract.tesseract_cmd = tesseract_cmd_path
except Exception as e:
    cp.red(
        f"Tesseract not found at: {tesseract_cmd_path}. Please install Tesseract and set the path in config.py\n{e}"
    )

WO_NUM_FORMAT = r"56561-\d{6}"


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
        pdf = PdfDocument(pdf_file)  # Splits the PDF into pages
        n_pages = len(pdf)  # Get number of pages
        for page_number in range(n_pages):  # Loop through pages
            page = pdf.get_page(page_number)  # Get page
            pil_image = page.render(  # Render page
                scale=1,  # 1 = 100% scale
                rotation=0,  # 0 = 0 degrees rotation
                crop=(0, 0, 0, 0),  # No crop
            ).to_pil()  # Convert to PIL image
            images.append(pil_image)  # Add to list
            page.close()  # Close page
        pdf.close()  # Close PDF
        return images  # Return list of PIL images (one per page)

    except Exception as e:
        cp.red(e)
        print_exc()
        try:
            # Fallback option: Use pdf2image library
            cp.yellow(
                f"PyPDFium2 failed. Using pdf2image to convert {os.path.basename(pdf_file)} to images."
            )
            images = convert_from_path(pdf_file)
            return images
        except Exception as fallback_error:
            cp.red("Fallback conversion to images failed:")
            cp.red(fallback_error)
            print_exc()
    return []


# extract text from pdf using tesseract OCR
def tesseractOcr(pdf_file):
    images = _pdf_to_img(pdf_file)  # Get list of PIL images
    text = []
    for pg, img in enumerate(images):  # Loop through images
        page_text = image_to_string(img)  # OCR image
        text.append(page_text)  # Append to list
    return text  # Return text string of all pages


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
        if text == [] or all([not t for t in text]):
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
        with open_with_debug(filepath, "rb") as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            pdf_writer = PdfWriter()
            for page_num in pg_nums:
                pdf_writer.add_page(pdf_reader.pages[page_num])
            with open_with_debug(output_path, "wb") as output:
                pdf_writer.write(output)
    except Exception as e:
        cp.red(e)


# extract work orders from pdf, create a set of pages for each work order
# append pages with no work order to the previous work order.
# TODO: Make the return type consistent. Right now it returns a dict if no work order numbers are found in the file name, and a list if work order numbers are found in the file name. This is confusing and should be fixed.
def workorders(filepath) -> dict | list[Any]:
    order_number = ""
    fileorders = findall(WO_NUM_FORMAT, filepath)  # Find order numbers in file name

    # Use order number from file name if found
    if fileorders != []:
        return fileorders

    pages = extract(filepath)  # Get list of text from PDF
    scannedorders: dict[str, set[int]] = {}  # Create empty dictionary for order numbers
    for page_index, page in enumerate(pages):
        order_numbers = findall(WO_NUM_FORMAT, page)  # Find order numbers in page
        # Use new order number if found
        if order_numbers != []:
            order_number = order_numbers[0]
        else:
            # Skip pages without order numbers
            if order_number == "":
                continue
            # Skip emptry pages
            if page.strip() == "":
                continue

        if order_number not in scannedorders:
            scannedorders[order_number] = set()  # Create empty set for order number
        scannedorders[order_number].add(page_index)  # Add page number to set
    return scannedorders  # Return dictionary of order numbers and page numbers


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
def move_file(filepath, output_dir) -> str | bool:
    file_name = os.path.basename(filepath)
    new_filepath = os.path.join(output_dir, file_name)
    attempt = 0
    while attempt < 50:  # Max number of rename attempts = 50
        try:
            os.rename(filepath, new_filepath)
            cp.green(f"Moved file to {os.path.relpath(new_filepath)}.")
            return new_filepath
        except PermissionError as e:
            cp.yellow(e)
            attempt += 1
            sleep(1)  # Wait 1 second before retrying
        except FileExistsError:
            if attempt == 0:
                print("Incrementing filename...", end="")
            else:
                print(".", end="")
            print()
            new_filepath = increment_filename(new_filepath)
            attempt += 1
        except FileNotFoundError as e:
            # This probably means the file was already moved by another process
            # (Perhaps another instance of this script is running?)
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

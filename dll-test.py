import cv2

# Get the path to the cv2 module file
cv2_path = cv2.__file__

# Extract the directory containing the DLLs
dll_directory = cv2_path.split('cv2')[0]

# Print the DLL directory
print("OpenCV DLL directory:", dll_directory)

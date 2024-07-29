import os
import my_tools
import cv2

root = os.path.dirname(os.path.realpath("cat_cnn.py"))

# Load the cascade classifier for detecting cat faces
face_cascade = cv2.CascadeClassifier(root + '/etc/Cat_Dataset/haarcascade_frontalcatface.xml')

for cat in my_tools.get_files_in_path(root + '/etc/Cat_Dataset/', root, 'jpg'):
    # Load the image and convert it to grayscale
    img = cv2.imread(root + '/etc/Cat_Dataset/' + cat)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detect cat faces in the image
    faces = face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5)

    # Check if any faces were detected
    if len(faces) == 0:
        print("No cat faces detected")
    else:
        print("Cat faces detected")

    # Draw rectangles around the cat faces
    for (x, y, w, h) in faces:
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)

    # Display the image
    cv2.imshow('Cat faces', img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
